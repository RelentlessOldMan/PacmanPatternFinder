"""Maze geometry mirrored from server.lua. Coordinates: (col 0..27, row 0..30)."""
from pathlib import Path

ROWS = [line.ljust(28) for line in Path(__file__).with_name("maze.txt").read_text().splitlines()]
W, H = 28, len(ROWS)
DIRS = {"R": (1, 0), "D": (0, 1), "L": (-1, 0), "U": (0, -1)}
REV = {"R": "L", "L": "R", "U": "D", "D": "U"}
TUNNEL_ROW = 14


def wrapc(c):
    return ((c + 2) % 32) - 2


def is_open(c, r):
    if r < 0 or r >= H:
        return False
    if c < 0 or c >= W:
        return r == TUNNEL_ROW
    return ROWS[r][c] != "#"


def exits(c, r):
    return [d for d, (dc, dr) in DIRS.items() if is_open(c + dc, r + dr)]


def is_node(c, r):
    if not (0 <= c < W) or not is_open(c, r):
        return False
    ex = set(exits(c, r))
    if len(ex) >= 3:
        return True
    return len(ex) == 2 and ex not in ({"L", "R"}, {"U", "D"})


def step(c, r, d):
    dc, dr = DIRS[d]
    return wrapc(c + dc), r + dr


def next_node(c, r, d):
    """First node at or ahead of (c,r) moving d; returns (node, tiles walked incl. node)."""
    path = []
    for _ in range(40):
        path.append((c, r))
        if is_node(c, r):
            return (c, r), path
        c, r = step(c, r, d)
    raise ValueError(f"no node ahead of {(c, r)} {d}")


DOTS = frozenset((c, r) for r in range(H) for c in range(W) if ROWS[r][c] in ".o")
ENERGIZERS = frozenset((c, r) for r in range(H) for c in range(W) if ROWS[r][c] == "o")
assert len(DOTS) == 244, len(DOTS)


def _bfs_all(src):
    from collections import deque
    dist = {src: 0}
    q = deque([src])
    while q:
        c, r = q.popleft()
        for d in DIRS:
            n = step(c, r, d)
            if n not in dist and is_open(*n):
                dist[n] = dist[(c, r)] + 1
                q.append(n)
    return dist


_DIST = {}


def bfs_dist(src, targets):
    """Shortest walking distance (tiles) from src to any tile in targets."""
    if not targets:
        return 0
    if src not in _DIST:
        _DIST[src] = _bfs_all(src)
    d = _DIST[src]
    return min(d.get(t, 99) for t in targets)



def clusters(dots):
    """Number of separate groups of dots (4-connected along the maze)."""
    left, n = set(dots), 0
    while left:
        n += 1
        stack = [left.pop()]
        while stack:
            c, r = stack.pop()
            for d in DIRS:
                nb = step(c, r, d)
                if nb in left:
                    left.remove(nb); stack.append(nb)
    return n


def groups(dots):
    """The separate groups of dots (4-connected along the maze), as lists of tiles."""
    left, out = set(dots), []
    while left:
        g = [left.pop()]
        stack = list(g)
        while stack:
            c, r = stack.pop()
            for d in DIRS:
                nb = step(c, r, d)
                if nb in left:
                    left.remove(nb); stack.append(nb); g.append(nb)
        out.append(g)
    return out


def gaps(dots):
    """Empty tiles walked joining the groups of dots into one tour: the total length of a minimum
    spanning tree over the groups, each edge the walking distance between them minus the 1 step
    from a dot onto its neighbour. A few dots stranded far from the rest cost a long trip."""
    gs = groups(dots)
    if len(gs) < 2:
        return 0
    from collections import deque
    owner = {t: i for i, g in enumerate(gs) for t in g}
    dist = [[0] * len(gs) for _ in gs]
    for i, g in enumerate(gs):  # one BFS from each whole group finds its distance to every other
        seen, q, todo = {t: 0 for t in g}, deque(g), len(gs) - 1
        found = {i}
        while q and todo:
            t = q.popleft()
            for d in DIRS:
                n = step(*t, d)
                if n in seen or not is_open(*n):
                    continue
                seen[n] = seen[t] + 1
                j = owner.get(n)
                if j is not None and j not in found:
                    found.add(j); todo -= 1; dist[i][j] = seen[n] - 1
                q.append(n)
    best = {j: dist[0][j] for j in range(1, len(gs))}  # Prim
    total = 0
    while best:
        j = min(best, key=best.get)
        total += best.pop(j)
        for k in best:
            best[k] = min(best[k], dist[j][k])
    return total


def _pockets():
    """Tiles that can only be reached through an energizer without reversing: from each energizer,
    walk both ways along the corridor (through corners) up to the first junction."""
    out = set()
    for e in ENERGIZERS:
        out.add(e)
        for d in exits(*e):
            c, r, h = *step(*e, d), d
            while len(exits(c, r)) == 2:
                out.add((c, r))
                h = next(x for x in exits(c, r) if x != REV[h])
                c, r = step(c, r, h)
    return frozenset(out)


POCKETS = _pockets()  # 4 energizers + 7 dots each at the top corners, 11 each at the bottom
