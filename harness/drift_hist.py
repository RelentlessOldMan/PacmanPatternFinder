"""drift_hist.py <n> <seed> <out.json> [p kmax lo]: lateness histories for search.py --history-sims --late-rel on
level 21. Each is the 118's first 110 moves with each turn from move lo on pressed 1-kmax frames late with chance
p, kept only if Pac-Man is still alive at move 110; the history then runs on (moves 111-160) with the same random
lateness, so the searched ending has to survive a sloppy player there too."""
import json, random, sys
from search import parse_seg, tokens
from worker import MAME_MEM, Worker

n, seed, outp = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
P, KMAX, LO = (float(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6])) if len(sys.argv) > 4 else (0.3, 2, 80)
r = tokens(json.load(open("../best/L21_full_118.json"))["route"])
rng = random.Random(seed)
w = Worker(MAME_MEM, idle=True)
w.cmd("newgame"); w.cmd("level 21"); w.cmd("msave s")
hists, tries = [], 0
while len(hists) < n:
    tries += 1
    h = [rng.randint(1, KMAX) if i >= LO - 1 and rng.random() < P else 0 for i in range(160)]
    w.cmd("mload s L"); held, ok = "L", True
    for i, d in enumerate(r[:110]):
        k = h[i] if d != held else 0
        held = d
        if parse_seg(w.cmd(f"seg {d} 4 {k}" if k else f"seg {d} E 0"))["st"] != "ok":
            ok = False; break
    if ok:
        hists.append(h)
print(f"{n} histories from {tries} tries")
json.dump({"21": hists}, open(outp, "w"))
