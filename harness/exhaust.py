"""Exhaustive timing check: follow every game state that any lateness pattern can produce.

  python exhaust.py result.json --levels 5,15 --moves 139 --max-lag 10

At every turn, each live state is played with the press 0..max-lag frames late; results that
leave the game in an identical state (same RAM) merge into one. A route passes when no state
in the set dies or misses a turn, which covers every combination of per-turn lateness up to
max-lag, not just sampled ones. Prints the set size per move so you can see if it blows up.
"""
import argparse
import itertools
import json
import threading
import time

from search import RUN, Pool, cleanup, make_starts, parse_seg, stepped_lag

_ids, _lock = itertools.count(), threading.Lock()


def name():
    with _lock:
        return f"{RUN}x{next(_ids)}"


def play(w, state, held, opt, lag):
    w.cmd(f"load {state} {held}")
    r = parse_seg(w.cmd(f"seg {opt} E {stepped_lag(lag) if opt != held else 0}"))
    if r["st"] not in ("ok", "clear"):
        return r["st"], None, None
    n = name()
    w.cmd(f"save {n}")
    return r["st"], w.cmd("hash").split()[1], n


def run_level(pool, start, route, max_lag, cap, log, limits={}):
    states = {start: ()}  # savestate -> one lateness history that reaches it
    held = "L"
    peak = 1
    for i, opt in enumerate(route):
        lags = range(limits.get(i, max_lag) + 1) if opt != held else [0]
        jobs = [(s, hist, lag, pool.submit(play, s, held, opt, lag)) for s, hist in states.items() for lag in lags]
        nxt, seen, fails = {}, set(), {}
        for s, hist, lag, f in jobs:
            st, h, n = f.result()
            if n is None:
                fails.setdefault(st, hist + (lag,))
                continue
            if h in seen:
                cleanup({}, n.removeprefix(RUN))
                continue
            seen.add(h)
            nxt[n] = hist + (lag,)
        cleanup(set(nxt), "x*")
        states, held = nxt, opt
        peak = max(peak, len(states))
        if fails or i % 10 == 0 or opt != route[i - 1:i]:
            log(f"  move {i} {opt}: {len(states)} states" + (f"  FAIL {list(fails)}" if fails else ""))
        if fails:
            st, hist = next(iter(fails.items()))
            turn_lags = [l for l, o, h in zip(hist, route, "L" + route) if o != h]
            return f"{st} at move {i}", peak, turn_lags
        if len(states) > cap:
            return f"too many states ({len(states)}) at move {i}", peak, None
    run_level.ends = list(states.values())
    return "ok", peak, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("result")
    ap.add_argument("--levels", required=True)
    ap.add_argument("--moves", type=int, default=0, help="only the first N moves (default: all)")
    ap.add_argument("--max-lag", type=int, default=10)
    ap.add_argument("--cap", type=int, default=3000, help="give up when the state set grows past this")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--limit", default="", help="per-move max lag overrides, e.g. 5:4 (a corner the player presses early)")
    ap.add_argument("--dump", help="write {level: [lateness history per final state]} here (for search.py --history-sims)")
    args = ap.parse_args()
    route = json.load(open(args.result))["route"]
    route = route[:args.moves] if args.moves else route
    levels = [int(x) for x in args.levels.split(",")]
    pool = Pool(args.workers)
    starts = make_starts(pool, levels)
    ends = {}
    for lv, start in zip(levels, starts):
        t0 = time.time()
        run_level.ends = []
        print(f"L{lv}:", flush=True)
        verdict, peak, example = run_level(pool, start, route, args.max_lag, args.cap,
                                           lambda s: print(s, flush=True),
                                           {int(m): int(k) for m, k in (x.split(":") for x in args.limit.split(",") if x)})
        print(f"L{lv}: {verdict}; peak {peak} states; {time.time() - t0:.0f}s"
              + (f"\n     lateness per turn that fails: {example}" if example else ""), flush=True)
        ends[lv] = run_level.ends
    if args.dump:
        json.dump(ends, open(args.dump, "w"))
    pool.close()
    cleanup(set(), "*")


if __name__ == "__main__":
    main()
