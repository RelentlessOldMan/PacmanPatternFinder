"""tripsets.py: ghost-free two-fruit floor walks from many step sets (sub-39, 2026-10-29). A min-step set has only a
dozen Euler walks (the 291's: 12), so a cheaper fruit timing needs other step sets. Each task solves the floor milp
with small random arc costs (--jitter: a different near-optimal set), takes its distinct Euler walks, and for each
finds the cheapest side trips to FRUIT whose arrival falls inside each fruit window (timing model: frame ~
--a*index + --b*dots; fruit n out from the 70th / 170th dot for --dur frames, --margin each side). The cheapest
--play walks (steps + trips) are played on pacemu; two-fruit clears are kept (late {} : polish.py starts from them).

    PACMAN_NOGHOSTS=1 python tripsets.py <out.json> [--sets 200] [--jobs 10] [--time-limit 300] [--jitter 0.02]
        [--steps-from JSON (task 0 uses these steps, no milp)]"""
import sys, os, json, argparse, time, random
from multiprocessing import Pool
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import maze, floor, booeywalk as B
from fruitwalk import timing

G = {}
EAT = ((13, 17), (14, 17))


def bfs(ts, src):
    dist, q = {src: 0}, [src]
    for u in q:
        for d in maze.DIRS:
            v = maze.step(*u, d)
            if v in ts and v not in dist:
                dist[v] = dist[u] + 1; q.append(v)
    return dist


def options(w, fr, i0, shift, a):
    """(extra steps, k) for a trip leaving w[k] that reaches FRUIT inside the window opened at index i0."""
    m = G["a"].margin
    lo, hi = fr[i0] + m, fr[i0] + G["a"].dur - m
    out = []
    for k in range(i0, len(w) - 1):  # a trip before the 70th / 170th dot would delay the fruit too
        t = far(w[k]); D = G["dist"][t]
        arr = fr[k] + a * D[w[k]]
        if arr > hi: break
        if arr >= lo:
            out.append((D[w[k]] + D[w[k + 1]] - 1, k, t))
    return sorted(out)[:6]


def far(u):
    """the fruit is eaten crossing between EAT tiles (13,17)-(14,17): a trip goes to the far one of the pair."""
    d = G["dist"]
    return EAT[1] if d[EAT[0]][u] < d[EAT[1]][u] else EAT[0]


def with_trip(w, k, t):
    p1, p2 = floor.path_to(w[k], t, G["ts"]), floor.path_to(t, w[k + 1], G["ts"])
    return w[:k + 1] + p1[1:] + p2[1:] + w[k + 2:]


def candidates(x, rng, n=600):
    a, b = G["a"].a, G["a"].b
    walks = {tuple(floor.euler_walk(G["A"], x, rng)) for _ in range(n)}
    cands = []
    for w in walks:
        w = list(w); d = timing(w)
        fr = [a * i + b * d[i] for i in range(len(w))]
        i70 = next(i for i in range(len(d)) if d[i] >= 70); i170 = next(i for i in range(len(d)) if d[i] >= 170)
        for e1, k1, t1 in options(w, fr, i70, 0, a):
            fr2 = fr[:k1 + 1] + [f + a * e1 for f in fr[k1 + 1:]]
            for e2, k2, t2 in options(w, fr2, i170, 0, a):
                if k2 > k1:
                    cands.append((e1 + e2, (k1, t1), (k2, t2), w))
    cands.sort(key=lambda c: c[0])
    return len(walks), cands


def init_worker(a, A, ts, dist):
    B.FRUIT_FAIL = True
    G.update(a=a, A=A, ts=ts, dist=dist)


def task(seed):
    a = G["a"]
    rng = random.Random(seed)
    t0 = time.time()
    if seed == 0 and a.steps_from:
        x = floor.walk_arcs([tuple(t) for t in json.load(open(a.steps_from))["walk"]], G["A"])
    else:
        jit = np.array([rng.random() * a.jitter for _ in G["A"]])
        import io, contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            x = floor.solve(G["ts"], G["A"], a.time_limit, jitter=jit)
    steps = sum(x.values())
    nw, cands = candidates(x, rng)
    out, tried = [], set()
    for extra, k1, k2, w in cands:
        if len(tried) >= a.play: break
        key = (tuple(w), k1, k2)
        if key in tried: continue
        tried.add(key)
        tw = with_trip(with_trip(w, *k2), *k1)
        B.init(tw)
        r = B.play({}, stop_frame=a.stop)
        out.append((extra, r[0], r[1], r[3], tw))
    return seed, steps, nw, (cands[0][0] if cands else None), time.time() - t0, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--sets", type=int, default=200); ap.add_argument("--jobs", type=int, default=10)
    ap.add_argument("--time-limit", type=int, default=300); ap.add_argument("--jitter", type=float, default=0.02)
    ap.add_argument("--steps-from"); ap.add_argument("--play", type=int, default=8)
    ap.add_argument("--a", type=float, default=5.6); ap.add_argument("--b", type=float, default=1.75)
    ap.add_argument("--dur", type=int, default=541); ap.add_argument("--margin", type=int, default=25)
    ap.add_argument("--stop", type=int, default=2400); ap.add_argument("--keep", type=int, default=40)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    assert os.environ.get("PACMAN_NOGHOSTS"), "set PACMAN_NOGHOSTS=1"
    ts = floor.tiles(); A = floor.arcs(ts); dist = {t: bfs(ts, t) for t in EAT}
    seeds = ([0] if a.steps_from else []) + [a.seed * 100000 + i for i in range(1, a.sets + 1)]
    kept, t0 = {}, time.time()
    with Pool(a.jobs, initializer=init_worker, initargs=(a, A, ts, dist)) as pp:
        for seed, steps, nw, ex, secs, out in pp.imap_unordered(task, seeds):
            clears = [(fr, ex_, tw) for ex_, st, fr, fruits, tw in out if st == "clear" and fruits >= 2]
            best = min(kept.values()) if kept else None
            for fr, ex_, tw in clears:
                k = tuple(map(tuple, tw))
                if k not in kept:
                    kept[k] = fr
                    if best is None or fr < best:
                        best = fr
                        print(f"  NEW BEST {fr} ({fr / 60.606:.2f}s): set {seed}, {steps}+{ex_} steps", flush=True)
            print(f"set {seed}: {steps} steps, {nw} walks, cheapest trips +{ex}, played {len(out)} -> "
                  f"{sorted(fr for fr, _, _ in clears)[:3]} ({secs:.0f}s); best {best}, {time.time() - t0:.0f}s", flush=True)
            walks = sorted(kept.items(), key=lambda kv: kv[1])[:a.keep]
            if walks:
                json.dump({"level": 21, "frames": walks[0][1], "fruits": 2, "walk": list(walks[0][0]), "late": {},
                           "walks": [dict(frames=fr, walk=list(wk)) for wk, fr in walks]}, open(a.out, "w"))
    print("done", min(kept.values()) if kept else None)


if __name__ == "__main__":
    main()
