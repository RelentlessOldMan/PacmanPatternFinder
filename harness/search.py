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


def new_name():
    with _id_lock:
        return f"n{next(_ids)}"


def parse_seg(r):
    st, fr, mc, mr, mind, dots, tc, tr, win, fruits, lead = r.split()
    return dict(st=st, fr=int(fr), node=(int(mc), int(mr)), mind=int(mind), dots=int(dots),
                tile=(int(tc), int(tr)), win=int(win), fruits=int(fruits), lead=int(lead))


BADLOADS = []


def run_child(w, sims, held, opt, minwin, route=(), expect=None):
    """Run one move on every sim; stop at the first failure.

    A sim name ending in "*" is a "late player" variant: it presses every corner turn `minwin`
    frames after passing the previous node, so at a tight corner Pac-Man pauses against the wall
    first. When an on-time sim takes a corner whose window is shorter than `minwin`, a late variant
    is spawned from it; from then on the route has to survive both.
    """
    out, res, spawned = [], [], []
    for sim in sims:
        late = sim.endswith("*")
        name0 = sim.rstrip("*")
        got = w.cmd(f"load {name0} {held}")
        if expect and got != expect:
            BADLOADS.append((sim, "".join(route), expect, got, w.cmd(f"load {name0} {held}")))
            return "badload", None, None
        r = parse_seg(w.cmd(f"seg {opt} E {minwin if late and opt != held else 0}"))
        if r["st"] not in ("ok", "clear"):
            if r["st"] == "stuck":
                print(f"STUCK route={''.join(route)}+{opt} {r}", flush=True)
            return r["st"], None, None
        # a late press at a corner only makes Pac-Man pause there; at a junction it sends him the
        # wrong way, so junctions get the full window and corners a shorter one
        corner = len(maze.exits(*r["node"])) == 2
        if not late and opt != held and r["win"] < (CORNER_MINWIN if corner else minwin):
            return "shortwin", None, None
        name = new_name()
        w.cmd(f"save {name}")
        out.append(name + ("*" if late else ""))
        res.append(r)
        if not late and corner and opt != held and r["win"] < minwin and LATE_VARIANTS:
            w.cmd(f"load {name0} {held}")
            rl = parse_seg(w.cmd(f"seg {opt} E {minwin}"))
            if rl["st"] not in ("ok", "clear"):
                return "late-" + rl["st"], None, None
            lname = new_name()
            w.cmd(f"save {lname}")
            spawned.append(lname + "*")
            res.append(rl)
    return ("clear" if all(r["st"] == "clear" for r in res) else "ok"), out + spawned, res


CLUSTER_COST = 40
CORNER_MINWIN = 8
LATE_VARIANTS = True


def score(c):
    left = maze.DOTS - c.eaten
    near = maze.bfs_dist(c.tile, left)
    # each stranded pocket of dots costs a long trip back later (with a faster red ghost)
    return (len(c.eaten) * 10 - c.frames * 0.25 - near * 6 - c.risk * 2 + c.fruits * 400
            - maze.clusters(left) * CLUSTER_COST)


def cleanup(keep):
    keep = {f"{k.rstrip('*')}.sta" for k in keep}
    for f in (STATE_DIR / "pacman").glob("n*.sta"):
        if f.name not in keep:
            try:
                f.unlink()
            except OSError:
                pass


def make_starts(pool, levels):
    def mk(w, lv):
        w.cmd("newgame"); w.cmd(f"level {lv}"); w.cmd(f"save start_L{lv}")
        return w.cmd("peek")
    for lv in levels:
        print("start", lv, pool.submit(mk, lv).result())
    return [f"start_L{lv}" for lv in levels]


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
    ch.score = score(ch)
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
                if opt == maze.REV[h]:
                    continue
                nt = maze.step(*node, opt)
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
    """Play a whole planned move list from candidate c on all its sims; return the clearing child."""
    for opt in moves:
        node, path = maze.next_node(*c.tile, c.heading)
        st, sims, res = run_child(w, c.sims, c.heading, opt, minwin)
        if sims is None:
            return None
        c = make_child(c, path, opt, sims, res)
        if st == "clear":
            return c
    return None


def endgame(pool, beam, args, rng):
    """Try full planned cleanup routes from the best few candidates that have few dots left."""
    cands = [c for c in beam if len(maze.DOTS - c.eaten) <= args.endgame][:args.endgame_cands]
    jobs, tried = [], set()
    for c in cands:
        for _ in range(args.endgame_plans):
            mv = plan_moves(c.tile, c.heading, maze.DOTS - c.eaten, rng)
            if mv and (id(c), tuple(mv)) not in tried:
                tried.add((id(c), tuple(mv)))
                jobs.append(pool.submit(rollout, c, mv, args.minwin))
    sols = [s for s in (j.result() for j in jobs) if s is not None and s.fruits >= args.need_fruits]
    return min(sols, key=lambda s: s.frames) if sols else None, len(jobs)


def search(pool, sims0, args, log=print):
    t0 = time.time()
    n = len(sims0)
    beam = [Cand([], (13, 23), "L", frozenset(), 0, 0.0, 0, sims0, [])]
    best_partial, best_depth, solution = beam[0], 0, None
    rng = random.Random(args.seed)
    for depth in itertools.count():
        jobs = []
        for c in beam:
            node, path = maze.next_node(*c.tile, c.heading)
            for opt in maze.exits(*node):
                if opt != maze.REV[c.heading]:
                    jobs.append((c, path, opt, pool.submit(run_child, c.sims, c.heading, opt, args.minwin, c.route,
                                                         f"ok {c.tile[0]} {c.tile[1]} {len(c.eaten)}" if c.route else None)))
        children, fails = {}, {}
        for c, path, opt, fut in jobs:
            st, sims, res = fut.result()
            if sims is None:
                fails[st] = fails.get(st, 0) + 1
                continue
            ch = make_child(c, path, opt, sims, res)
            r0 = res[0]
            if r0["dots"] != len(ch.eaten) and args.debug:
                print(f"DOTMISMATCH game={r0['dots']} mine={len(ch.eaten)} route={''.join(ch.route)}", flush=True)
            if st == "clear":
                if ch.fruits < args.need_fruits:
                    fails["nofruit"] = fails.get("nofruit", 0) + 1
                elif solution is None or ch.frames < solution.frames:
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
            sol, njobs = endgame(pool, beam, args, rng)
            if njobs:
                log(f"d={depth} endgame: {njobs} planned cleanups tried -> {'CLEARED' if sol else 'none cleared'}")
            if sol:
                solution = sol
        if beam and len(beam[0].eaten) > len(best_partial.eaten):
            best_partial, best_depth = beam[0], depth
        if depth - best_depth > args.stall:
            log(f"d={depth} stalled: no progress past {len(best_partial.eaten)} dots for {args.stall} moves")
            return solution, best_partial
        if BADLOADS and args.debug:
            for b in BADLOADS[:3]:
                print("BADLOAD sim=%s route=%s expected=%r got=%r retry=%r" % b, flush=True)
            BADLOADS.clear()
        top = beam[0] if beam else None
        if depth % 10 == 0 or solution or not beam:
            log(f"d={depth} jobs={len(jobs)} kids={len(children)} fails={fails} "
                f"best={len(top.eaten) if top else '-'} fruit={top.fruits if top else '-'} "
                f"t={time.time() - t0:.0f}s")
        keep = {s for c in beam for s in c.sims} | set(solution.sims if solution else []) | set(sims0)
        cleanup(keep)
        if solution is not None or not beam:
            return solution, best_partial


def summarize(c, levels, cleared):
    turns = [s for s in c.segs if s["turn"]]
    return dict(levels=levels, cleared=cleared, dots=len(c.eaten), frames=c.frames, fruits=c.fruits,
                route="".join(c.route), n_moves=len(c.route), n_turns=len(turns),
                min_window=min((s["win"] for s in turns), default=99), segs=c.segs, end_sims=c.sims)


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
    ap.add_argument("--no-late", action="store_true", help="don't test late presses at tight corners")
    ap.add_argument("--out", default="result.json")
    args = ap.parse_args()
    global CLUSTER_COST, CORNER_MINWIN, LATE_VARIANTS
    CLUSTER_COST, CORNER_MINWIN, LATE_VARIANTS = args.cluster_cost, args.corner_minwin, not args.no_late
    levels = [int(x) for x in args.levels.split(",")]
    pool = Pool(args.workers)
    sims0 = args.starts.split(",") if args.starts else make_starts(pool, levels)
    solution, partial = search(pool, sims0, args, log=lambda s: print(s, flush=True))
    out = summarize(solution or partial, levels, solution is not None)
    json.dump(out, open(args.out, "w"), indent=1, default=list)
    print("RESULT cleared=%s dots=%d frames=%d fruits=%d moves=%d turns=%d minwin=%d route=%s" % (
        out["cleared"], out["dots"], out["frames"], out["fruits"], out["n_moves"], out["n_turns"],
        out["min_window"], out["route"]))
    pool.close()


if __name__ == "__main__":
    main()

