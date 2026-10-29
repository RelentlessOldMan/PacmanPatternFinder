"""floor.py: the fastest possible level clear with no ghosts (PACMAN_NOGHOSTS=1, see emu_server.py).

With no ghosts, a dot tile costs ~8 frames and an empty tile ~7 whatever the route, so the fastest clear is
(nearly) the fewest tile steps that visit every dot: an integer program on the tile graph (scipy milp),
with connectivity cuts added until the steps form one walk from the start. Pac-Man may turn back on any
tile. Many walks use those steps (Euler paths); each is driven frame by frame on pacemu (the joystick
always points at the next tile, so corners are cut as early as possible) and the fastest is kept.

    PACMAN_NOGHOSTS=1 python floor.py [--level 21] [--tries 300] [--out result_floor.json]
"""
import argparse, json, os, random, sys
from collections import defaultdict
import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds
from scipy.sparse import lil_matrix
import maze

START = (13, 23)


def tiles():
    out = set()
    for r in range(maze.H):
        for c in (range(-2, 30) if r == maze.TUNNEL_ROW else range(maze.W)):
            if maze.is_open(c, r):
                out.add((c, r))
    return out


def arcs(ts):
    return [(t, maze.step(*t, d), d) for t in sorted(ts) for d in maze.DIRS if maze.step(*t, d) in ts]


def solve(ts, A, time_limit=1800, fruit_visits=0, avoid=(), jitter=None):
    """Fewest steps from START visiting every dot, ending anywhere. Returns {arc index: count}.
    Connected by flow: START sends one unit to every dot, only along steps the walk takes.
    avoid: arc sets of earlier walks; each must be left at least once (a step on an arc outside it).
    jitter: extra cost per arc (small, for a different near-optimal step set)."""
    T = sorted(ts)
    nt, na = len(T), len(A)
    idx = {t: i for i, t in enumerate(T)}
    nd = sum(1 for t in T if t in maze.DOTS and t != START)
    fv = 1 if fruit_visits and FRUIT not in maze.DOTS else 0  # FRUIT gets flow too: its visits must join the walk
    nd += fv
    # variables: x[a] (steps along arc a), f[a] (flow along a), e[t] (the walk ends on t)
    X, F, E = 0, na, 2 * na
    n = 2 * na + nt
    cost = np.zeros(n); cost[X:X + na] = 1
    if jitter is not None: cost[X:X + na] += jitter
    M = lil_matrix((2 * nt + 2 + na + len(avoid), n)); lo, hi = [], []
    k = 0
    for t in T:  # steps: out - in + end = [t is START]
        M[k, E + idx[t]] = 1
        v = 1 if t == START else 0; lo.append(v); hi.append(v); k += 1
    for t in T:  # flow: in - out = 1 on every dot (START: -nd); FRUIT entered fruit_visits times as well
        if t == FRUIT and fruit_visits:
            for j, (a, b, _) in enumerate(A):
                if b == FRUIT: M[2 * nt + 1 + na, X + j] = 1
        v = -nd if t == START else (1 if t in maze.DOTS or (fv and t == FRUIT) else 0); lo.append(v); hi.append(v); k += 1
    for j, (a, b, _) in enumerate(A):
        M[idx[a], X + j] += 1; M[idx[b], X + j] -= 1
        M[nt + idx[b], F + j] += 1; M[nt + idx[a], F + j] -= 1
    M[k, E:E + nt] = 1; lo.append(1); hi.append(1); k += 1
    for j in range(na):  # flow only where Pac-Man steps
        M[k, F + j] = 1; M[k, X + j] = -nd; lo.append(-np.inf); hi.append(0); k += 1
    lo.append(fruit_visits); hi.append(np.inf); k += 1
    for S in avoid:
        for j in range(na):
            if j not in S:
                M[k, X + j] = 1
        lo.append(1); hi.append(np.inf); k += 1
    ub = np.concatenate([np.full(na, 4), np.full(na, nd), np.ones(nt)])
    integ = np.concatenate([np.ones(na), np.zeros(na), np.ones(nt)])
    res = milp(cost, constraints=LinearConstraint(M.tocsr(), lo, hi), integrality=integ,
               bounds=Bounds(np.zeros(n), ub), options={"disp": True, "time_limit": time_limit})
    assert res.x is not None, res.message
    x = {j: int(round(v)) for j, v in enumerate(res.x[:na]) if round(v) > 0}
    print(f"milp: {sum(x.values())} steps ({res.message}; bound {getattr(res, 'mip_dual_bound', None)})", flush=True)
    return x


def euler_walk(A, x, rng):
    """A random Euler path from START over the chosen steps (Hierholzer). Returns the tile list."""
    out = defaultdict(list)
    for j, n in x.items():
        out[A[j][0]] += [A[j][1]] * n
    for v in out.values():
        rng.shuffle(v)
    st, walk = [START], []
    while st:
        u = st[-1]
        if out[u]:
            st.append(out[u].pop())
        else:
            walk.append(st.pop())
    return walk[::-1]


def dir_of(a, b):
    return next(d for d in maze.DIRS if maze.step(*a, d) == b)


HEADING = "RDLU"  # 0x4D30


def press(walk, k, heading=None):
    """The joystick on walk[k]: the next change of direction, as early as it can't turn Pac-Man too soon
    (like seg's "E" policy); a turn-back only on its own tile."""
    cur = dir_of(walk[k], walk[k + 1])
    if heading is not None and heading != cur:
        return cur  # this tile's own turn first
    j = k + 1
    while j + 1 < len(walk) and dir_of(walk[j], walk[j + 1]) == cur:
        j += 1
    if j + 1 >= len(walk):
        return cur
    d2 = dir_of(walk[j], walk[j + 1])
    if d2 == maze.REV[cur]:
        return cur
    if any(maze.is_open(*maze.step(*walk[i], d2)) for i in range(k, j)):
        return cur
    return d2


FRUIT = (13, 17)  # where both fruits sit (RAM 0x4DD2/3 = 148,128); out while 0x4DD4 != 0


def score(srv):
    b = lambda v: (v >> 4) * 10 + (v & 15)
    return b(srv.rd(0x4E80)) + b(srv.rd(0x4E81)) * 100 + b(srv.rd(0x4E82)) * 10000


def drive(srv, walk):
    """Play a tile walk from the level start (joystick: see press). Returns None if Pac-Man leaves the walk,
    else dict(frames, fruits, at=[frame each walk index is reached], windows=[[first, last frame a fruit is out]])."""
    srv.handle("mload s L")
    k, frames, fruits = 0, 1, 0  # 1: the frame the start state's load runs (like search.py)
    at, windows, last, out = [1], [], score(srv), False
    while srv.dots() < 244:
        t = srv.tile()
        while k + 1 < len(walk) and t == walk[k + 1]:
            k += 1; at.append(frames)
        if t != walk[k]:
            return None
        if k + 1 < len(walk):
            srv.joy(press(walk, k, HEADING[srv.rd(0x4D30)]))
        srv.wait(1); frames += 1
        if frames > 6000 or srv.rd(0x4DA5):
            return None
        sc = score(srv)
        if sc - last in (100, 300, 500, 700, 1000, 2000, 3000, 5000):
            fruits += 1
        last = sc
        now = srv.rd(0x4DD4) != 0
        if now and not out:
            windows.append([frames, None])
        if out and not now:
            windows[-1][1] = frames - 1
        out = now
    return dict(frames=frames, fruits=fruits, at=at, windows=windows)


def path_to(a, b, ts):
    """Shortest tile path a..b (BFS, tunnel included)."""
    prev, q = {a: None}, [a]
    for u in q:
        if u == b:
            break
        for d in maze.DIRS:
            v = maze.step(*u, d)
            if v in ts and v not in prev:
                prev[v] = u; q.append(v)
    p = [b]
    while prev[p[-1]] is not None:
        p.append(prev[p[-1]])
    return p[::-1]


def add_fruit(srv, walk, info, n, ts, tries=10):
    """Insert a side trip to FRUIT while fruit n (0, 1) is out: leave the walk at index k, go to FRUIT, rejoin
    at k+1. Tries the cheapest few (by steps) whose arrival fits the window; returns the best (frames, walk, info)."""
    if n >= len(info["windows"]):
        return None
    w0, w1 = info["windows"][n]
    w1 = w1 or 10 ** 9
    cands = []
    for k in range(len(walk) - 1):
        if not (w0 <= info["at"][k] <= w1) if k < len(info["at"]) else True:
            continue
        p1, p2 = path_to(walk[k], FRUIT, ts), path_to(FRUIT, walk[k + 1], ts)
        if info["at"][k] + 8 * (len(p1) - 1) > w1:
            continue
        cands.append((len(p1) + len(p2) - 2, k, p1, p2))
    best = None
    for extra, k, p1, p2 in sorted(cands)[:tries]:
        w = walk[:k + 1] + p1[1:] + p2[1:] + walk[k + 2:]
        r = drive(srv, w)
        if r and r["fruits"] > n and (best is None or r["frames"] < best[0]):
            best = (r["frames"], w, r)
    return best


def avoid_sets(files, A):
    """--avoid: the arc set of every walk saved in each file."""
    out = []
    for f in files:
        r = json.load(open(f))
        for w in [r["walk"]] + [k["walk"] for k in r.get("walks", [])]:
            out.append(set(walk_arcs([tuple(t) for t in w], A)))
    return out


def walk_arcs(walk, A):
    """The step counts (like solve's result) of a saved walk."""
    j = {(a, b): i for i, (a, b, _) in enumerate(A)}
    x = defaultdict(int)
    for a, b in zip(walk, walk[1:]):
        x[j[(a, b)]] += 1
    return dict(x)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", type=int, default=21)
    ap.add_argument("--tries", type=int, default=300)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--fruits", type=int, default=0, help="2: also eat both fruits (side trips added)")
    ap.add_argument("--fruit-visits", type=int, default=0, help="the milp walk enters the fruit tile this often")
    ap.add_argument("--time-limit", type=int, default=1800, help="milp seconds")
    ap.add_argument("--steps-from", metavar="JSON", help="reuse the steps of a saved floor result (skip the milp)")
    ap.add_argument("--avoid", nargs="*", default=[], metavar="JSON",
                    help="milp: use a step outside each of these saved walks (all their \"walks\") for new step sets")
    ap.add_argument("--keep", type=int, default=1, help="also save the N fastest distinct walks (\"walks\")")
    ap.add_argument("--out", default="result_floor.json")
    args = ap.parse_args()
    assert os.environ.get("PACMAN_NOGHOSTS"), "set PACMAN_NOGHOSTS=1"
    from emu_server import Server
    ts = tiles()
    A = arcs(ts)
    x = walk_arcs([tuple(t) for t in json.load(open(args.steps_from))["walk"]], A) if args.steps_from else solve(ts, A, args.time_limit, args.fruit_visits, avoid_sets(args.avoid, A))
    srv = Server()
    srv.handle("newgame"); srv.handle(f"level {args.level}"); srv.handle("msave s")
    rng = random.Random(args.seed)
    best, kept = None, {}
    for i in range(args.tries):
        w = euler_walk(A, x, rng)
        r = drive(srv, w)
        if not r:
            continue
        for n in range(args.fruits):
            if r["fruits"] > n:
                continue
            got = add_fruit(srv, w, r, n, ts)
            if not got:
                r = None
                break
            _, w, r = got
        if r and r["fruits"] >= args.fruits:
            kept[tuple(map(tuple, w))] = r["frames"]
        if r and r["fruits"] >= args.fruits and (best is None or r["frames"] < best[0]):
            best = (r["frames"], w, r)
            print(f"try {i}: {r['frames']} frames ({r['frames'] / 60.606:.2f}s) steps={len(w) - 1} "
                  f"fruits={r['fruits']} windows={r['windows']}", flush=True)
    f, w, r = best
    walks = sorted(kept.items(), key=lambda kv: kv[1])[:args.keep]
    json.dump({"level": args.level, "frames": f, "steps": len(w) - 1, "fruits": r["fruits"], "walk": w,
               "walks": [dict(frames=fr, walk=list(wk)) for wk, fr in walks]}, open(args.out, "w"))
    print(f"kept {len(walks)} walks: {[fr for _, fr in walks]}")
    print(f"BEST {f} frames {f / 60.606:.2f}s steps={len(w) - 1} fruits={r['fruits']}")


if __name__ == "__main__":
    main()
