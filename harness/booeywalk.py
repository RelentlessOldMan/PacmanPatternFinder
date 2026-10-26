"""booeywalk.py: follow a fixed tile walk (e.g. the ghost-free floor walk) with live ghosts; at each catch, try late
presses on the turns just before it, so Pac-Man either dodges or booeys through (a booey: Pac-Man and the ghost swap
tiles within one half-frame game step; the ROM checks tiles once per step, two steps a frame, before anyone moves).
Beam search over {turn: frames late} by progress along the walk, then frames.

booeywalk.py <walk.json> <out.json> [--beam 24] [--back 4] [--kmax 12] [--jobs 4] [--fruits 2] [--budget 100]
"""
import sys, os, json, argparse, time
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

srv = None
P = DIRS = None


def init(walk):
    global srv, P, DIRS
    import maze
    from emu_server import Server
    srv = Server(); srv.handle("newgame"); srv.handle("level 21"); srv.handle("msave s")
    P = [tuple(t) for t in walk]
    DIRS = [next(d for d in "LRUD" if maze.step(*P[i], d) == P[i + 1]) for i in range(len(P) - 1)]


def play(late, delay=0, stop_frame=4000):
    """Pathplay along P with early presses; late[j] holds the old direction until Pac-Man has been on P[j] that many
    frames. Returns (status, frames, k, fruits); status clear / caught / stop; k = walk index reached."""
    import maze
    late = {int(a): b for a, b in late.items()}
    srv.handle("mload s L")
    f0 = srv.frame - 1
    k, h, on_since, last_t = 0, "L", 0, None
    fruits, score = 0, srv.score()
    while True:
        t = srv.tile(); fr = srv.frame - f0
        if t != last_t: on_since, last_t = fr, t
        for s in range(1, 4):
            if k + s < len(P) and P[k + s] == t and all(P[k + q] != t for q in range(0, s)):
                k += s; break
        if k == 0: want = DIRS[0]
        elif k >= len(DIRS): want = h
        else:
            cur = DIRS[k - 1]
            j = k
            while j < len(DIRS) and DIRS[j] == cur: j += 1
            if j >= len(DIRS): want = cur
            elif DIRS[j] == maze.REV[cur]:
                want = DIRS[j] if t == P[j] else cur
            else:
                between = P[k + 1:j] if t == P[k] else P[k:j]
                early = any(maze.step(*b, DIRS[j]) for b in between if b != P[j])
                want = cur if early else DIRS[j]
                if j in late and not (t == P[j] and fr - on_since >= late[j]): want = cur
        if fr <= delay: want = None
        srv.joy(want); h = want or h
        srv.wait(1)
        s2 = srv.score()
        if s2 - score == 5000: fruits += 1  # level 21's key
        score = s2
        if srv.rd(0x4DA5): return "caught", srv.frame - f0, k, fruits
        if srv.dots() >= 244: return "clear", srv.frame - f0, k, fruits
        if srv.frame - f0 > stop_frame: return "stop", srv.frame - f0, k, fruits


def turns():
    return [j for j in range(1, len(DIRS)) if DIRS[j] != DIRS[j - 1] and DIRS[j] != {"L": "R", "R": "L", "U": "D", "D": "U"}[DIRS[j - 1]]]


def job(late):
    return late, play(late)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("walk"); ap.add_argument("out")
    ap.add_argument("--beam", type=int, default=24); ap.add_argument("--back", type=int, default=4)
    ap.add_argument("--kmax", type=int, default=12); ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--fruits", type=int, default=2); ap.add_argument("--budget", type=int, default=100)
    ap.add_argument("--target", type=int, default=2438)
    a = ap.parse_args()
    walk = json.load(open(a.walk))["walk"]
    init(walk)
    T = turns()
    pool = Pool(a.jobs, initializer=init, initargs=(walk,))
    t0 = time.time()
    beam = [({}, play({}))]
    seen = {()}
    best = None
    rnd = 0
    while beam:
        rnd += 1
        kids = []
        for late, (st, fr, k, fz) in beam:
            # turns at or before the catch spot, the last --back of them, each pressed 1..kmax late
            back = [j for j in T if j <= k][-a.back:]
            for j in back:
                for v in range(1, a.kmax + 1):
                    if late.get(j, 0) >= v: continue
                    nl = dict(late); nl[j] = v
                    key = tuple(sorted(nl.items()))
                    if key in seen or sum(nl.values()) > a.budget: continue
                    seen.add(key); kids.append(nl)
        res = pool.map(job, kids, chunksize=4)
        nxt = []
        for late, r in res:
            st, fr, k, fz = r
            if st == "clear":
                print(f"  CLEAR {fr} fruits {fz} late {late}", flush=True)
                if fz >= a.fruits and (best is None or fr < best[0]):
                    best = (fr, late, fz)
                    json.dump({"walk": walk, "late": late, "frames": fr, "fruits": fz}, open(a.out, "w"))
                continue
            nxt.append((late, r))
        parent_k = max(r[2] for _, r in beam)
        nxt.sort(key=lambda x: (-x[1][2], x[1][1], sum(x[0].values())))
        beam = [x for x in nxt if x[1][2] > min(r[2] for _, r in beam)][:a.beam]
        top = beam[0] if beam else None
        print(f"round {rnd}: {len(kids)} tried, best progress {top[1][2] if top else '-'} / {len(walk)} "
              f"(frame {top[1][1] if top else '-'}, late {top[0] if top else '-'}), {time.time() - t0:.0f}s, "
              f"best clear {best[0] if best else '-'}", flush=True)
    print("done", best)


if __name__ == "__main__":
    main()
