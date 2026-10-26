"""pathplay2: pathplay as a function with a start delay and late presses {turn path index: frames late}."""
import sys, json
sys.path.insert(0, r'C:\Playground\PacmanPatternFinder\harness')
import maze
from emu_server import Server
REV = maze.REV
srv = Server(); srv.handle("newgame"); srv.handle("level 21"); srv.handle("msave s")

def d_of(a, b):
    return next(d for d in "LRUD" if maze.step(*a, d) == b)

def run(P, delay=0, late={}, stop_frame=4000, watch=None):
    dirs = [d_of(P[i], P[i + 1]) for i in range(len(P) - 1)]
    srv.handle("mload s L")
    f0 = srv.frame - 1
    lives = srv.rd(0x4E14)
    k, h, on_since, last_t = 0, "L", 0, None
    while True:
        t = srv.tile(); fr = srv.frame - f0
        if t != last_t: on_since, last_t = fr, t
        for s in range(1, 4):
            if k + s < len(P) and P[k + s] == t and all(P[k + q] != t for q in range(0, s)):
                k += s; break
        if k == 0: want = dirs[0]
        elif k >= len(dirs): want = h
        else:
            cur = dirs[k - 1]
            j = k
            while j < len(dirs) and dirs[j] == cur: j += 1
            if j >= len(dirs): want = cur
            elif dirs[j] == REV[cur]:
                want = dirs[j] if t == P[j] else cur
            else:
                between = P[k + 1:j] if t == P[k] else P[k:j]
                early = any(maze.step(*b, dirs[j]) for b in between if b != P[j])
                want = cur if early else dirs[j]
                if j in late and not (t == P[j] and fr - on_since >= late[j]): want = cur
        if fr <= delay: want = None
        srv.joy(want); h = want or h
        if watch: watch(fr, t, k)
        srv.wait(1)
        if srv.dots() >= 244: return "clear", srv.frame - f0, k
        if srv.rd(0x4E14) != lives: return "dead", srv.frame - f0, k
        if srv.frame - f0 > stop_frame: return "stop", srv.frame - f0, k

def turns(P):
    dirs = [d_of(P[i], P[i + 1]) for i in range(len(P) - 1)]
    return [j for j in range(1, len(dirs)) if dirs[j] != dirs[j - 1]]
