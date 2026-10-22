"""Beam search for robust Pac-Man routes, using MAME as the simulator.

A route is the direction taken at each node (junction or corner), never reversing. Presses are
"early": made as soon as the previous node is passed. Measured in MAME, any press made at least
4px before the turn gives an identical game, so the only timing requirement is that each turn's
early-press window (passing previous node -> 4px before turn) is long enough: --minwin frames.

Every candidate move is run from each requested level's start state; a move survives only if
it survives on all of them, which is how one route gets shared across a group of levels.
"""
import argparse
import itertools
import json
import os
import pickle
import queue
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import maze
from worker import Worker, STATE_DIR


@dataclass
class Cand:
    route: list
    tile: tuple
    heading: str
    eaten: frozenset
    frames: int
    risk: float
    fruits: int  # min over levels
    sims: list
    segs: list
    score: float = 0.0
    after: int = -1  # moves played since the goal was reached (-1: not yet)


class Pool:
    def __init__(self, n):
        self.q = queue.Queue()
        with ThreadPoolExecutor(n) as ex:
            for w in ex.map(lambda _: Worker(), range(n)):
                self.q.put(w)
        self.ex = ThreadPoolExecutor(n)

    def submit(self, fn, *args):
        def task():
            w = self.q.get()
            try:
                return fn(w, *args)
            finally:
                self.q.put(w)
        return self.ex.submit(task)

    def close(self):
        while not self.q.empty():
            self.q.get().close()


_ids = itertools.count()
_id_lock = threading.Lock()


# savestates of concurrent runs share STATE_DIR, so every name carries this run's prefix
RUN = f"r{os.getpid()}"


def new_name():
    with _id_lock:
        return f"{RUN}n{next(_ids)}"


def parse_seg(r):
    st, fr, mc, mr, mind, dots, tc, tr, win, fruits, lead = r.split()
    return dict(st=st, fr=int(fr), node=(int(mc), int(mr)), mind=int(mind), dots=int(dots),
                tile=(int(tc), int(tr)), win=int(win), fruits=int(fruits), lead=int(lead))


BADLOADS = []


def base(sim):
    """Savestate name of a sim: strips the late marker "*" and the jitter seed "~s"."""
    return sim.split("~")[0].split("@")[0].rstrip("*")


def jitter_lag(sim, depth, corner):
    """A jitter sim ("name~seed") presses every turn a fixed pseudo-random number of frames late,
    the same ranges validate.py uses, so the search tests the timings the validator will.
    "name~fK" presses every turn exactly K frames late (a consistently late player)."""
    tag = sim.split("~")[1]
    if tag.startswith("f"):
        return int(tag[1:])
    if tag.startswith("h"):
        hist = HISTORIES[tag]
        return hist[depth] if depth < len(hist) else 0
    seed = int(tag)
    return random.Random(seed * 7919 + depth).randint(0, JITTER_CORNER if corner else JITTER)


def stepped_lag(lag):
    """Saving the state at the end of a move costs one emulated frame, so a sim that is reloaded for
    every move starts each move one frame later than straight-through play (validate.py, a human).
    Press one frame sooner to make "k frames late" mean the same thing in both."""
    return max(0, lag - 1)


def run_child(w, sims, held, opt, minwin, route=(), expect=None, corner=False):
    """Run one move on every sim; stop at the first failure.

    Returns (status, sims, results); on failure (status, index of the failing sim, None). The
    first len(sims0) sims are always the per-level on-time sims, in level order.

    A sim name "name~seed" is a jitter sim (see jitter_lag); `corner` says whether this move's
    node is a corner, and len(route) is the move number.

    A sim name ending in "*" is a "late player" variant: it presses every corner turn `minwin`
    frames after passing the previous node, so at a tight corner Pac-Man pauses against the wall
    first. When an on-time sim takes a corner whose window is shorter than `minwin`, a late variant
    is spawned from it; from then on the route has to survive both.
    """
    if BRANCH:
        return run_child_branch(w, sims, held, opt, minwin, route, expect)
    out, res, spawned = [], [], []
    for i, sim in enumerate(sims):
        late = sim.endswith("*")
        jit = "~" in sim
        name0 = base(sim)
        got = w.cmd(f"load {name0} {held}")
        if expect and got != expect:
            BADLOADS.append((sim, "".join(route), expect, got, w.cmd(f"load {name0} {held}")))
            return "badload", i, None
        lag = 0
        if opt != held:
            lag = minwin if late else jitter_lag(sim, len(route), corner) if jit else 0
        if LATE_REL and lag:  # k frames after the last press that still corners cleanly
            r = parse_seg(w.cmd(f"seg {opt} 4 {lag}"))
        else:
            r = parse_seg(w.cmd(f"seg {opt} E {stepped_lag(lag)}"))
        if r["st"] not in ("ok", "clear"):
            if r["st"] == "stuck":
                print(f"STUCK route={''.join(route)}+{opt} {r}", flush=True)
            return r["st"], i, None
        # a late press at a corner only makes Pac-Man pause there; at a junction it sends him the
        # wrong way, so junctions get the full window and corners a shorter one
        corner = len(maze.exits(*r["node"])) == 2
        if not late and not jit and opt != held and r["win"] < (CORNER_MINWIN if corner else minwin):
            return "shortwin", i, None
        name = new_name()
        w.cmd(f"save {name}")
        out.append(name + ("*" if late else "") + (sim[sim.index("~"):] if jit else ""))
        res.append(r)
        if not late and not jit and corner and opt != held and r["win"] < minwin and LATE_VARIANTS:
            w.cmd(f"load {name0} {held}")
            rl = parse_seg(w.cmd(f"seg {opt} E {stepped_lag(minwin)}"))
            if rl["st"] not in ("ok", "clear"):
                return "late-" + rl["st"], i, None
            lname = new_name()
            w.cmd(f"save {lname}")
            spawned.append(lname + "*")
            res.append(rl)
    return ("clear" if all(r["st"] == "clear" for r in res) else "ok"), out + spawned, res


def run_child_branch(w, sims, held, opt, minwin, route=(), expect=None):
    """--branch N: at a turn, every sim splits into one per press 0..N frames late (counted from the
    last clean-cornering point); children that leave the game in an identical state (RAM hash) merge.
    Each level keeps its on-time sim (the first len(SIMS0) sims, in level order) plus at most
    BRANCH_CAP others ("name@<level index>"), a random sample, so the set stays affordable."""
    n0 = len(SIMS0)
    main, extra, res, seen = [None] * n0, {}, [], set()
    for i, sim in enumerate(sims):
        lv = i if i < n0 else int(sim.split("@")[1])
        for k in (range(BRANCH + 1) if opt != held else [0]):
            got = w.cmd(f"load {base(sim)} {held}")
            if expect and got != expect:
                BADLOADS.append((sim, "".join(route), expect, got, w.cmd(f"load {base(sim)} {held}")))
                return "badload", i, None
            r = parse_seg(w.cmd(f"seg {opt} 4 {k}" if k else f"seg {opt} E 0"))
            if r["st"] not in ("ok", "clear"):
                return r["st"], i, None
            on_time = i < n0 and k == 0
            if on_time and opt != held:
                corner = len(maze.exits(*r["node"])) == 2
                if r["win"] < (CORNER_MINWIN if corner else minwin):
                    return "shortwin", i, None
            h = w.cmd("hash").split()[1]
            if h in seen and not on_time:
                continue
            seen.add(h)
            name = new_name()
            w.cmd(f"save {name}")
            res.append(r)
            if on_time:
                main[i] = name
            else:
                extra.setdefault(lv, []).append(name)
    rng = random.Random("".join(route) + opt)
    kept = [f"{n}@{lv}" for lv, names in sorted(extra.items())
            for n in (names if len(names) <= BRANCH_CAP else rng.sample(names, BRANCH_CAP))]
    return ("clear" if all(r["st"] == "clear" for r in res) else "ok"), main + kept, res


CLUSTER_COST = 40
CORNER_MINWIN = 8
LATE_VARIANTS = True
TURN_COST = 0.0
JITTER, JITTER_CORNER = 8, 10
HISTORIES = {}  # "h<level>_<j>" -> per-move lateness, from exhaust.py --dump
BRANCH, BRANCH_CAP = 0, 0
LATE_REL = False  # --late-rel: jitter/fixed sims count lateness from the turn, not the previous junction
GOAL = maze.DOTS  # --leave-pockets: every dot but the energizer pockets, which are never entered
AVOID = frozenset()


SAFE_AFTER = 0  # --safe-after: moves every sim must survive past the goal before it counts


def done(c):
    return GOAL <= c.eaten


def finished(c):
    """The goal is reached and every sim has lived SAFE_AFTER more moves (not just reached it with
    a ghost about to land on Pac-Man)."""
    return c.after >= SAFE_AFTER


def allowed(c, node, opt):
    """Never reverse; stay out of the pockets until the goal is reached."""
    return opt != maze.REV[c.heading] and (c.after >= 0 or maze.step(*node, opt) not in AVOID)


def score(c):
    left = GOAL - c.eaten
    near = maze.bfs_dist(c.tile, left)
    # each stranded pocket of dots costs a long trip back later (with a faster red ghost)
    return (len(c.eaten) * 10 - c.frames * 0.25 - near * 6 - c.risk * 2 + c.fruits * 400
            - maze.clusters(left) * CLUSTER_COST - n_turns(c) * TURN_COST)


def n_turns(c):
    return sum(s["turn"] for s in c.segs)


def solution_cost(c):
    """Which of two clearing routes is better: faster, and (with --turn-cost) fewer turns."""
    return c.frames * 0.25 + n_turns(c) * TURN_COST


def cleanup(keep, pattern="n*"):
    keep = {f"{base(k)}.sta" for k in keep}
    for f in (STATE_DIR / "pacman").glob(f"{RUN}{pattern}.sta"):
        if f.name not in keep:
            try:
                f.unlink()
            except OSError:
                pass


def make_starts(pool, levels):
    def mk(w, lv):
        w.cmd("newgame"); w.cmd(f"level {lv}"); w.cmd(f"save {RUN}start_L{lv}")
        return w.cmd("peek")
    for lv in levels:
        print("start", lv, pool.submit(mk, lv).result())
    return [f"{RUN}start_L{lv}" for lv in levels]


def make_child(c, path, opt, sims, res):
    r0 = res[0]
    ch = Cand(c.route + [opt], r0["tile"], opt,
              c.eaten | (frozenset(path) & maze.DOTS) | (frozenset([r0["tile"]]) & maze.DOTS),
              c.frames + max(r["fr"] for r in res),
              c.risk + max(0, 24 - min(r["mind"] for r in res)),
              c.fruits + min(r["fruits"] for r in res), sims,
              c.segs + [dict(node=r0["node"], dir=opt, turn=opt != c.heading,
                             win=min(r["win"] for r in res), mind=min(r["mind"] for r in res),
                             frames=r0["fr"])])
    ch.after = c.after + 1 if c.after >= 0 else (0 if done(ch) else -1)
    ch.score = score(ch) + (100000 + 1000 * ch.after if ch.after >= 0 else 0)
    return ch


def plan_moves(tile, heading, left, rng, k=3, cap=80):
    """A complete cleanup route through every dot in `left`: repeatedly head for one of the k
    nearest moves that eats something (random pick, so each call gives a different order)."""
    import heapq
    left, moves = set(left), []
    while left and len(moves) < cap:
        # Dijkstra over (tile, heading) by tiles walked, never reversing
        pq, seen, goals, tie = [(0, 0, tile, heading, ())], set(), [], itertools.count(1)
        while pq and len(goals) < k:
            dist, _, t, h, ms = heapq.heappop(pq)
            if (t, h) in seen or len(ms) > 25:
                continue
            seen.add((t, h))
            node, path = maze.next_node(*t, h)
            for opt in maze.exits(*node):
                nt = maze.step(*node, opt)
                if opt == maze.REV[h] or nt in AVOID:
                    continue
                walked = set(path) | {nt}
                if walked & left:
                    goals.append((ms + (opt,), nt, opt))
                else:
                    heapq.heappush(pq, (dist + len(path), next(tie), nt, opt, ms + (opt,)))
        if not goals:
            return None
        ms, _, _ = rng.choice(goals)
        for opt in ms:  # walk the chosen moves, eating as we go
            node, path = maze.next_node(*tile, heading)
            tile, heading = maze.step(*node, opt), opt
            left -= set(path) | {tile}
            moves.append(opt)
    return moves if not left else None


def rollout(w, c, moves, minwin):
    """Play a whole planned move list from candidate c on all its sims.

    Returns (clearing child, None) or (None, (status, failing sim index, dots left))."""
    for opt in moves:
        node, path = maze.next_node(*c.tile, c.heading)
        st, sims, res = run_child(w, c.sims, c.heading, opt, minwin, c.route,
                                  corner=len(maze.exits(*node)) == 2)
        if res is None:
            return None, (st, sims, len(GOAL - c.eaten))
        c = make_child(c, path, opt, sims, res)
        if st == "clear" or finished(c):
            return c, None
        if c.after >= 0:  # goal reached: any continuation that every sim survives will do
            s = survive(w, c, minwin)
            return (s, None) if s else (None, ("dead-after-goal", None, 0))
    return None, ("unfinished", None, len(GOAL - c.eaten))


def survive(w, c, minwin):
    """Depth-first: extend c past the goal until finished(), trying every option at each node."""
    if finished(c):
        return c
    node, path = maze.next_node(*c.tile, c.heading)
    for opt in maze.exits(*node):
        if allowed(c, node, opt):
            st, sims, res = run_child(w, c.sims, c.heading, opt, minwin, c.route,
                                      corner=len(maze.exits(*node)) == 2)
            if res is not None:
                s = survive(w, make_child(c, path, opt, sims, res), minwin)
                if s:
                    return s
    return None


def endgame(pool, beam, args, rng):
    """Try full planned cleanup routes from the best few candidates that have few dots left."""
    cands = [c for c in beam if len(GOAL - c.eaten) <= args.endgame][:args.endgame_cands]
    jobs, tried = [], set()
    for c in cands:
        for _ in range(args.endgame_plans):
            mv = plan_moves(c.tile, c.heading, GOAL - c.eaten, rng)
            if mv and (id(c), tuple(mv)) not in tried:
                tried.add((id(c), tuple(mv)))
                jobs.append(pool.submit(rollout, c, mv, args.minwin))
    sols, why = [], {}
    for j in jobs:
        s, fail = j.result()
        if s is not None and s.fruits >= args.need_fruits:
            sols.append(s)
        elif fail:
            st, i, left = fail
            who = "-" if i is None else sim_label(SIMS0, i)
            k = f"{st}:{who}"
            n, tot = why.get(k, (0, 0))
            why[k] = (n + 1, tot + left)
    summary = {k: f"{n}x avg{tot / n:.0f}left" for k, (n, tot) in sorted(why.items(), key=lambda kv: -kv[1][0])}
    return min(sols, key=solution_cost) if sols else None, len(jobs), summary


SIMS0 = []


def sim_label(sims0, i):
    """Failing-sim index -> level label ("L5", jitter sims "L5~"); indexes past the starting
    sims are late-press variants."""
    if i >= len(sims0):
        return "late"
    s = sims0[i].split("start_")[-1]
    return s.split("~")[0] + "~" if "~" in s else s


CKPT_KEYS = ("depth", "beam", "best_partial", "best_depth", "solution", "snapshots", "last_beam",
             "backtracks", "misses", "last_target")


def save_checkpoint(args, sims0, state, rng):
    """Everything the search loop needs to carry on (--resume), written atomically. The savestates
    it refers to stay on disk: the beam and snapshots are never cleaned up while they're live."""
    state = dict(state, rng=rng.getstate(), sims0=sims0, histories=HISTORIES, run=RUN)
    tmp = args.checkpoint + ".tmp"
    with open(tmp, "wb") as f:
        pickle.dump(state, f)
    os.replace(tmp, args.checkpoint)


def search(pool, sims0, args, log=print, resume=None):
    SIMS0[:] = sims0
    t0 = time.time()
    n = len(sims0)
    beam = [Cand([], (13, 23), "L", frozenset(), 0, 0.0, 0, sims0, [])]
    # --prefix: play a given opening (e.g. a human's, from watch.py) and search on from its end
    for opt in ("" if resume else args.prefix):
        c = beam[0]
        node, path = maze.next_node(*c.tile, c.heading)
        st, sims, res = pool.submit(run_child, c.sims, c.heading, opt, args.minwin, c.route,
                                    f"ok {c.tile[0]} {c.tile[1]} {len(c.eaten)}" if c.route else None,
                                    len(maze.exits(*node)) == 2).result()
        if res is None:
            log(f"prefix fails at move {len(c.route)} ({opt} at {node}): {st} on {sim_label(sims0, sims)}")
            break
        beam = [make_child(c, path, opt, sims, res)]
    if args.prefix:
        log(f"prefix: {len(beam[0].route)}/{len(args.prefix)} moves, {len(beam[0].eaten)} dots")
    best_partial, best_depth, solution = beam[0], len(beam[0].route), None
    rng = random.Random(args.seed)
    # backtracking: the beam narrows to one family of routes near the end, and when that family
    # dies the search has nothing to fall back on. Keep a beam snapshot every 5 moves; on a dead
    # end, rewind (further each time it fails again) and drop the ancestors of the dead family.
    snapshots, last_beam, backtracks, misses, last_target = [], beam, 0, 0, None
    depth = len(beam[0].route) - 1
    if resume:
        (depth, beam, best_partial, best_depth, solution, snapshots, last_beam, backtracks, misses,
         last_target) = (resume[k] for k in CKPT_KEYS)
        rng.setstate(resume["rng"])
        log(f"resumed at d={depth} from {args.checkpoint}")
        depth -= 1
    while True:
        depth += 1
        if depth % 5 == 0 and not (snapshots and snapshots[-1][0] == depth):
            snapshots = (snapshots + [(depth, beam)])[-args.snapshots:]
            if args.checkpoint:
                save_checkpoint(args, sims0, dict(
                    depth=depth, beam=beam, best_partial=best_partial, best_depth=best_depth, solution=solution,
                    snapshots=snapshots, last_beam=last_beam, backtracks=backtracks, misses=misses,
                    last_target=last_target), rng)
        jobs = []
        for c in beam:
            node, path = maze.next_node(*c.tile, c.heading)
            for opt in maze.exits(*node):
                if allowed(c, node, opt):
                    jobs.append((c, path, opt, pool.submit(run_child, c.sims, c.heading, opt, args.minwin, c.route,
                                                         f"ok {c.tile[0]} {c.tile[1]} {len(c.eaten)}" if c.route else None,
                                                         len(maze.exits(*node)) == 2)))
        children, fails, by_sim = {}, {}, {}
        for c, path, opt, fut in jobs:
            st, sims, res = fut.result()
            if res is None:
                who = sim_label(sims0, sims)
                fails[st] = fails.get(st, 0) + 1
                by_sim[who] = by_sim.get(who, 0) + 1
                continue
            ch = make_child(c, path, opt, sims, res)
            r0 = res[0]
            if r0["dots"] != len(ch.eaten) and args.debug:
                print(f"DOTMISMATCH game={r0['dots']} mine={len(ch.eaten)} route={''.join(ch.route)}", flush=True)
            if st == "clear" or finished(ch):
                if ch.fruits < args.need_fruits:
                    fails["nofruit"] = fails.get("nofruit", 0) + 1
                elif solution is None or solution_cost(ch) < solution_cost(solution):
                    solution = ch
                continue
            key = (ch.tile, ch.heading, ch.eaten)
            if key not in children or children[key].score < ch.score:
                children[key] = ch
        ranked = sorted(children.values(), key=lambda c: -c.score)
        per, beam = {}, []
        for c in ranked:
            k = (c.tile, c.heading)
            if per.get(k, 0) < max(2, args.beam // 8):
                per[k] = per.get(k, 0) + 1
                beam.append(c)
            if len(beam) >= args.beam:
                break
        if args.endgame and solution is None and beam and depth % args.endgame_every == 0:
            sol, njobs, why = endgame(pool, beam, args, rng)
            if njobs:
                log(f"d={depth} endgame: {njobs} planned cleanups tried -> {'CLEARED' if sol else 'none cleared'} {why}")
            if sol:
                solution = sol
        if beam and len(beam[0].eaten) > len(best_partial.eaten):
            best_partial, best_depth, misses = beam[0], depth, 0
        if beam:
            last_beam = beam
        dead_end = solution is None and (not beam or depth - best_depth > args.stall)
        if dead_end and backtracks < args.backtracks:
            why = "beam died" if not beam else f"no progress past {len(best_partial.eaten)} dots"
            dead = {tuple(c.route) for c in last_beam}
            # a repeat failure (no new best since the last rewind) rewinds to before the last target
            limit = last_target - 1 if misses and last_target is not None else depth
            alive = []
            for back in range(1, len(snapshots) + 1):
                snap_depth, snap = snapshots[-back]
                if snap_depth > limit:
                    continue
                alive = [c for c in snap if not any(r[:len(c.route)] == tuple(c.route) for r in dead)]
                if alive:
                    break
            if alive:
                backtracks, misses, last_target = backtracks + 1, misses + 1, snap_depth
                log(f"d={depth} {why}: backtrack #{backtracks} to d={snap_depth}, "
                    f"{len(alive)}/{len(snap)} candidates left after dropping the dead family")
                snapshots = snapshots[:len(snapshots) - back + 1]
                snapshots[-1] = (snap_depth, alive)
                best_depth = max(best_depth, depth)  # restart the stall clock from the failure
                beam, depth = alive, snap_depth - 1  # the snapshot is the beam going into snap_depth
                continue
        if depth - best_depth > args.stall:
            log(f"d={depth} stalled: no progress past {len(best_partial.eaten)} dots for {args.stall} moves")
            return solution, best_partial
        if BADLOADS and args.debug:
            for b in BADLOADS[:3]:
                print("BADLOAD sim=%s route=%s expected=%r got=%r retry=%r" % b, flush=True)
            BADLOADS.clear()
        top = beam[0] if beam else None
        if depth % 10 == 0 or solution or not beam:
            log(f"d={depth} jobs={len(jobs)} kids={len(children)} fails={fails} on={by_sim} "
                f"best={len(top.eaten) if top else '-'} fruit={top.fruits if top else '-'} "
                f"t={time.time() - t0:.0f}s")
        keep = ({s for c in beam for s in c.sims} | set(solution.sims if solution else []) | set(sims0)
                | {s for _, snap in snapshots for c in snap for s in c.sims})
        cleanup(keep)
        if solution is not None or not beam:
            return solution, best_partial


def summarize(c, levels, cleared):
    turns = [s for s in c.segs if s["turn"]]
    return dict(levels=levels, cleared=cleared, dots=len(c.eaten), frames=c.frames, fruits=c.fruits,
                route="".join(c.route), n_moves=len(c.route), n_turns=len(turns),
                min_window=min((s["win"] for s in turns), default=99), segs=c.segs, end_sims=c.sims,
                goal_at=len(c.route) - c.after if c.after >= 0 else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--levels", default="1")
    ap.add_argument("--starts", default=None, help="comma list of savestate names to use instead of level jumps")
    ap.add_argument("--beam", type=int, default=96)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--minwin", type=int, default=10)
    ap.add_argument("--need-fruits", type=int, default=0)
    ap.add_argument("--stall", type=int, default=30)
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--cluster-cost", type=float, default=40)
    ap.add_argument("--corner-minwin", type=int, default=5)
    ap.add_argument("--endgame", type=int, default=40, help="plan full cleanups once this few dots are left (0=off)")
    ap.add_argument("--endgame-every", type=int, default=3)
    ap.add_argument("--endgame-cands", type=int, default=12)
    ap.add_argument("--endgame-plans", type=int, default=12)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--prefix", default="", help="opening route to play before searching (e.g. from watch.py)")
    ap.add_argument("--backtracks", type=int, default=20, help="max rewinds on dead ends (0 = old behaviour)")
    ap.add_argument("--snapshots", type=int, default=8, help="beam snapshots kept for backtracking (one per 5 moves)")
    ap.add_argument("--no-late", action="store_true", help="don't test late presses at tight corners")
    ap.add_argument("--jitter-sims", type=int, default=0,
                    help="per level, this many sims that press every turn randomly late (replaces late variants)")
    ap.add_argument("--jitter", type=int, default=8, help="jitter sims: max frames late at junctions")
    ap.add_argument("--jitter-corner", type=int, default=10, help="jitter sims: max frames late at corners")
    ap.add_argument("--fixed-sims", default="",
                    help="comma list K: per level, a sim that presses every turn exactly K frames late")
    ap.add_argument("--history-sims", default="",
                    help="exhaust.py --dump file: per level, a sim replaying each distinct lateness history "
                         "(e.g. every way the opening can end), on time after it")
    ap.add_argument("--turn-cost", type=float, default=0, help="score penalty per turn (a dot is worth 10)")
    ap.add_argument("--late-rel", action="store_true",
                    help="jitter/fixed sims press K frames after the last clean-cornering point (4px before the "
                         "turn) instead of K frames after leaving the previous junction")
    ap.add_argument("--branch", type=int, default=0,
                    help="every turn, each sim splits into presses 0..N frames late (from the last clean-cornering "
                         "point); identical states merge")
    ap.add_argument("--branch-cap", type=int, default=8, help="--branch: max extra sims kept per level")
    ap.add_argument("--leave-pockets", action="store_true",
                    help="goal: every dot except the 4 energizer pockets (maze.POCKETS), never entering them")
    ap.add_argument("--safe-after", type=int, default=3,
                    help="--leave-pockets: moves every sim must survive after the goal is reached")
    ap.add_argument("--checkpoint", default=None,
                    help="write the search state here every 5 moves (default: <out>.ckpt; 'none' = off)")
    ap.add_argument("--resume", action="store_true",
                    help="carry on from --checkpoint (same arguments otherwise; code may have changed)")
    ap.add_argument("--out", default="result.json")
    args = ap.parse_args()
    global CLUSTER_COST, CORNER_MINWIN, LATE_VARIANTS, TURN_COST, JITTER, JITTER_CORNER, LATE_REL, GOAL, AVOID, BRANCH, BRANCH_CAP, SAFE_AFTER
    CLUSTER_COST, CORNER_MINWIN = args.cluster_cost, args.corner_minwin
    LATE_VARIANTS = not args.no_late and not args.jitter_sims and not args.fixed_sims and not args.history_sims
    TURN_COST, JITTER, JITTER_CORNER = args.turn_cost, args.jitter, args.jitter_corner
    LATE_REL = args.late_rel
    BRANCH, BRANCH_CAP = args.branch, args.branch_cap
    if BRANCH:
        LATE_VARIANTS = False
    if args.leave_pockets:
        GOAL, AVOID = maze.DOTS - maze.POCKETS, maze.POCKETS
        SAFE_AFTER = args.safe_after
    levels = [int(x) for x in args.levels.split(",")]
    pool = Pool(args.workers)
    args.checkpoint = None if args.checkpoint == "none" else args.checkpoint or args.out + ".ckpt"
    resume = None
    if args.resume:
        resume = pickle.load(open(args.checkpoint, "rb"))
        HISTORIES.update(resume["histories"])
    sims0 = resume["sims0"] if resume else args.starts.split(",") if args.starts else make_starts(pool, levels)
    fixed = [int(k) for k in args.fixed_sims.split(",") if k]
    sims0 += [] if resume else ([f"{s}~{100 * (j + 1) + k}" for k in range(args.jitter_sims) for j, s in enumerate(sims0)]
              + [f"{s}~f{k}" for k in fixed for s in sims0])
    if args.history_sims and not resume:
        hist = json.load(open(args.history_sims))
        for lv, s in zip(levels, list(sims0[:len(levels)])):
            for j, h in enumerate(hist.get(str(lv), [])):
                if any(h):  # the all-on-time history is the level's own sim
                    HISTORIES[f"h{lv}_{j}"] = h
                    sims0.append(f"{s}~h{lv}_{j}")
    solution, partial = search(pool, sims0, args, log=lambda s: print(s, flush=True), resume=resume)
    out = summarize(solution or partial, levels, solution is not None)
    json.dump(out, open(args.out, "w"), indent=1, default=list)
    print("RESULT cleared=%s dots=%d frames=%d fruits=%d moves=%d turns=%d minwin=%d route=%s" % (
        out["cleared"], out["dots"], out["frames"], out["fruits"], out["n_moves"], out["n_turns"],
        out["min_window"], out["route"]))
    pool.close()
    cleanup(set(), "*")
    if resume and resume["run"] != RUN:  # the savestates the checkpointed run left behind
        for f in (STATE_DIR / "pacman").glob(f"{resume['run']}*.sta"):
            try:
                f.unlink()
            except OSError:
                pass


if __name__ == "__main__":
    main()

