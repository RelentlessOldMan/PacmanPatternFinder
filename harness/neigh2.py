"""neigh2.py <route.json> [out.txt] [ks] [from] [span]: two-move neighbors of a route, as --prefix strings: two of its
turns (moves i < j, j within the next `span` turns after i, i >= `from`) both pressed late (k1, k2 in ks), the moves
between them as they were. The search then re-searches after j. One per line: i alt prefix (like neigh.py)."""
import json, random, sys
import maze
from search import tokens

route = tokens(json.load(open(sys.argv[1]))["route"])
KS = [int(k) for k in (sys.argv[3] if len(sys.argv) > 3 else "2,8").split(",")]
FROM = int(sys.argv[4]) if len(sys.argv) > 4 else 50
SPAN = int(sys.argv[5]) if len(sys.argv) > 5 else 6
heading, turns = "L", []
for i, m in enumerate(route):
    if m[0] == "x":
        heading = maze.REV[heading]
        continue
    if len(m) == 1 and m != heading and i >= FROM:
        turns.append(i)
    heading = m[0]
out = []
for a, i in enumerate(turns):
    for j in turns[a + 1:a + 1 + SPAN]:
        for k1 in KS:
            for k2 in KS:
                p = route[:i] + [route[i] + str(k1)] + route[i + 1:j] + [route[j] + str(k2)]
                out.append((i, f"{route[i]}{k1}_{j}{route[j]}{k2}", "".join(p)))
random.Random(1).shuffle(out)
with open(sys.argv[2] if len(sys.argv) > 2 else "neigh2.txt", "w") as f:
    for i, a, p in out:
        f.write(f"{i} {a} {p}\n")
print(len(out), "pair neighbors")
