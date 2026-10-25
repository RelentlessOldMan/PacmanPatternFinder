"""pattern_sheet.py <route.json> <out.png> <title> [screenshot.png] [--level N]: draw a route as one image to learn it from.

The route is split into legs, one maze panel each: the leg's path in colour with every move numbered
where it's taken, on the dots still left when the leg starts. The maze is drawn from maze.txt (no game
graphics), or with a screenshot, on that: a 3x MAME frame (672x864) of the level's start, its eaten dots
blacked out.

A route with turn-backs ("x", "x3") or late presses ("R9") is walked on pacemu (replay_route.play, level N,
default 21), since where a turn-back happens depends on the dots eaten and where each move leaves Pac-Man."""
import json, re, sys, os
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import maze

T = 20                      # pixels per tile
PW, PH = maze.W * T, maze.H * T
MY = 0                      # where the maze starts in a panel (a screenshot has the score above it)
LW = 4                      # path line width
PAD, HEAD, LEGHEAD, FOOT = 24, 96, 56, 60
BG, WALL, WALL_EDGE, DOT = (12, 12, 20), (24, 34, 92), (70, 90, 200), (235, 205, 170)
COLOURS = [(255, 70, 70), (70, 210, 90), (80, 150, 255), (255, 150, 60), (230, 220, 70), (60, 220, 220), (220, 100, 230)]
FONT = "C:/Windows/Fonts/arial.ttf"
BOLD = "C:/Windows/Fonts/arialbd.ttf"


def walk(route):
    """Tiles Pac-Man covers, and the index into them where each move is taken."""
    cur, h = (13, 23), "L"
    tiles, at = [cur], []
    for m in route + "!":
        while True:
            cur = maze.step(*cur, h)
            tiles.append(cur)
            if maze.is_node(*cur):
                break
        if m == "!":
            break
        assert maze.is_open(*maze.step(*cur, m)), (len(at), cur, m)
        at.append(len(tiles) - 1)
        h = m
    return tiles, at


def walk_emu(route, level):
    """walk() for routes with turn-backs or late presses: plays it on pacemu (replay_route.play) and records,
    for each move, the corridor lookup it made (where the move is taken) and the tile it left Pac-Man on."""
    import replay_route
    from emu_server import Server
    srv = Server()
    srv.handle("newgame"); srv.handle(f"level {level}"); srv.handle("msave s"); srv.handle("mload s L")
    orig_rev, orig_next = replay_route.rev_spots, maze.next_node
    buf, moves = [], []

    def rev_spots(tile, heading, eaten, any_dot=False):
        out = orig_rev(tile, heading, eaten, any_dot)
        buf.append(("x", tile, heading, {mv: sp for mv, sp, wk in out}))
        return out

    def next_node(c, r, h):
        out = orig_next(c, r, h)
        buf.append(("n", (c, r), h, out[0]))
        return out

    def on_move(i, m, st, fr):
        g = dict(kv.split("=", 1) for kv in srv.handle("peek").split() if "=" in kv)
        ev = next(e for e in reversed(buf) if e[0] == ("x" if m[0] == "x" else "n"))
        moves.append((m, ev, tuple(map(int, g["tile"].split(",")))))
        buf.clear()
    replay_route.rev_spots, maze.next_node = rev_spots, next_node
    try:
        st, n, fr = replay_route.play(srv, route, on_move)
    finally:
        replay_route.rev_spots, maze.next_node = orig_rev, orig_next
    assert st in ("ok", "clear"), (st, n)
    tiles, at = [(13, 23)], []

    def go(to, h):  # step from the last tile to `to` heading h
        for _ in range(40):
            if tiles[-1] == to:
                return
            tiles.append(maze.step(*tiles[-1], h))
        tiles.append(to)
    for m, (kind, tile, h, info), end in moves:
        go(tile, h)
        go(info[m] if kind == "x" else info, h)  # the turn-back spot, or the node the move is taken at
        at.append(len(tiles) - 1)
        go(end, maze.REV[h] if kind == "x" else m[0])
    return tiles, at


def legs(n, k):
    size = -(-n // k)
    return [(i, min(i + size, n)) for i in range(0, n, size)]


def centre(t, ox, oy):
    # tunnel tiles past the maze's sides are drawn at the panel's edge
    return ox + min(max(t[0] * T + T // 2, 0), PW), oy + t[1] * T + T // 2


def draw_maze(d, ox, oy, dots):
    for r in range(maze.H):
        for c in range(maze.W):
            if maze.ROWS[r][c] == "#":
                d.rectangle([ox + c * T, oy + r * T, ox + c * T + T - 1, oy + r * T + T - 1], fill=WALL)
    for r in range(maze.H):  # an edge where wall meets corridor
        for c in range(maze.W):
            if maze.ROWS[r][c] != "#":
                continue
            x, y = ox + c * T, oy + r * T
            if r > 0 and maze.ROWS[r - 1][c] != "#": d.line([x, y, x + T - 1, y], fill=WALL_EDGE, width=2)
            if r < maze.H - 1 and maze.ROWS[r + 1][c] != "#": d.line([x, y + T - 1, x + T - 1, y + T - 1], fill=WALL_EDGE, width=2)
            if c > 0 and maze.ROWS[r][c - 1] != "#": d.line([x, y, x, y + T - 1], fill=WALL_EDGE, width=2)
            if c < maze.W - 1 and maze.ROWS[r][c + 1] != "#": d.line([x + T - 1, y, x + T - 1, y + T - 1], fill=WALL_EDGE, width=2)
    for t in dots:
        x, y = centre(t, ox, oy)
        rad = 6 if t in maze.ENERGIZERS else 2
        d.ellipse([x - rad, y - rad, x + rad, y + rad], fill=DOT)


def draw_leg(d, ox, oy, path, col, numbers, small, first):
    # a corridor walked twice in one leg is drawn as two side-by-side lines
    passes = {}
    pts = []
    for a, b in zip(path, path[1:]):
        if abs(a[0] - b[0]) > 1:  # through the tunnel
            if len(pts) > 1: d.line(pts, fill=col, width=LW, joint="curve")
            pts = []
            continue
        key = frozenset((a, b))
        k = passes.get(key, 0); passes[key] = k + 1
        off = (k * 6) - (3 if k else 0)
        dx, dy = b[0] - a[0], b[1] - a[1]
        px, py = -dy * off, dx * off
        (x1, y1), (x2, y2) = centre(a, ox, oy), centre(b, ox, oy)
        if not pts: pts.append((x1 + px, y1 + py))
        pts.append((x2 + px, y2 + py))
    if len(pts) > 1: d.line(pts, fill=col, width=LW, joint="curve")
    # where the leg starts and the way it ends
    if first:
        sx, sy = centre(path[0], ox, oy)
        d.ellipse([sx - 7, sy - 7, sx + 7, sy + 7], outline=col, width=3)
    a, b = path[-2], path[-1]
    if abs(a[0] - b[0]) <= 1 and centre(a, ox, oy) != centre(b, ox, oy):
        (x1, y1), (x2, y2) = centre(a, ox, oy), centre(b, ox, oy)
        dx, dy = x2 - x1, y2 - y1
        d.polygon([(x2 + dx * .5, y2 + dy * .5), (x2 - dy * .45, y2 + dx * .45), (x2 + dy * .45, y2 - dx * .45)], fill=col)
    seen = {}
    for num, t in numbers:
        x, y = centre(t, ox, oy)
        k = seen.get(t, 0); seen[t] = k + 1
        x += k * 22
        d.ellipse([x - 10, y - 10, x + 10, y + 10], fill=(250, 250, 250), outline=col, width=2)
        d.text((x, y), str(num), fill=(10, 10, 10), font=small, anchor="mm")


def shot_panel(shot, eaten, hide_pac):
    """The screenshot with the dots already eaten blacked out (and Pac-Man, after the first leg)."""
    im = shot.copy()
    d = ImageDraw.Draw(im)
    for t in eaten:
        x, y = t[0] * T + T // 2, MY + t[1] * T + T // 2
        r = 11 if t in maze.ENERGIZERS else 5
        d.rectangle([x - r, y - r, x + r, y + r], fill=(0, 0, 0))
    if hide_pac:
        px = im.load()
        cx, cy = 14 * T, MY + 23 * T + T // 2  # his start, between tiles 13 and 14
        for y in range(cy - T, cy + T):
            for x in range(cx - T, cx + T):
                rr, gg, bb = px[x, y][:3]
                if not (bb > 120 and rr < 120 and gg < 120):  # keep the blue walls
                    px[x, y] = (0, 0, 0)
    return im


def main():
    global T, PW, PH, MY, LW
    src, out, title = sys.argv[1], sys.argv[2], sys.argv[3]
    shot = None
    if len(sys.argv) > 4 and sys.argv[4] != "--level":
        shot = Image.open(sys.argv[4]).convert("RGB")
        T, MY, LW = 24, 3 * 24, 5
        PW, PH = shot.size
    info = json.load(open(src, encoding="utf-8"))
    route = re.findall(r"x\d*|[LRUD]\d*", info["route"])
    level = int(sys.argv[sys.argv.index("--level") + 1]) if "--level" in sys.argv else 21
    special = any(m[0] == "x" or len(m) > 1 for m in route)
    tiles, at = walk_emu(route, level) if special else walk("".join(route))
    dirs = [m[0] for m in route if m[0] != "x"]
    turns = sum(1 for i, m in enumerate(dirs) if m != ("L" if i == 0 else dirs[i - 1]))
    backs = sum(1 for m in route if m[0] == "x")
    lates = [f"move {i + 1} {m[0]} {m[1:]} late" for i, m in enumerate(route) if m[0] != "x" and len(m) > 1]
    eaten = set(tiles) & maze.DOTS
    nleg = 6
    parts = legs(len(route), nleg)
    cols = 3
    rows = -(-len(parts) // cols)
    W = PAD + cols * (PW + PAD)
    H = HEAD + rows * (LEGHEAD + PH + PAD) + FOOT
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    f_title, f_sub = ImageFont.truetype(BOLD, 34), ImageFont.truetype(FONT, 18)
    f_leg, f_moves, small = ImageFont.truetype(BOLD, 20), ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 17), ImageFont.truetype(BOLD, 11)
    d.text((PAD, 18), title, fill=(255, 255, 255), font=f_title)
    left = len(maze.DOTS - eaten)
    rev = f"{backs} turn-backs (x: turn around mid-corridor)" if backs else "no reverses"
    sub = (f"{len(route)} moves, {turns} turns, {rev}. Start heading left; a move is the way to leave each "
           f"junction or corner. " + (f"Late presses (frames): {', '.join(lates)}. " if lates else "") + (f"Leaves {left} dots (the corner pockets) to eat by hand." if left else "Eats all 244 dots."))
    d.text((PAD, 60), sub, fill=(200, 200, 210), font=f_sub)
    left_dots = set(maze.DOTS)
    for li, (a, b) in enumerate(parts):
        col = COLOURS[li % len(COLOURS)]
        ox = PAD + (li % cols) * (PW + PAD)
        oy = HEAD + (li // cols) * (LEGHEAD + PH + PAD)
        t0 = 0 if a == 0 else at[a]
        t1 = at[b] if b < len(at) else len(tiles) - 1
        path = tiles[t0:t1 + 1]
        d.text((ox, oy + 4), f"Leg {li + 1}: moves {a + 1}-{b}", fill=col, font=f_leg)
        moves = route[a:b]
        d.text((ox, oy + 30), " ".join("".join(moves[i:i + 5]) for i in range(0, len(moves), 5)), fill=(230, 230, 230), font=f_moves)
        if shot:
            img.paste(shot_panel(shot, maze.DOTS - left_dots, li > 0), (ox, oy + LEGHEAD))
        else:
            draw_maze(d, ox, oy + LEGHEAD, left_dots)
        draw_leg(d, ox, oy + LEGHEAD + MY, path, col, [(i + 1, tiles[at[i]]) for i in range(a, b)], small, li == 0)
        left_dots -= set(path)
    d.text((PAD, H - FOOT + 14), "Each panel shows the dots left when its leg starts. Numbers mark where each move is taken; "
           "each leg starts where the last one's arrow ends. "
           + ("Screenshots from MAME; Pac-Man is a trademark of Bandai Namco." if shot else "Maze drawn from harness/maze.txt."), fill=(150, 150, 165), font=f_sub)
    img.save(out)
    print(out, len(route), "moves", turns, "turns", len(eaten), "dots eaten")


if __name__ == "__main__":
    main()
