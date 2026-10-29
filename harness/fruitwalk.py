"""fruitwalk.py: ghost-free two-fruit floor walks with no side trips (sub-39, 2026-10-29). A milp step set that
enters the fruit tile (floor.py --fruit-visits 2: 295 steps, only 4 over the no-fruit 291) is cheap, but floor.py's
300 random Euler walks never passed it while a fruit was out, so it fell back to side trips (2346). Here many random
Euler walks are timed by a per-step model (frames ~ a*steps + b*dots + c, fitted on pacemu) and only the ones that
pass FRUIT inside both fruit windows (fruit n is out from the 70th / 170th dot for --dur frames; --margin each side)
are played on pacemu. The --keep fastest two-fruit clears are saved (late {} : polish.py starts from them).

    PACMAN_NOGHOSTS=1 python fruitwalk.py <out.json> (--steps-from JSON | --fruit-visits 2 [--time-limit 1800])
        [--tries 1000000] [--jobs 4] [--margin 20] [--keep 40]
The milp steps are saved to <out>.steps.json (reuse with --steps-from)."""
import sys, os, json, argparse, time, random
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import maze, floor, booeywalk as B

G = {}


def timing(walk):
    """dots eaten at each walk index (first visits to dot tiles)."""
    seen, n, out = set(), 0, [0]
    for t in walk[1:]:
        if t in maze.DOTS and t not in seen and t != floor.START:
            seen.add(t); n += 1
        out.append(n)
    return out


def predict(walk, cal):
    a, b, c, dur, m = cal
    d = timing(walk)
    fr = [a * i + b * d[i] + c for i in range(len(walk))]
    ok = []
    for need in (70, 170):
        i0 = next((i for i in range(len(d)) if d[i] >= need), None)
        if i0 is None:
            return False
        w0, w1 = fr[i0] + m, fr[i0] + dur - m
        ok.append(any(w0 <= fr[i] <= w1 for i in range(i0, len(walk)) if walk[i] == floor.FRUIT))
    return all(ok)


def calibrate(A, x, rng, n=8):
    """play n random walks with no fruit check; fit frame = a*index + b*dots + c; fruit durations of uneaten fruits."""
    import numpy as np
    rows, ys, durs = [], [], []
    for _ in range(n):
        w = floor.euler_walk(A, x, rng)
        B.init(w)
        log = []
        B.play({}, hook=lambda f: log.append((f, B.srv.tile(), B.srv.rd(0x4DD2) != 0, B.srv.score())))
        d = timing(w)
        i, last = 0, w[0]
        for f, t, up, sc in log:
            if t != last:
                last = t
                if i + 1 < len(w) and w[i + 1] == t:
                    i += 1; rows.append((i, d[i], 1)); ys.append(f)
        up0 = None
        for k, (f, t, up, sc) in enumerate(log):
            if up and up0 is None: up0 = f
            if not up and up0 is not None:
                if sc - log[k - 1][3] < 5000: durs.append(f - up0)
                up0 = None
    (a, b, c), *_ = np.linalg.lstsq(np.array(rows, float), np.array(ys, float), rcond=None)
    res = np.array(ys) - np.array(rows, float) @ np.array([a, b, c])
    print(f"calibrated on {len(ys)} steps: frame = {a:.3f}*i + {b:.3f}*dots + {c:.1f} (resid sd {res.std():.1f}, "
          f"max {abs(res).max():.1f}); uneaten fruit durations {sorted(durs)}", flush=True)
    return a, b, c, (min(durs) if durs else 560)


def init_worker(A, x, cal, stop):
    B.FRUIT_FAIL = True
    G.update(A=A, x=x, cal=cal, stop=stop)


def job(arg):
    seed, n = arg
    rng = random.Random(seed)
    hits, out = 0, []
    for _ in range(n):
        w = floor.euler_walk(G["A"], G["x"], rng)
        if not predict(w, G["cal"]):
            continue
        hits += 1
        B.init(w)
        r = B.play({}, stop_frame=G["stop"])
        if r[0] == "clear" and r[3] >= 2:
            out.append((r[1], w))
    return hits, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--steps-from"); ap.add_argument("--fruit-visits", type=int, default=2)
    ap.add_argument("--time-limit", type=int, default=1800)
    ap.add_argument("--tries", type=int, default=1000000); ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--chunk", type=int, default=2000); ap.add_argument("--margin", type=int, default=20)
    ap.add_argument("--keep", type=int, default=40); ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--stop", type=int, default=2400, help="stop a play beyond this frame")
    a = ap.parse_args()
    assert os.environ.get("PACMAN_NOGHOSTS"), "set PACMAN_NOGHOSTS=1"
    ts = floor.tiles(); A = floor.arcs(ts)
    if a.steps_from:
        x = floor.walk_arcs([tuple(t) for t in json.load(open(a.steps_from))["walk"]], A)
    else:
        x = floor.solve(ts, A, a.time_limit, a.fruit_visits)
        w = floor.euler_walk(A, x, random.Random(0))
        json.dump({"walk": w, "steps": len(w) - 1}, open(a.out[:-5] + ".steps.json", "w"))
    assert len(floor.euler_walk(A, x, random.Random(0))) == sum(x.values()) + 1, "steps not one connected walk"
    print(f"{sum(x.values())} steps, fruit tile entered {sum(n for j, n in x.items() if A[j][1] == floor.FRUIT)}x", flush=True)
    rng = random.Random(a.seed)
    a_, b_, c_, dur = calibrate(A, x, rng)
    cal = (a_, b_, c_, dur, a.margin)
    t0, done, hits, kept = time.time(), 0, 0, {}
    xs = [(a.seed * 1000003 + i, a.chunk) for i in range(a.tries // a.chunk)]
    with Pool(a.jobs, initializer=init_worker, initargs=(A, x, cal, a.stop)) as pp:
        for h, out in pp.imap_unordered(job, xs):
            done += a.chunk; hits += h
            best = min(kept.values()) if kept else None
            for fr, w in out:
                k = tuple(map(tuple, w))
                if k not in kept:
                    kept[k] = fr
                    if best is None or fr < best:
                        best = fr
                        print(f"  NEW BEST {fr} ({fr / 60.606:.2f}s) at try {done}", flush=True)
            walks = sorted(kept.items(), key=lambda kv: kv[1])[:a.keep]
            if walks:
                json.dump({"level": 21, "frames": walks[0][1], "fruits": 2, "walk": list(walks[0][0]), "late": {},
                           "walks": [dict(frames=fr, walk=list(wk)) for wk, fr in walks]}, open(a.out, "w"))
            print(f"try {done}: {hits} predicted hits, {len(kept)} two-fruit clears, best {best}, "
                  f"{time.time() - t0:.0f}s", flush=True)
    print("done", min(kept.values()) if kept else None)


if __name__ == "__main__":
    main()
