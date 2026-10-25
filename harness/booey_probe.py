"""booey_probe.py [walks] [level]: how often can a press timing tweak turn a death into a booey?

Random walks from the level start (random move at each node, never reversing, early presses) until Pac-Man
dies. Then the move before the deadly one is redone with a late press (seg "4 k": k frames after Pac-Man is
within 4 px of the node; at a corner he waits at the wall) for k = 1..12, and the deadly move run again.
A rescue whose closest ghost is < 6 px went through the ghost (a booey); otherwise the delay dodged it.
Also reports which way the killing ghost was heading (0x4D2C.. ghost headings, like 0x4D30 for Pac-Man)."""
import random, sys
import maze
from emu_server import Server
from search import parse_seg

walks = int(sys.argv[1]) if len(sys.argv) > 1 else 100
level = int(sys.argv[2]) if len(sys.argv) > 2 else 21
srv = Server()
srv.handle("newgame"); srv.handle(f"level {level}"); srv.handle("msave start")
GHOST_DIR = [0x4D2C, 0x4D2D, 0x4D2E, 0x4D2F]  # Blinky, Pinky, Inky, Clyde: 0 R, 1 D, 2 L, 3 U


def killer():
    """(ghost, its heading, Pac-Man's heading) for the ghost on Pac-Man's tile."""
    pc, pr = srv.tile()
    for g in range(4):
        gr, gc = srv.rd(0x4D31 + 2 * g) - 33, 59 - srv.rd(0x4D32 + 2 * g)  # ghost tile (like 0x4D39/3A for Pac-Man)
        if (gc, gr) == (pc, pr):
            return g, "RDLU"[srv.rd(GHOST_DIR[g]) & 3], "RDLU"[srv.rd(0x4D30) & 3]
    return None


stats = dict(deaths=0, headon=0, rescued=0, booey=0)
for w in range(walks):
    rng = random.Random(w)
    srv.handle("mload start L")
    tile, heading, hist = (13, 23), "L", []
    for i in range(200):
        node, _ = maze.next_node(*tile, heading)
        opt = rng.choice([d for d in maze.exits(*node) if d != maze.REV[heading]])
        srv.handle(f"msave m{i}")
        hist.append((heading, opt))
        r = parse_seg(srv.handle(f"seg {opt} E 0"))
        if r["st"] == "dead":
            break
        if r["st"] != "ok":
            hist = None
            break
        tile, heading = r["tile"], opt
    if not hist or r["st"] != "dead" or i == 0:
        continue
    k_info = killer()
    stats["deaths"] += 1
    head_on = bool(k_info) and k_info[1] == maze.REV[k_info[2]]
    stats["headon"] += head_on
    (h0, prev), (h1, opt) = hist[-2], hist[-1]
    ok = []
    for k in range(1, 13):
        srv.handle(f"mload m{i - 1} {h0}")
        a = parse_seg(srv.handle(f"seg {prev} 4 {k}"))
        if a["st"] != "ok":
            break  # missed the turn: later presses miss too
        b = parse_seg(srv.handle(f"seg {opt} E 0"))
        if b["st"] in ("ok", "clear"):
            ok.append((k, b["mind"]))
    stats["rescued"] += bool(ok)
    stats["booey"] += any(md < 6 for _, md in ok)
    print(f"walk {w} move {i + 1}: killed by {k_info} ({'head-on' if head_on else 'other'}); "
          f"late {prev} rescues (k, mind): {ok}", flush=True)
print(stats)
