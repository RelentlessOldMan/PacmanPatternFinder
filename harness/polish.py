"""polish.py: hill-climb a clearing walk (reorder.py result: walk + late presses). Neighbours: loop reversals and
2-opt anywhere (span <= --span, length change <= --slack), late presses changed by -3..+8 on existing keys, and new
late presses 1..--kmax on any turn. Accept the best two-fruit clear that is faster; keep up to --beam ties/near ones.
polish.py <start.json> <out.json> [--span 30] [--slack 0] [--jobs 4] [--beam 6] [--near 3]"""
import sys, os, json, argparse, time
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import booeywalk as B, reorder as R


def init_worker():
    B.FRUIT_FAIL = True


def job(x):
    w, late = x[0], x[1]
    B.init(w)
    return B.play(late, stop_frame=x[2] if len(x) > 2 else 4000)


def neighbours(w, late, a):
    n = len(w)
    out = []
    for ij, nw in R.variants(w, n // 2, a.minlen, n, n):
        if ij[1] - ij[0] <= a.span:
            out.append((ij, nw, {k: v for k, v in late.items() if k < ij[0] - 1}))
    for i in range(1, n - 2):
        for j in range(i + 2, min(n - 2, i + a.span) + 1):
            c1 = R.path(w[i - 1], w[j]); c2 = R.path(w[i], w[j + 1])
            nw = w[:i - 1] + c1 + w[i + 1:j][::-1] + c2 + w[j + 2:]
            if len(nw) - n <= a.slack and nw != w:
                d = len(nw) - n
                out.append((("2opt", i, j), nw, {(k + d if k > j else k): v for k, v in late.items() if k < i - 1 or k > j + 1}))
    B.init(w)
    for t in B.turns():
        cur = late.get(t, 0)
        for v in range(max(0, cur - 3), cur + (8 if cur else a.kmax) + 1):
            if v != cur:
                nl = dict(late)
                if v: nl[t] = v
                else: nl.pop(t, None)
                out.append((("late", t, v), w, nl))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("start"); ap.add_argument("out")
    ap.add_argument("--span", type=int, default=30); ap.add_argument("--slack", type=int, default=0)
    ap.add_argument("--minlen", type=int, default=4); ap.add_argument("--kmax", type=int, default=12)
    ap.add_argument("--jobs", type=int, default=4); ap.add_argument("--beam", type=int, default=6)
    ap.add_argument("--near", type=int, default=3); ap.add_argument("--rounds", type=int, default=50)
    a = ap.parse_args()
    d = json.load(open(a.start))
    B.FRUIT_FAIL = True
    start = ([list(t) for t in d["walk"]], {int(k): v for k, v in d["late"].items()})
    B.init(start[0]); r0 = B.play(start[1])
    print("start", r0, flush=True)
    best = r0[1]
    beam = [(start[0], start[1], [], r0[1])]
    seen = {(tuple(map(tuple, start[0])), tuple(sorted(start[1].items())))}
    pool = Pool(a.jobs, initializer=init_worker)
    t0 = time.time()
    for rnd in range(1, a.rounds + 1):
        kids = []
        for w, late, hist, fr in beam:
            for mv, nw, nl in neighbours(w, late, a):
                key = (tuple(map(tuple, nw)), tuple(sorted(nl.items())))
                if key not in seen:
                    seen.add(key); kids.append((nw, nl, hist + [mv]))
        # stop each run once it is beyond best + near (cannot help)
        res = pool.map(job, [(w, l, best + a.near + 1) for w, l, _ in kids], chunksize=8)
        good = []
        for (w, l, h), r in zip(kids, res):
            if r[0] == "clear" and r[3] >= 2 and r[1] <= best + a.near:
                good.append((w, l, h, r[1]))
        good.sort(key=lambda x: x[3])
        if good and good[0][3] < best:
            best = good[0][3]
            w, l, h, fr = good[0]
            json.dump({"walk": w, "late": l, "frames": fr, "fruits": 2, "moves": d.get("moves", []) + h}, open(a.out, "w"))
            print(f"  NEW BEST {fr} via {h}", flush=True)
        beam = good[:a.beam]
        print(f"round {rnd}: {len(kids)} tried, {len(good)} within best+{a.near}, best {best}, {time.time() - t0:.0f}s", flush=True)
        if not beam:
            break
    print("done", best)


if __name__ == "__main__":
    main()
