"""pattern_sheet.py <route.json> <out.png> <title>: draw a route as one image to learn it from.

The route is split into legs, one maze panel each: the leg's path in colour with every move numbered
where it's taken, on the dots still left when the leg starts. The maze is drawn from maze.txt (no game
graphics)."""
import json, sys, os
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import maze

T = 20                      # pixels per tile
PW, PH = maze.W * T, maze.H * T
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
            if len(pts) > 1: d.line(pts, fill=col, width=4, joint="curve")
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
    if len(pts) > 1: d.line(pts, fill=col, width=4, joint="curve")
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


def main():
    src, out, title = sys.argv[1], sys.argv[2], sys.argv[3]
    info = json.load(open(src, encoding="utf-8"))
    route = info["route"]
    tiles, at = walk(route)
    turns = sum(1 for i, m in enumerate(route) if m != ("L" if i == 0 else route[i - 1]))
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
    sub = (f"{len(route)} moves, {turns} turns, no reverses. Start heading left; a move is the way to leave each "
           f"junction or corner. " + (f"Leaves {left} dots (the corner pockets) to eat by hand." if left else "Eats all 244 dots."))
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
        d.text((ox, oy + 30), " ".join(moves[i:i + 5] for i in range(0, len(moves), 5)), fill=(230, 230, 230), font=f_moves)
        draw_maze(d, ox, oy + LEGHEAD, left_dots)
        draw_leg(d, ox, oy + LEGHEAD, path, col, [(i + 1, tiles[at[i]]) for i in range(a, b)], small, li == 0)
        left_dots -= set(path)
    d.text((PAD, H - FOOT + 14), "Each panel shows the dots left when its leg starts. Numbers mark where each move is taken; "
           "each leg starts where the last one's arrow ends. Maze drawn from harness/maze.txt.", fill=(150, 150, 165), font=f_sub)
    img.save(out)
    print(out, len(route), "moves", turns, "turns", len(eaten), "dots eaten")


if __name__ == "__main__":
    main()
