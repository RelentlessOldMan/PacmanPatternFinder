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


def solve(ts, A, time_limit=1800):
    """Fewest steps from START visiting every dot, ending anywhere. Returns {arc index: count}.
    Connected by flow: START sends one unit to every dot, only along steps the walk takes."""
    T = sorted(ts)
    nt, na = len(T), len(A)
    idx = {t: i for i, t in enumerate(T)}
    nd = sum(1 for t in T if t in maze.DOTS and t != START)
    # variables: x[a] (steps along arc a), f[a] (flow along a), e[t] (the walk ends on t)
    X, F, E = 0, na, 2 * na
    n = 2 * na + nt
    cost = np.zeros(n); cost[X:X + na] = 1
    M = lil_matrix((2 * nt + 1 + na, n)); lo, hi = [], []
    k = 0
    for t in T:  # steps: out - in + end = [t is START]
        M[k, E + idx[t]] = 1
        v = 1 if t == START else 0; lo.append(v); hi.append(v); k += 1
    for t in T:  # flow: in - out = 1 on every dot (START: -nd)
        v = -nd if t == START else (1 if t in maze.DOTS else 0); lo.append(v); hi.append(v); k += 1
    for j, (a, b, _) in enumerate(A):
        M[idx[a], X + j] += 1; M[idx[b], X + j] -= 1
        M[nt + idx[b], F + j] += 1; M[nt + idx[a], F + j] -= 1
    M[k, E:E + nt] = 1; lo.append(1); hi.append(1); k += 1
    for j in range(na):  # flow only where Pac-Man steps
        M[k, F + j] = 1; M[k, X + j] = -nd; lo.append(-np.inf); hi.append(0); k += 1
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


def drive(srv, walk, need_fruits=0):
    """Play a tile walk from the level start; joystick always toward the next tile. Returns (frames, fruits) or None."""
    srv.handle("mload s L")
    k, frames, fruits = 0, 1, 0  # 1: the frame the start state's load runs (like search.py)
    score = srv.score() if hasattr(srv, "score") else None
    while srv.dots() < 244:
        t = srv.tile()
        while k + 1 < len(walk) and t == walk[k + 1]:
            k += 1
        if t != walk[k]:
            return None
        if k + 1 < len(walk):
            srv.joy(press(walk, k, HEADING[srv.rd(0x4D30)]))
        srv.wait(1); frames += 1
        if frames > 6000 or srv.rd(0x4DA5):
            return None
    return frames


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", type=int, default=21)
    ap.add_argument("--tries", type=int, default=300)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default="result_floor.json")
    args = ap.parse_args()
    assert os.environ.get("PACMAN_NOGHOSTS"), "set PACMAN_NOGHOSTS=1"
    from emu_server import Server
    ts = tiles()
    A = arcs(ts)
    x = solve(ts, A)
    srv = Server()
    srv.handle("newgame"); srv.handle(f"level {args.level}"); srv.handle("msave s")
    rng = random.Random(args.seed)
    best = None
    for i in range(args.tries):
        w = euler_walk(A, x, rng)
        f = drive(srv, w)
        if f and (best is None or f < best[0]):
            best = (f, w)
            print(f"try {i}: {f} frames ({f / 60.606:.2f}s)", flush=True)
    f, w = best
    json.dump({"level": args.level, "frames": f, "steps": len(w) - 1, "walk": w}, open(args.out, "w"))
    print(f"BEST {f} frames {f / 60.606:.2f}s steps={len(w) - 1}")


if __name__ == "__main__":
    main()
