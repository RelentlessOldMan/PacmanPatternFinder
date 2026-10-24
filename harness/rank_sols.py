"""Rank clearing routes from search.py --solutions (<out>.sols.jsonl).

1. Replay each route on time on every level in --levels; keep the ones that live on all of them
   (and never let a fruit go uneaten once one should have been eaten: the first fruit).
2. For those, follow every mix of up to --budget late presses (1-4 frames after the clean-cornering
   point, like search.py --branch 4) on --late-level, and count the mixes that kill Pac-Man (or let
   the first fruit go) and the moves they die on.

    python rank_sols.py result_ontime_L7.json.sols.jsonl --levels 5-20 --late-level 7 --budget 2
"""
import argparse
import collections
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import search
from search import parse_seg
from worker import MAME_MEM, Worker

LOCAL = threading.local()
LEVELS = []
GAME = "emu"  # pacemu (emu/); --mame: our patched MAME
NEED_FRUITS = 1  # --need-fruits


def worker():
    """This thread's game (pacemu or MAME), with a start state in memory for each level. They are all made up front:
    a second newgame after playing leaves the game in a bad state (Pac-Man stuck or dead at once)."""
    if not hasattr(LOCAL, "w"):
        LOCAL.w = w = Worker(GAME, idle=True)
        for lv in LEVELS:
            w.cmd("newgame"); w.cmd(f"level {lv}"); w.cmd(f"msave start{lv}")
    return LOCAL.w


def bad(r, eaten):
    """Pac-Man died, or the first fruit went uneaten (gone counts this level's fruits eaten or
    expired; eaten is the running total of seg's per-move fruits). The second may expire unless
    --need-fruits 2."""
    return (r["st"] not in ("ok", "clear") or (r["gone"] and not eaten)
            or r["gone"] - eaten > 2 - NEED_FRUITS)


def on_time(route, lv):
    """None if the route lives through level lv played on time, else the move it fails on."""
    w = worker()
    w.cmd(f"mload start{lv} L")
    eaten = 0
    for i, d in enumerate(route):
        r = parse_seg(w.cmd(f"seg {d} E 0"))
        eaten += r["fruits"]
        if bad(r, eaten):
            return i + 1
    return len(route) if eaten < NEED_FRUITS else None  # a fruit still out when the route ends


def late_mixes(route, lv, budget):
    """Every mix of up to `budget` late presses: the killing mixes as (move died on, ((move, k), ...))."""
    w = worker()
    w.cmd(f"mload start{lv} L"); w.cmd("msave r0")
    states, n, held, deaths = {"": ("r0", (), 0)}, 0, "L", []
    for i, d in enumerate(route):
        nxt, replaced = {}, []

        def keep(name, r, h, mix, eaten0):
            """True if the state saved as `name` is kept for the next move."""
            eaten = eaten0 + r["fruits"]
            if bad(r, eaten):
                deaths.append((i + 1, mix))
                return False
            if h in nxt:
                if len(nxt[h][1]) <= len(mix):
                    return False
                replaced.append(nxt[h][0])
            nxt[h] = (name, mix, eaten)
            return True

        for slot, lates, eaten0 in states.values():
            w.cmd(f"mload {slot} {held}")
            r = parse_seg(w.cmd(f"seg {d} E 0"))
            n += 1
            if keep(f"r{n}", r, w.cmd("hash").split()[1], lates, eaten0):
                w.cmd(f"msave r{n}")
            if d != held and len(lates) < budget:
                # the late presses (1-4 frames) share every frame up to the press: one segb plays them
                w.cmd(f"mload {slot} {held}")
                names = [f"r{n + k}" for k in range(1, 5)]
                n += 4
                lines = w.cmd(f"segb {d} 4 " + " ".join(names)).split(" | ")
                drop = [name for k, (name, line) in enumerate(zip(names, lines), 1)
                        if not keep(name, parse_seg(line.rsplit(" ", 1)[0]), line.split()[-1],
                                    lates + ((i + 1, k),), eaten0)]
                if drop:
                    w.cmd("mdrop " + " ".join(drop))
        for slot in [v[0] for v in states.values()] + replaced:
            w.cmd(f"mdrop {slot}")
        states, held = nxt, d
    return deaths


def levels_arg(s):
    out = []
    for part in s.split(","):
        a, _, b = part.partition("-")
        out += range(int(a), int(b or a) + 1)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sols")
    ap.add_argument("--levels", default="5-20")
    ap.add_argument("--late-levels", default=None, help="levels to try late presses on (default: --levels)")
    ap.add_argument("--budget", type=int, default=2)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--out", default=None, help="default: <sols> with .ranked.json")
    ap.add_argument("--mame", action="store_true", help="run the game in our patched MAME instead of pacemu")
    ap.add_argument("--need-fruits", type=int, default=1, help="fruits (of 2) each level must eat")
    ap.add_argument("--all-ghosts", action="store_true", help="a late press that loses a ghost (of 4 per energizer) kills too")
    args = ap.parse_args()
    search.ALL_GHOSTS = args.all_ghosts
    global GAME, NEED_FRUITS
    NEED_FRUITS = args.need_fruits
    if args.mame:
        GAME = MAME_MEM
    sols = [json.loads(l) for l in open(args.sols)]
    levels = levels_arg(args.levels)
    late_levels = levels_arg(args.late_levels) if args.late_levels else levels
    LEVELS[:] = sorted(set(levels) | set(late_levels))
    with ThreadPoolExecutor(args.workers) as ex:
        fails = list(ex.map(lambda rl: on_time(*rl), [(s["route"], lv) for s in sols for lv in levels]))
        good = []
        for j, s in enumerate(sols):
            f = {lv: m for lv, m in zip(levels, fails[j * len(levels):(j + 1) * len(levels)]) if m}
            if f:
                print(f"#{j + 1} {s['n_moves']} moves: fails on time on " +
                      ", ".join(f"L{lv} move {m}" for lv, m in f.items()), flush=True)
            else:
                good.append(s)
        print(f"{len(good)}/{len(sols)} live on time on every level {args.levels}", flush=True)
        jobs = [(s["route"], lv) for s in good for lv in late_levels]
        # longest routes first so the pool doesn't end waiting on one
        order = sorted(range(len(jobs)), key=lambda i: -len(jobs[i][0]))
        done = iter(range(1, len(jobs) + 1))  # next() on a shared iterator is atomic under the GIL

        def run(i):
            ds = late_mixes(*jobs[i], args.budget)
            print(f"late presses: {next(done)}/{len(jobs)} route-levels done", flush=True)
            return ds
        out = dict(zip(order, ex.map(run, order)))
    rows = []
    for j, s in enumerate(good):
        ds = [(lv, m, mix) for k, lv in enumerate(late_levels) for m, mix in out[j * len(late_levels) + k]]
        by_move = collections.Counter(m for _, m, _ in ds)
        by_level = collections.Counter(lv for lv, _, _ in ds)
        one = [(lv, m, mix) for lv, m, mix in ds if len(mix) == 1]
        rows.append(dict(s, killers=len(ds), killers1=len(one), weak_moves=sorted(by_move),
                         deaths_by_move=dict(by_move), deaths_by_level=dict(by_level),
                         single_killers=[[lv, m, list(map(list, mix))] for lv, m, mix in one],
                         killer_mixes=[[lv, m, list(map(list, mix))] for lv, m, mix in ds]))
    rows.sort(key=lambda r: (r["killers1"], r["killers"], r["n_moves"]))
    json.dump(rows, open(args.out or args.sols.replace(".jsonl", ".ranked.json"), "w"), indent=1)
    print(f"\nUp to {args.budget} late presses, on levels {args.late_levels or args.levels} (killer mixes summed):")
    for r in rows:
        worst = ", ".join(f"L{lv}:{n}" for lv, n in sorted(r["deaths_by_level"].items(), key=lambda kv: -kv[1])[:3])
        print(f"{r['killers1']:3d} single late presses kill, {r['killers']:5d} mixes in all, "
              f"{len(r['weak_moves']):2d} moves die (worst {worst or '-'})  "
              f"{r['n_moves']} moves {r['n_turns']} turns  {r['route'][40:]}", flush=True)


if __name__ == "__main__":
    main()
