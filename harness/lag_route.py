"""lag_route.py <route.json> [level]: where a route spends its frames. Pac-Man's speed depends only on his path
(dots slow him, the tunnel too), so ghosts cost time only through detours (walking tiles already eaten) and waits
(late presses, corner stops). Per move: frames, tiles walked, new dots, tiles walked over already-eaten ground,
and the frames per tile. Also the frame each dot count is reached vs the ghost-free 2337 walk (lag_floor.json)."""
import json, re, sys
import maze
from emu_server import Server
from replay_route import play
from pattern_sheet import walk_emu

src = sys.argv[1]
level = int(sys.argv[2]) if len(sys.argv) > 2 else 21
route = re.findall(r"x\d*|[LRUD]\d*", json.load(open(src))["route"])
tiles, at = walk_emu(route, level)
srv = Server(); srv.handle("newgame"); srv.handle(f"level {level}"); srv.handle("msave s"); srv.handle("mload s L")
ends = []
play(srv, route, lambda i, m, st, fr: ends.append(fr))
floor = json.load(open("lag_floor.json"))  # [(frame, dots eaten)]
floor_at = {}
for f, d in floor:
    floor_at.setdefault(d, f)
eaten, seen, rows = set(), set(), []
prev_at, prev_fr = 0, 1
for i, m in enumerate(route):
    stop = at[i]  # a move's frames run from the last turn to its own turn
    seg = tiles[prev_at + 1:stop + 1]
    new = [t for t in seg if t in maze.DOTS and t not in eaten]
    empty = sum(1 for t in seg if t in seen or t not in maze.DOTS)
    eaten |= set(new); seen |= set(seg)
    fr = ends[i] - prev_fr
    d = len(eaten)
    rows.append((i + 1, m, fr, len(seg), len(new), empty, d, ends[i], ends[i] - floor_at.get(d, 0)))
    prev_at, prev_fr = stop, ends[i]
print("move press frames tiles newdots emptytiles dots frame  behind_floor")
for r in rows:
    print("%4d %-4s %4d %4d %4d %4d %4d %5d %5d" % r)
tail = tiles[at[-1] + 1:]
print("after the last turn:", len(tail), "tiles,", sum(1 for t in tail if t in maze.DOTS and t not in eaten), "new dots")
print("total empty tiles", sum(r[5] for r in rows), "frames", ends[-1])
