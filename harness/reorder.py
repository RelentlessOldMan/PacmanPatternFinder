"""reorder.py: user's idea (2026-10-26): the ghost-free floor walk doubles back a lot, so parts of it can be traversed
in another order (or mirrored) at the same length. That changes when dots are eaten (Pac-Man's speed phase) and where
he is when a ghost arrives, which may dodge a catch or line up a booey. Moves: reverse any stretch P[i..j] that starts
and ends on the same tile (same tiles, same length, new eat order). Beam over walks by progress with live ghosts.

reorder.py <walk.json> <out.json> [--rounds 12] [--beam 8] [--minlen 4] [--before 30] [--shard i/n]
"""
import sys, os, json, argparse, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import booeywalk as B
from multiprocessing import Pool


def evaluate(walk, late=None):
    B.init(walk)
    return B.play(late or {})


def init_worker(ff):
    B.FRUIT_FAIL = ff


def job(x):
    w, late, hist = x
    return w, late, hist, evaluate(w, late)


def variants(walk, k, minlen, before, after):
    """Loop reversals touching the stretch just before the catch at walk index k."""
    out = []
    pos = {}
    for i, t in enumerate(map(tuple, walk)):
        pos.setdefault(t, []).append(i)
    for idx in pos.values():
        for a in range(len(idx)):
            for b in range(a + 1, len(idx)):
                i, j = idx[a], idx[b]
                if j - i < minlen or j < k - before or i > k + after:
                    continue
                w = walk[:i] + walk[i:j + 1][::-1] + walk[j + 1:]
                if w != walk:
                    out.append(((i, j), w))
    return out


def path(a, b):
    """Shortest tile path a..b inclusive (BFS, tunnel wraps)."""
    import maze
    from collections import deque
    a, b = tuple(a), tuple(b)
    prev, q = {a: None}, deque([a])
    while q:
        t = q.popleft()
        if t == b:
            break
        for d in maze.exits(*t):
            n = maze.step(*t, d)
            if n not in prev:
                prev[n] = t; q.append(n)
    out, t = [], b
    while t is not None:
        out.append(list(t)); t = prev[t]
    return out[::-1]


def two_opt(walk, k, before, after, slack):
    """Reverse P[i..j] and reconnect P[i-1]->P[j] and P[i]->P[j+1] by shortest paths (all dots stay covered)."""
    out = []
    n = len(walk)
    for i in range(max(1, k - before), min(n - 2, k + after) + 1):
        for j in range(i + 2, min(n - 2, k + after) + 1):
            c1 = path(walk[i - 1], walk[j]); c2 = path(walk[i], walk[j + 1])
            w = walk[:i - 1] + c1 + walk[i + 1:j][::-1] + c2 + walk[j + 2:]
            if len(w) - n <= slack and w != walk:
                out.append((("2opt", i, j), w))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("walk"); ap.add_argument("out")
    ap.add_argument("--rounds", type=int, default=12); ap.add_argument("--beam", type=int, default=8)
    ap.add_argument("--minlen", type=int, default=4); ap.add_argument("--before", type=int, default=60)
    ap.add_argument("--after", type=int, default=4); ap.add_argument("--slack", type=int, default=4)
    ap.add_argument("--jobs", type=int, default=3); ap.add_argument("--back", type=int, default=4)
    ap.add_argument("--kmax", type=int, default=12); ap.add_argument("--budget", type=int, default=60)
    ap.add_argument("--mirror", action="store_true", help="start from the left-right mirror of the walk"); ap.add_argument("--target", type=int, default=2438)
    ap.add_argument("--seed", type=int, default=0, help="with --noise: random beam ranking")
    ap.add_argument("--noise", type=float, default=0, help="add uniform 0..noise frames to each kid's rank key")
    ap.add_argument("--walk-index", type=int, help="use walks[i] of the floor file")
    ap.add_argument("--fruit-fail", action="store_true", help="a fruit vanishing uneaten counts as a catch")
    a = ap.parse_args()
    B.FRUIT_FAIL = a.fruit_fail
    d = json.load(open(a.walk))
    walk = [list(t) for t in (d["walks"][a.walk_index]["walk"] if a.walk_index is not None else d["walk"])]
    if a.mirror:
        walk = [[13, 23]] + [[27 - c, r] for c, r in walk]
    base_len = len(walk)
    t0 = time.time()
    pool = Pool(a.jobs, initializer=init_worker, initargs=(a.fruit_fail,))
    r0 = evaluate(walk)
    print("base", r0, flush=True)
    beam = [(walk, {}, [], r0)]
    seen = {(tuple(map(tuple, walk)), ())}
    best = None
    for rnd in range(1, a.rounds + 1):
        kids = []
        def add(w, late, hist, pk):
            key = (tuple(map(tuple, w)), tuple(sorted(late.items())))
            if key not in seen:
                seen.add(key); kids.append((w, late, hist, pk))
        for w, late, hist, r in beam:
            k = r[2]
            for ij, nw in variants(w, k, a.minlen, a.before, a.after) + two_opt(w, k, a.before, a.after, a.slack - (len(w) - base_len)):
                i0 = ij[1] if ij[0] == "2opt" else ij[0]
                add(nw, {t: v for t, v in late.items() if t < i0 - 1}, hist + [ij], k)
            B.init(w)
            T = B.turns()
            for t in [t for t in T if t <= k][-a.back:]:
                for v in range(1, a.kmax + 1):
                    if late.get(t, 0) >= v or sum(late.values()) - late.get(t, 0) + v > a.budget:
                        continue
                    nl = dict(late); nl[t] = v
                    add(w, nl, hist + [("late", t, v)], k)
        res = pool.map(job, [x[:3] for x in kids], chunksize=4)
        nxt = []
        for (w, late, hist, r), (_, _, _, pk) in zip(res, kids):
            if r[0] == "clear":
                print(f"  CLEAR {r[1]} fruits {r[3]} via {hist}", flush=True)
                if r[3] >= 2 and (best is None or r[1] < best[0]):
                    best = (r[1], hist)
                    json.dump({"walk": w, "late": late, "frames": r[1], "fruits": r[3], "moves": hist}, open(a.out, "w"))
                continue
            if r[2] > pk:
                nxt.append((w, late, hist, r))
        import random
        rng = random.Random(a.seed * 1000 + rnd)
        nxt = [(x, x[3][2] * 8 - x[3][1] / 8 + rng.uniform(0, a.noise)) for x in nxt]  # ~8 frames a tile
        nxt.sort(key=lambda y: -y[1])
        nxt = [y[0] for y in nxt]
        # diversity: at most 3 kids per progress value
        cnt, beam = {}, []
        for x in nxt:
            if cnt.get(x[3][2], 0) < 3:
                cnt[x[3][2]] = cnt.get(x[3][2], 0) + 1; beam.append(x)
            if len(beam) >= a.beam: break
        top = beam[0] if beam else None
        print(f"round {rnd}: {len(kids)} tried, best progress {top[3][2] if top else '-'} / {len(top[0]) if top else '-'} "
              f"(frame {top[3][1] if top else '-'}, {top[2] if top else ''}), {time.time() - t0:.0f}s, "
              f"best clear {best[0] if best else '-'}", flush=True)
        if not beam:
            break
    print("done", best)


if __name__ == "__main__":
    main()
