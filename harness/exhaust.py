"""Exhaustive timing check: follow every game state that any lateness pattern can produce.

  python exhaust.py result.json --levels 5,15 --moves 139 --max-lag 10

With --rel, "k frames late" means k frames after the last press that still corners cleanly (Pac-Man
4px before the turn); without it (the old meaning), k frames after leaving the previous junction,
which for most moves is still ahead of the turn.

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


REL = False  # --rel: lag k = k frames after the last clean-cornering point (4px before the turn)


def play(w, state, held, opt, lag):
    w.cmd(f"load {state} {held}")
    if REL and lag:
        r = parse_seg(w.cmd(f"seg {opt} 4 {lag}"))
    else:
        r = parse_seg(w.cmd(f"seg {opt} E {stepped_lag(lag) if opt != held else 0}"))
    if r["st"] not in ("ok", "clear"):
        return r["st"], None, None
    n = name()
    w.cmd(f"save {n}")
    return r["st"], w.cmd("hash").split()[1], n


def nlate(hist):
    return sum(1 for l in hist if l)


def run_level(pool, start, route, max_lag, cap, log, limits={}, keep_going=False, max_late=10**9):
    """With keep_going, dead states are dropped instead of ending the check, and each death is
    reported with the fewest late presses that reach it (states keep their least-late history).
    max_late: at most this many late presses per level, anywhere. Still exact: of two histories
    that reach the same game state, the one with fewer late presses is kept, and it can absorb
    every slip the other could."""
    states = {start: ()}  # savestate -> the lateness history with the fewest late presses that reaches it
    deaths = []
    held = "L"
    peak = 1
    for i, opt in enumerate(route):
        lags = range(limits.get(i, max_lag) + 1) if opt != held else [0]
        jobs = [(s, hist, lag, pool.submit(play, s, held, opt, lag)) for s, hist in states.items()
                for lag in (lags if nlate(hist) < max_late else [0])]
        nxt, seen, fails = {}, {}, {}
        for s, hist, lag, f in jobs:
            st, h, n = f.result()
            hist = hist + (lag,)
            if n is None:
                if st not in fails or nlate(hist) < nlate(fails[st]):
                    fails[st] = hist
                continue
            if h in seen:
                cleanup({}, n.removeprefix(RUN))
                if nlate(hist) < nlate(nxt[seen[h]]):
                    nxt[seen[h]] = hist
                continue
            seen[h] = n
            nxt[n] = hist
        cleanup(set(nxt), "x*")
        states, held = nxt, opt
        peak = max(peak, len(states))
        if fails or i % 10 == 0 or opt != route[i - 1:i]:
            log(f"  move {i} {opt}: {len(states)} states" + (f"  FAIL {list(fails)}" if fails else ""))
        if fails:
            st, hist = min(fails.items(), key=lambda kv: nlate(kv[1]))
            late = {m: l for m, l in enumerate(hist) if l}
            if not keep_going:
                return f"{st} at move {i}", peak, late
            deaths.append((i, st, late))
            log(f"    fewest late presses that die here: {len(late)}  {late}")
            if not states:
                return f"every state dead at move {i}", peak, late
        if len(states) > cap:
            return f"too many states ({len(states)}) at move {i}", peak, None
    run_level.ends = list(states.values())
    if deaths:
        i, st, late = min(deaths, key=lambda d: len(d[2]))
        return (f"{len(states)} states survive; deaths at moves {[d[0] for d in deaths]}; fewest late "
                f"presses that kill it: {len(late)} (move {i})"), peak, late
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
    ap.add_argument("--max-late", type=int, default=10**9,
                    help="at most this many late presses per level (each 1..max-lag frames), anywhere")
    ap.add_argument("--keep-going", action="store_true",
                    help="drop dead states and carry on; report each death with its fewest late presses")
    ap.add_argument("--rel", action="store_true",
                    help="count lateness from the turn (frames after the last clean-cornering press), not from "
                         "leaving the previous junction")
    args = ap.parse_args()
    global REL
    REL = args.rel
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
                                           {int(m): int(k) for m, k in (x.split(":") for x in args.limit.split(",") if x)},
                                           args.keep_going, args.max_late)
        print(f"L{lv}: {verdict}; peak {peak} states; {time.time() - t0:.0f}s"
              + (f"\n     late presses (move: frames) that fail: {example}" if example else ""), flush=True)
        ends[lv] = run_level.ends
    if args.dump:
        json.dump(ends, open(args.dump, "w"))
    pool.close()
    cleanup(set(), "*")


if __name__ == "__main__":
    main()
