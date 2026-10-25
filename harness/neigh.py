"""neigh.py <route.json> [out.txt]: the one-move neighbors of a route, as --prefix strings: for each move i, the
route's first i moves then one alternative: another way at that node, a turn-back ("x", "x<i>"), or a turn
pressed 2/4/6/8 frames late (the search only tries late presses to rescue a death). One per line: i alt prefix."""
import json, random, sys
import maze
from emu_server import Server
from search import parse_seg, rev_spots, tokens

route = tokens(json.load(open(sys.argv[1]))["route"])
srv = Server()
srv.handle("newgame"); srv.handle("level 21"); srv.handle("msave s"); srv.handle("mload s L")
tile, heading, eaten, out = (13, 23), "L", set(), []
for i, m in enumerate(route):
    alts = set()
    revs = {mv: (sp, wk) for mv, sp, wk in rev_spots(tile, heading, eaten, True)}
    alts |= set(revs)
    node, path = maze.next_node(*tile, heading)
    for d in maze.exits(*node):
        if d != maze.REV[heading]:
            alts.add(d)
            if d != heading:
                alts |= {d + str(k) for k in (2, 4, 6, 8)}
    alts.discard(m)
    out += [(i, a, "".join(route[:i]) + a) for a in sorted(alts)]
    if m[0] == "x":
        spot, walked = revs[m]
        p = srv.handle(f"reverse {maze.REV[heading]} {spot[0]} {spot[1]}").split()
        eaten |= set(walked) & maze.DOTS
        tile, heading = tuple(map(int, p[2][5:].split(","))), maze.REV[heading]
    else:
        r = parse_seg(srv.handle(f"seg {m[0]} 4 {m[1:]}" if len(m) > 1 else f"seg {m} E 0"))
        eaten |= (set(path) | {r["tile"]}) & maze.DOTS
        tile, heading = r["tile"], m[0]
random.Random(1).shuffle(out)
with open(sys.argv[2] if len(sys.argv) > 2 else "neigh.txt", "w") as f:
    for i, a, p in out:
        f.write(f"{i} {a} {p}\n")
print(len(out), "neighbors")
