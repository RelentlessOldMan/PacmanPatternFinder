"""Beam search for robust Pac-Man routes, using MAME as the simulator.

A route is the direction taken at each node (junction or corner), never reversing. Presses are
"early": made as soon as the previous node is passed. Measured in MAME, any press made at least
4px before the turn gives an identical game, so the only timing requirement is that each turn's
early-press window (passing previous node -> 4px before turn) is long enough: --minwin frames.

Every candidate move is run from each requested level's start state; a move survives only if
it survives on all of them, which is how one route gets shared across a group of levels.
"""
import argparse
import collections
import itertools
import json
import os
import pickle
import queue
import random
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass

import maze
from worker import MAME, MAME_MEM, Worker, STATE_DIR


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


# Savestates live in the RAM of the worker that made them (our patched MAME, mame-patches/) unless
# --no-ram: OWNER maps a state name to that worker's index. FILED is the states any worker can
# load: the level starts (files), and states whose bytes this process holds in SHARED (fetched with
# mget for a snapshot, the checkpoint or a job another worker took over; handed over with mset).
RAM = False
OWNER = {}
FILED = set()
SHARED = {}  # state name -> its memory slot's bytes
RAM_CAP = 200000  # --ram-cap: past this many memory states, new states go to files (~8 KB each)


def load_state(w, name, held):
    if OWNER.get(name) == w.idx:
        return w.cmd(f"mload {name} {held}")
    if name in OWNER and name not in FILED:
        raise RuntimeError(f"state {name} is only in worker {OWNER[name]}'s memory, not {w.idx}'s")
    if name in SHARED:
        if getattr(w, "shared", None) != name:  # slot "_sh" holds the last shared state it was given
            r = w.cmd(f"mset _sh {SHARED[name].hex()}")
            if r != "ok":
                raise RuntimeError(r)
            w.shared = name
        return w.cmd(f"mload _sh {held}")
    return w.cmd(f"load {name} {held}")


def save_state(w, name):
    if RAM and len(OWNER) < RAM_CAP:
        r = w.cmd(f"msave {name}")
        if r != "ok":
            raise RuntimeError(r)
        OWNER[name] = w.idx
    else:
        w.cmd(f"save {name}")
        FILED.add(name)


def owner_of(sims):
    """The worker whose memory holds (some of) these states, if they aren't all files."""
    owners = {OWNER[base(s)] for s in sims if base(s) in OWNER and base(s) not in FILED}
    assert len(owners) <= 1, owners  # a candidate's sims all come from one job, on one worker
    return owners.pop() if owners else None


COPY_SECONDS = [0.0]  # time spent fetching memory states into SHARED


def write_out(w, names):
    """Fetch the bytes of states held in this worker's memory into SHARED, so any worker can load them."""
    t = time.perf_counter()
    for n in names:
        if n not in FILED and OWNER.get(n) == w.idx:
            r = w.cmd(f"mget {n}")
            if not r.startswith("ok "):
                raise RuntimeError(r)
            SHARED[n] = bytes.fromhex(r[3:])
            FILED.add(n)
    COPY_SECONDS[0] += time.perf_counter() - t


def forget(w, sims, keep=()):
    """Free this worker's memory copies of these sims' states (not those of `keep`)."""
    if RAM:
        ks = {base(s) for s in keep}
        names = [n for n in {base(s) for s in sims} - ks if OWNER.get(n) == w.idx and n not in FILED]
        for n in names:
            del OWNER[n]
        if names:
            drop(w, names)


def drop(w, names):
    for i in range(0, len(names), 200):
        w.cmd("mdrop " + " ".join(names[i:i + 200]))


class Pool:
    """Workers with job affinity: a job that needs states held in one worker's memory (need=) is
    queued for that worker; jobs whose states are all files go to a shared queue that any free
    worker takes from (after its own). place() decides which jobs to move off their worker."""

    def __init__(self, n, mame=MAME, idle=False):
        with ThreadPoolExecutor(n) as ex:
            self.workers = list(ex.map(lambda _: Worker(mame, idle), range(n)))
        for i, w in enumerate(self.workers):
            w.idx = i
        self.n = n
        self.cv = threading.Condition()
        self.own = [collections.deque() for _ in range(n)]
        self.urgent = [collections.deque() for _ in range(n)]
        self.shared = collections.deque()
        self.closed = False
        self.moved = 0
        self.busy = [0.0] * n  # seconds each worker spent running jobs
        self.threads = [threading.Thread(target=self._loop, args=(w,), daemon=True) for w in self.workers]
        for t in self.threads:
            t.start()

    def _put(self, q, fn, args):
        fut = Future()
        with self.cv:
            q.append((fn, args, fut))
            self.cv.notify_all()
        return fut

    def submit(self, fn, *args, need=()):
        k = owner_of(need)
        return self._put(self.shared if k is None else self.own[k], fn, args)

    def on(self, k, fn, *args):
        """Run fn(worker k, *args) on worker k, ahead of its queued jobs."""
        return self._put(self.urgent[k], fn, args)

    def _loop(self, w):
        i = w.idx
        while True:
            with self.cv:
                while not (self.closed or self.urgent[i] or self.own[i] or self.shared):
                    self.cv.wait()
                if self.closed:
                    return
                fn, args, fut = (self.urgent[i] or self.own[i] or self.shared).popleft()
            if fut.set_running_or_notify_cancel():
                t = time.perf_counter()
                try:
                    fut.set_result(fn(w, *args))
                except BaseException as e:
                    fut.set_exception(e)
                self.busy[i] += time.perf_counter() - t

    def close(self):
        with self.cv:
            self.closed = True
            self.cv.notify_all()
        for t in self.threads:
            t.join()
        for w in self.workers:
            w.close()


def place(pool, needs):
    """Before submitting jobs (needs: each job's sims): keep each job with the worker holding its
    states up to an even share of the work (cost ~ number of sims), and write the states of the
    rest to files (each owner its own, in parallel, while the workers are idle) so any worker can
    take them from the shared queue."""
    cost = [len(n) for n in needs]
    cap = sum(cost) / pool.n
    load = [0] * pool.n
    moving = set()
    for i in sorted(range(len(needs)), key=lambda i: -cost[i]):
        k = owner_of(needs[i])
        if k is None:
            continue
        if load[k] == 0 or load[k] + cost[i] <= cap:
            load[k] += cost[i]
        else:
            moving.add(i)
    pool.moved += len(moving)
    write_out_all(pool, {base(s) for i in moving for s in needs[i]})


def write_out_all(pool, names):
    """Make sure these states exist as files (each owner writes its own, in parallel)."""
    by = {}
    for n in names:
        if n in OWNER and n not in FILED:
            by.setdefault(OWNER[n], []).append(n)
    for f in [pool.on(k, write_out, v) for k, v in by.items()]:
        f.result()


def free_ram(pool, keep):
    """Drop the memory copies of states outside `keep`."""
    by = {}
    for n, k in list(OWNER.items()):
        if n not in keep:
            del OWNER[n]
            by.setdefault(k, []).append(n)
    for f in [pool.on(k, drop, v) for k, v in by.items()]:
        f.result()


_ids = itertools.count()
_id_lock = threading.Lock()


# savestates of concurrent runs share STATE_DIR, so every name carries this run's prefix
RUN = f"r{os.getpid()}"


def new_name():
    with _id_lock:
        return f"{RUN}n{next(_ids)}"


def parse_seg(r):
    st, fr, mc, mr, mind, dots, tc, tr, win, fruits, lead, gone = r.split()
    return dict(st=st, fr=int(fr), node=(int(mc), int(mr)), mind=int(mind), dots=int(dots),
                tile=(int(tc), int(tr)), win=int(win), fruits=int(fruits), lead=int(lead), gone=int(gone))


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

    def fail(st, i):  # free the states this move saved
        if out or spawned:
            forget(w, out + spawned)
        return st, i, None
    for i, sim in enumerate(sims):
        late = sim.endswith("*")
        jit = "~" in sim
        name0 = base(sim)
        got = load_state(w, name0, held)
        if expect and got != expect:
            BADLOADS.append((sim, "".join(route), expect, got, load_state(w, name0, held)))
            return fail("badload", i)
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
            return fail(r["st"], i)
        # a late press at a corner only makes Pac-Man pause there; at a junction it sends him the
        # wrong way, so junctions get the full window and corners a shorter one
        corner = len(maze.exits(*r["node"])) == 2
        if not late and not jit and opt != held and r["win"] < (CORNER_MINWIN if corner else minwin):
            return fail("shortwin", i)
        name = new_name()
        save_state(w, name)
        out.append(name + ("*" if late else "") + (sim[sim.index("~"):] if jit else ""))
        res.append(r)
        if not late and not jit and corner and opt != held and r["win"] < minwin and LATE_VARIANTS:
            load_state(w, name0, held)
            rl = parse_seg(w.cmd(f"seg {opt} E {stepped_lag(minwin)}"))
            if rl["st"] not in ("ok", "clear"):
                return fail("late-" + rl["st"], i)
            lname = new_name()
            save_state(w, lname)
            spawned.append(lname + "*")
            res.append(rl)
    return ("clear" if all(r["st"] == "clear" for r in res) else "ok"), out + spawned, res


def run_child_branch(w, sims, held, opt, minwin, route=(), expect=None):
    """--branch N: at a turn, every sim splits into one per press 0..N frames late (counted from the
    last clean-cornering point); children that leave the game in an identical state (RAM hash) merge.
    Each level keeps its on-time sim (the first len(SIMS0) sims, in level order) plus others
    ("name@<level index>.<late presses so far>.<fruits so far>"; the on-time sims carry the same
    suffix). Fruits are counted per sim because variants eat a fruit on different moves: the
    candidate's fruit count is the lowest total over its sims, not a sum of per-move minimums.
    Without --late-budget, at most BRANCH_CAP others per level, a random sample (not exhaustive).
    With --late-budget K, a sim that has used K late presses only plays on time, merges keep the
    fewest late presses, and nothing is sampled: every combination of up to K late presses per
    level is followed exactly. More than BRANCH_CAP others in a level rejects the move ("toomany")."""
    n0 = len(SIMS0)
    main, extra, res, seen = [None] * n0, {}, [], {}
    unused = []  # states segb saved that merged away
    made = []  # states saved for this move, freed again if the move fails

    def fail(st, i):
        if made or unused:
            forget(w, made + unused)
        return st, i, None
    for i, sim in enumerate(sims):
        lv, used, fr = map(int, sim.split("@")[1].split(".")) if "@" in sim else (i, 0, 0)
        lags = range(BRANCH + 1) if opt != held and used < LATE_BUDGET else [0]
        batch = {}
        for k in lags:
            if not batch:  # segb, once run, has played every late press
                got = load_state(w, base(sim), held)
                if expect and got != expect:
                    BADLOADS.append((sim, "".join(route), expect, got, load_state(w, base(sim), held)))
                    return fail("badload", i)
            if k == 1 and RAM and len(OWNER) + BRANCH < RAM_CAP:
                # the late presses share every frame up to the press: one segb plays them
                names = [new_name() for _ in range(BRANCH)]
                for j, line in enumerate(w.cmd(f"segb {opt} 4 " + " ".join(names)).split(" | ")):
                    parts = line.rsplit(" ", 1)
                    batch[j + 1] = (names[j], parts[0], parts[1])
                    OWNER[names[j]] = w.idx
                unused += names
            if k in batch:
                name, line, h = batch[k]
                r = parse_seg(line)
            else:
                name, h = None, None
                r = parse_seg(w.cmd(f"seg {opt} 4 {k}" if k else f"seg {opt} E 0"))
            if r["st"] not in ("ok", "clear"):
                return fail(r["st"], i)
            r["fruits"] += fr  # running total for this sim
            if r["gone"] - r["fruits"] > 2 - NEED_FRUITS:
                return fail("fruitless", i)  # a fruit it needed came and went uneaten
            on_time = i < n0 and k == 0
            if on_time and opt != held:
                corner = len(maze.exits(*r["node"])) == 2
                if r["win"] < (CORNER_MINWIN if corner else minwin):
                    return fail("shortwin", i)
            if h is None:
                h = w.cmd("hash").split()[1]
            late = used + (k > 0)
            key = (lv, h)
            if key in seen and not on_time:
                if seen[key] is not None and late < extra[lv][seen[key]][1]:
                    extra[lv][seen[key]][1] = late
                continue
            if name is None:
                name = new_name()
                save_state(w, name)
            else:
                unused.remove(name)
            made.append(name)
            res.append(r)
            if on_time:
                main[i] = f"{name}@{lv}.0.{r['fruits']}"
                seen[key] = None
            else:
                seen[key] = len(extra.setdefault(lv, []))
                extra[lv].append([name, late, r["fruits"]])
    if unused:
        forget(w, unused)
    if LATE_BUDGET < 10**9:
        if any(len(v) > BRANCH_CAP for v in extra.values()):
            return fail("toomany", 0)
        kept = [f"{n}@{lv}.{late}.{f}" for lv, v in sorted(extra.items()) for n, late, f in v]
    else:
        rng = random.Random("".join(route) + opt)
        kept = [f"{n}@{lv}.0.{f}" for lv, v in sorted(extra.items())
                for n, _, f in (v if len(v) <= BRANCH_CAP else rng.sample(v, BRANCH_CAP))]
    return ("clear" if all(r["st"] == "clear" for r in res) else "ok"), main + kept, res


CLUSTER_COST = 40
CORNER_MINWIN = 8
LATE_VARIANTS = True
TURN_COST = 0.0
JITTER, JITTER_CORNER = 8, 10
HISTORIES = {}  # "h<level>_<j>" -> per-move lateness, from exhaust.py --dump
BRANCH, BRANCH_CAP = 0, 0
LATE_BUDGET = 10**9  # --late-budget: late presses per level that --branch follows exactly
LATE_REL = False  # --late-rel: jitter/fixed sims count lateness from the turn, not the previous junction
GOAL = maze.DOTS  # --leave-pockets: every dot but the energizer pockets, which are never entered
AVOID = frozenset()


NEED_FRUITS = 0  # --need-fruits (of the level's 2): --branch drops a move as soon as one is missed
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
    names = {base(k) for k in keep}
    for n in [n for n in SHARED if n not in names]:
        del SHARED[n]
        FILED.discard(n)
    keep = {f"{n}.sta" for n in names}
    for f in (STATE_DIR / "pacman").glob(f"{RUN}{pattern}.sta"):
        if f.name not in keep:
            try:
                f.unlink()
                FILED.discard(f.stem)
            except OSError:
                pass


def make_starts(pool, levels):
    def mk(w, lv):
        w.cmd("newgame"); w.cmd(f"level {lv}"); w.cmd(f"save {RUN}start_L{lv}")
        return w.cmd("peek")
    for lv in levels:
        print("start", lv, pool.submit(mk, lv).result())
    FILED.update(f"{RUN}start_L{lv}" for lv in levels)
    return [f"{RUN}start_L{lv}" for lv in levels]


def make_child(c, path, opt, sims, res):
    r0 = res[0]
    ch = Cand(c.route + [opt], r0["tile"], opt,
              c.eaten | (frozenset(path) & maze.DOTS) | (frozenset([r0["tile"]]) & maze.DOTS),
              c.frames + max(r["fr"] for r in res),
              c.risk + max(0, 24 - min(r["mind"] for r in res)),
              min(r["fruits"] for r in res) if BRANCH else c.fruits + min(r["fruits"] for r in res), sims,
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

    Returns (clearing child, None) or (None, (status, failing sim index, dots left)). In memory,
    each step's states are freed once the next step is made; only a clearing child's are kept."""
    c0 = c
    for opt in moves:
        node, path = maze.next_node(*c.tile, c.heading)
        st, sims, res = run_child(w, c.sims, c.heading, opt, minwin, c.route,
                                  corner=len(maze.exits(*node)) == 2)
        if c is not c0:
            forget(w, c.sims, keep=sims if res is not None else ())
        if res is None:
            return None, (st, sims, len(GOAL - c.eaten))
        c = make_child(c, path, opt, sims, res)
        if st == "clear" or finished(c):
            return c, None
        if c.after >= 0:  # goal reached: any continuation that every sim survives will do
            s = survive(w, c, minwin)
            if s is not c:
                forget(w, c.sims)
            return (s, None) if s else (None, ("dead-after-goal", None, 0))
    forget(w, c.sims if c is not c0 else ())
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
                k = make_child(c, path, opt, sims, res)
                s = survive(w, k, minwin)
                if s is not k:
                    forget(w, sims, keep=s.sims if s else ())
                if s:
                    return s
    return None


def endgame(pool, beam, args, rng):
    """Try full planned cleanup routes from the best few candidates that have few dots left."""
    cands = [c for c in beam if len(GOAL - c.eaten) <= args.endgame][:args.endgame_cands]
    plans, tried = [], set()
    for c in cands:
        for _ in range(args.endgame_plans):
            mv = plan_moves(c.tile, c.heading, GOAL - c.eaten, rng)
            if mv and (id(c), tuple(mv)) not in tried:
                tried.add((id(c), tuple(mv)))
                plans.append((c, mv))
    if RAM:  # all on the shared queue: rollouts vary a lot in length, so any free worker takes the next
        write_out_all(pool, {base(s) for c, _ in plans for s in c.sims})
    jobs = [pool.submit(rollout, c, mv, args.minwin, need=c.sims) for c, mv in plans]
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
    """Everything the search loop needs to carry on (--resume), written atomically, with the bytes
    of the savestates it refers to (SHARED: the beam and snapshots were just fetched)."""
    state = dict(state, rng=rng.getstate(), sims0=sims0, histories=HISTORIES, run=RUN, shared=SHARED)
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
                                    len(maze.exits(*node)) == 2, need=c.sims).result()
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
    peak_ram = 0
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
            write_out_all(pool, {base(s) for c in beam for s in c.sims})
            if args.checkpoint:
                save_checkpoint(args, sims0, dict(
                    depth=depth, beam=beam, best_partial=best_partial, best_depth=best_depth, solution=solution,
                    snapshots=snapshots, last_beam=last_beam, backtracks=backtracks, misses=misses,
                    last_target=last_target), rng)
        jobs = []
        if RAM:
            place(pool, [c.sims for c in beam for opt in maze.exits(*maze.next_node(*c.tile, c.heading)[0])
                         if allowed(c, maze.next_node(*c.tile, c.heading)[0], opt)])
        for c in beam:
            node, path = maze.next_node(*c.tile, c.heading)
            for opt in maze.exits(*node):
                if allowed(c, node, opt):
                    jobs.append((c, path, opt, pool.submit(run_child, c.sims, c.heading, opt, args.minwin, c.route,
                                                         f"ok {c.tile[0]} {c.tile[1]} {len(c.eaten)}" if c.route else None,
                                                         len(maze.exits(*node)) == 2, need=c.sims)))
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
        peak_ram = max(peak_ram, len(OWNER))
        if RAM:
            free_ram(pool, {base(s) for c in beam + ([solution] if solution else []) for s in c.sims})
        if depth % 10 == 0 or solution or not beam:
            ram = (f" ram={len(OWNER)} states (peak {peak_ram} ~{peak_ram * 0.0077 / 1024:.1f}GB)"
                   f" moved={pool.moved}" if RAM else "")
            log(f"d={depth} jobs={len(jobs)} kids={len(children)} fails={fails} on={by_sim} "
                f"best={len(top.eaten) if top else '-'} fruit={top.fruits if top else '-'} "
                f"t={time.time() - t0:.0f}s{ram} busy={sum(pool.busy) / max(1e-9, (time.time() - t0) * pool.n):.0%}"
                + (f" copy={COPY_SECONDS[0]:.0f}s" if RAM else ""))
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
    ap.add_argument("--branch-cap", type=int, default=8,
                    help="--branch: max extra sims kept per level (with --late-budget: more rejects the move)")
    ap.add_argument("--late-budget", type=int, default=None,
                    help="--branch: follow every combination of up to K late presses per level exactly")
    ap.add_argument("--leave-pockets", action="store_true",
                    help="goal: every dot except the 4 energizer pockets (maze.POCKETS), never entering them")
    ap.add_argument("--safe-after", type=int, default=3,
                    help="--leave-pockets: moves every sim must survive after the goal is reached")
    ap.add_argument("--checkpoint", default=None,
                    help="write the search state here every 5 moves (default: <out>.ckpt; 'none' = off)")
    ap.add_argument("--resume", action="store_true",
                    help="carry on from --checkpoint (same arguments otherwise; code may have changed)")
    ap.add_argument("--ram-cap", type=int, default=200000,
                    help="memory savestates kept at most (~8 KB each, plus MAME itself); more go to files")
    ap.add_argument("--no-ram", action="store_true",
                    help="keep every savestate in a file and use stock MAME (default: states live in the "
                         "memory of the worker that made them, in our patched MAME, mame-0.289-mem/)")
    ap.add_argument("--no-idle-skip", action="store_true",
                    help="with our patched MAME, emulate Pac-Man's idle loop instead of skipping it")
    ap.add_argument("--out", default="result.json")
    args = ap.parse_args()
    global RAM, CLUSTER_COST, CORNER_MINWIN, LATE_VARIANTS, TURN_COST, JITTER, JITTER_CORNER, LATE_REL, GOAL, AVOID, BRANCH, BRANCH_CAP, SAFE_AFTER, LATE_BUDGET, NEED_FRUITS, RAM_CAP
    CLUSTER_COST, CORNER_MINWIN = args.cluster_cost, args.corner_minwin
    LATE_VARIANTS = not args.no_late and not args.jitter_sims and not args.fixed_sims and not args.history_sims
    TURN_COST, JITTER, JITTER_CORNER = args.turn_cost, args.jitter, args.jitter_corner
    LATE_REL = args.late_rel
    BRANCH, BRANCH_CAP = args.branch, args.branch_cap
    NEED_FRUITS = args.need_fruits
    if args.late_budget is not None:
        LATE_BUDGET = args.late_budget
    if BRANCH:
        LATE_VARIANTS = False
    if args.leave_pockets:
        GOAL, AVOID = maze.DOTS - maze.POCKETS, maze.POCKETS
        SAFE_AFTER = args.safe_after
    levels = [int(x) for x in args.levels.split(",")]
    RAM = not args.no_ram
    RAM_CAP = args.ram_cap
    if RAM and not MAME_MEM.exists():
        raise SystemExit(f"{MAME_MEM} not found: build it (see mame-patches/README.md) or use --no-ram")
    pool = Pool(args.workers, MAME_MEM if RAM else MAME, idle=RAM and not args.no_idle_skip)
    args.checkpoint = None if args.checkpoint == "none" else args.checkpoint or args.out + ".ckpt"
    resume = None
    if args.resume:
        resume = pickle.load(open(args.checkpoint, "rb"))
        HISTORIES.update(resume["histories"])
        SHARED.update(resume.get("shared", {}))
        FILED.update(SHARED)
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

