"""Turn a watched human game (watch.lua log) into a route and check it like a search result.

  python watch.py watch/play_X.log                     # print the route taken on the logged level
  python watch.py watch/play_X.log --check 5,7,10,13   # replay it on those levels: deaths, tight
                                                       # windows, and every turn exactly k frames late
The route is the direction Pac-Man leaves every junction/corner with, in search.py's format, so it
can be fed to the search as a starting prefix.
"""
import argparse
import re

import maze
from search import Pool, cleanup, make_starts, parse_seg

LINE = re.compile(r"f=(\d+) L=(\d+) t=(-?\d+),(-?\d+) d=(\d) dots=(\d+) lives=(\d+)")
NAME = "RDLU"


def games(path):
    """Split the log into games: lists of (tile, dir, dots), each ending at a death or level change."""
    out, cur = [], None
    for line in open(path):
        m = LINE.match(line)
        if m:
            f, lv, c, r, d, dots, lives = map(int, m.groups())
            if cur and dots < cur["steps"][-1][2]:
                cur = None  # dots went down: a new game (e.g. the attract demo, then a real game)
            if cur is None:
                if (c, r) != (13, 23) or dots != 0:
                    continue  # boot garbage / demo mid-play
                cur = dict(level=lv, steps=[], end="unfinished")
                out.append(cur)
            cur["steps"].append(((c, r), NAME[d], dots))
        elif cur and (line.startswith("DEATH") or line.startswith("LEVEL")):
            cur["end"] = line.split()[0].lower() + " " + line.split("f=")[1].split(" ", 1)[-1].strip()
            cur = None
    return out


def route_of(steps):
    """Direction Pac-Man leaves each node with: the last dir logged while on that node's tile."""
    blocks = []  # (tile, final dir) per stay on a tile
    for tile, d, _ in steps:
        if blocks and blocks[-1][0] == tile:
            blocks[-1][1] = d
        else:
            blocks.append([tile, d])
    route = []
    for i, (tile, d) in enumerate(blocks[:-1]):  # the last tile's exit isn't known yet
        if tile == (13, 23) and i == 0:
            continue  # start tile: search.py starts here heading L, the first node comes after
        if maze.is_node(*tile):
            route.append(d)
    return "".join(route)


def check(w, start, route, minwin, lag, corner_minwin=5):
    w.cmd(f"load {start} L")
    held, tile, warn = "L", (13, 23), []
    for i, d in enumerate(route):
        node, _ = maze.next_node(*tile, held)
        corner = len(maze.exits(*node)) == 2
        r = parse_seg(w.cmd(f"seg {d} E {lag if d != held else 0}"))
        if r["st"] not in ("ok", "clear"):
            return r["st"], i, r["dots"], warn
        if d != held and r["win"] < (corner_minwin if corner else minwin):
            warn.append(f"{i}:{d}@{node[0]},{node[1]} win={r['win']}")
        held, tile = d, r["tile"]
        if r["st"] == "clear":
            return "clear", i, r["dots"], warn
    return "ok", len(route), r["dots"], warn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("--game", type=int, default=-1, help="which game in the log (default: the longest)")
    ap.add_argument("--check", default="", help="levels to replay the route on")
    ap.add_argument("--minwin", type=int, default=10)
    ap.add_argument("--fixed-max", type=int, default=10)
    ap.add_argument("--workers", type=int, default=10)
    args = ap.parse_args()
    gs = games(args.log)
    for i, g in enumerate(gs):
        print(f"game {i}: L{g['level']} {len(g['steps'])} steps, {g['steps'][-1][2]} dots, {g['end']}")
    g = gs[args.game] if args.game >= 0 else max(gs, key=lambda g: g["steps"][-1][2])
    route = route_of(g["steps"])
    print(f"route ({len(route)} moves, {sum(a != b for a, b in zip('L' + route, route))} turns): {route}")
    if not args.check:
        return
    levels = [int(x) for x in args.check.split(",")]
    pool = Pool(args.workers)
    starts = make_starts(pool, levels)
    futs = {(lv, k): pool.submit(check, s, route, args.minwin, k)
            for lv, s in zip(levels, starts) for k in range(args.fixed_max + 1)}
    for lv in levels:
        st, i, dots, warn = futs[(lv, 0)].result()
        print(f"L{lv}: on time: {st} after {i}/{len(route)} moves, {dots} dots; tight turns: {warn or 'none'}")
        late = []
        for k in range(1, args.fixed_max + 1):
            st, i, dots, _ = futs[(lv, k)].result()
            late.append(f"{k}:" + ("ok" if st in ("ok", "clear") else f"{st}@{i}"))
        print(f"     every turn k frames late: {' '.join(late)}")
    pool.close()
    cleanup(set(), "*")


if __name__ == "__main__":
    main()
