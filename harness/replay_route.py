"""replay_route.py <route.json|route> <level>: play a route on pacemu exactly on time and print its frames
(ready to clear) and the outcome. Routes may hold "x" / "x<i>" moves (search.py --reverse / --reverse-any:
turn back mid-corridor) and late presses like "R4" (search.py --booey)."""
import json, sys
import maze
from emu_server import Server
from search import parse_seg, rev_spots, tokens


def play(srv, route, on_move=None):
    """Play route from the level start; returns (status, moves played, frames)."""
    tile, heading, eaten, frames = (13, 23), "L", set(), 1  # the start state's load runs a frame
    route = tokens(route)
    for i, m in enumerate(route):
        if m[0] == "x":
            spot, walked = {mv: (sp, wk) for mv, sp, wk in rev_spots(tile, heading, eaten, True)}[m]
            f0 = int(srv.handle("peek").split()[1][2:])
            p = srv.handle(f"reverse {maze.REV[heading]} {spot[0]} {spot[1]}").split()
            if p[0] != "ok":
                return p[0], i + 1, frames
            frames += int(p[1][2:]) - f0
            eaten |= set(walked) & maze.DOTS
            tile, heading = tuple(map(int, p[2][5:].split(","))), maze.REV[heading]
            st = "clear" if int(p[3][5:]) >= 244 else "ok"
        else:
            node, path = maze.next_node(*tile, heading)
            # "R4" (search.py --booey): R pressed 4 frames late
            r = parse_seg(srv.handle(f"seg {m[0]} 4 {m[1:]}" if len(m) > 1 else f"seg {m} E 0"))
            frames += r["fr"]
            eaten |= (set(path) | {r["tile"]}) & maze.DOTS
            tile, heading, st = r["tile"], m[0], r["st"]
        if on_move:
            on_move(i, m, st, frames)
        if st != "ok":
            return st, i + 1, frames
    return st, len(route), frames


if __name__ == "__main__":
    a = sys.argv[1]
    route = json.load(open(a))["route"] if a.endswith(".json") else a
    srv = Server()
    srv.handle("newgame"); srv.handle(f"level {sys.argv[2]}")
    srv.handle("msave s"); srv.handle("mload s L")
    st, n, fr = play(srv, route)
    print(st, f"{n}/{len(tokens(route))} moves", fr, "frames", f"{fr / 60.606:.2f}s")
