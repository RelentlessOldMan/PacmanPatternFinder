"""Replay a route straight through (no savestate branching) under many press timings.

  early     : every press made the moment the previous node is passed
  jitterN   : each press delayed by a random 0..N frames (a human pressing "some time early")
  lateK     : (informational) each press made at a random point in the last few px before the
              turn -- the timing the patterns are designed NOT to rely on
A route is timing-robust when every jitter run plays out frame-identical to the early run.
"""
import argparse
import json
import random

import maze
from search import Pool, make_starts, parse_seg

LATE = ["3", "2", "1", "0", "-1"]


def replay(w, start, route, pols, lags):
    w.cmd(f"load {start} L")
    trace = []
    for i, d in enumerate(route):
        r = parse_seg(w.cmd(f"seg {d} {pols[i]} {lags[i]}"))
        trace.append((r["fr"], r["dots"]))
        if r["st"] == "clear":
            return "clear", i, trace
        if r["st"] != "ok":
            return r["st"], i, trace
    return "unfinished", len(route), trace


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("result")
    ap.add_argument("--levels", default=None)
    ap.add_argument("--trials", type=int, default=30)
    ap.add_argument("--jitter", type=int, default=8)
    ap.add_argument("--corner-lag", type=int, default=10)
    ap.add_argument("--workers", type=int, default=10)
    args = ap.parse_args()
    res = json.load(open(args.result))
    route = res["route"]
    levels = [int(x) for x in args.levels.split(",")] if args.levels else res["levels"]
    pool = Pool(args.workers)
    starts = make_starts(pool, levels)
    n = len(route)
    for lv, start in zip(levels, starts):
        tests = [("early", ["E"] * n, [0] * n)]
        for t in range(args.trials):
            rng = random.Random(1000 + t)
            tests.append((f"jitter{t}", ["E"] * n, [rng.randint(0, args.jitter) for _ in route]))
        corner = [len(maze.exits(*s["node"])) == 2 and s["turn"] for s in res["segs"]]
        for t in range(args.trials):
            rng = random.Random(3000 + t)
            tests.append((f"cornerlate{t}", ["E"] * n,
                          [rng.randint(0, args.corner_lag) if c else rng.randint(0, args.jitter) for c in corner]))
        for t in range(10):
            rng = random.Random(2000 + t)
            tests.append((f"late{t}", [rng.choice(LATE) for _ in route], [0] * n))
        futs = [(name, pool.submit(replay, start, route, p, l)) for name, p, l in tests]
        results = {name: f.result() for name, f in futs}
        base = results["early"]
        jit = [k for k in results if k.startswith("jitter")]
        same = sum(results[k][2] == base[2] for k in jit)
        jit_clear = sum(results[k][0] == "clear" for k in jit)
        cl = [k for k in results if k.startswith("cornerlate")]
        cl_clear = sum(results[k][0] == "clear" for k in cl)
        cl_fails = sorted(results[k][0] + "@" + str(results[k][1]) for k in cl if results[k][0] != "clear")
        late_clear = sum(results[k][0] == "clear" for k in results if k.startswith("late"))
        print(f"L{lv}: early={base[0]}@{base[1]}  jitter 0-{args.jitter}f: {jit_clear}/{len(jit)} cleared, "
              f"{same}/{len(jit)} frame-identical to early  |  late presses: {late_clear}/10 cleared", flush=True)
        print(f"     corners pressed up to {args.corner_lag}f late (Pac-Man pauses): {cl_clear}/{len(cl)} cleared {cl_fails}", flush=True)
    pool.close()


if __name__ == "__main__":
    main()
