"""Does the first N moves of a route survive on every level under late timing?

  python trunk_check.py result.json --moves 139 --levels 5,6,7
Prints, per level, which fixed lags (every turn exactly k frames late) and how many random-jitter
runs get through the first N moves alive."""
import argparse
import json
import random

import maze
from search import Pool, cleanup, make_starts
from validate import replay


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("result")
    ap.add_argument("--moves", type=int, required=True)
    ap.add_argument("--levels", required=True)
    ap.add_argument("--trials", type=int, default=30)
    ap.add_argument("--fixed-max", type=int, default=12)
    ap.add_argument("--workers", type=int, default=10)
    args = ap.parse_args()
    res = json.load(open(args.result))
    route, n = res["route"][:args.moves], args.moves
    corner = [len(maze.exits(*s["node"])) == 2 and s["turn"] for s in res["segs"][:n]]
    levels = [int(x) for x in args.levels.split(",")]
    pool = Pool(args.workers)
    starts = make_starts(pool, levels)
    jobs = []
    for lv, start in zip(levels, starts):
        for k in range(args.fixed_max + 1):
            jobs.append((lv, f"fixed{k}", pool.submit(replay, start, route, ["E"] * n, [k] * n)))
        for t in range(args.trials):
            rng = random.Random(3000 + t)
            lags = [rng.randint(0, 10) if c else rng.randint(0, 8) for c in corner]
            jobs.append((lv, f"jitter{t}", pool.submit(replay, start, route, ["E"] * n, lags)))
    out = {}
    for lv, name, f in jobs:
        st, i, _ = f.result()
        out.setdefault(lv, {})[name] = "ok" if st in ("unfinished", "clear") else f"{st}@{i}"
    for lv in levels:
        o = out[lv]
        fixed = " ".join(f"{k}:{o[f'fixed{k}']}" for k in range(args.fixed_max + 1))
        jit = [v for k, v in o.items() if k.startswith("jitter")]
        print(f"L{lv}: fixed {fixed} | jitter {jit.count('ok')}/{len(jit)} {sorted(v for v in jit if v != 'ok')}", flush=True)
    pool.close()
    cleanup(set(), "*")


if __name__ == "__main__":
    main()
