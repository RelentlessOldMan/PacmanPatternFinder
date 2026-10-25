"""drift_end.py <trials> <seed> <out.json> [p kmax lo enddrift]: how often each L21 ending survives when the first 110 moves of the 118
drift. Each trial plays moves 1-79 on time (spread-out drift there dies at moves 37-46/78 anyway), then each turn of
moves 80-110 late by 1-2 frames 30% of the time; keeps the trial if
Pac-Man is alive at move 110, then plays every candidate ending on time from there. Candidates: the 118's own
ending, the user's (RRULLDRU after 112) and every ending from the safeend searches. Defaults p=0.3 kmax=2 lo=80;
enddrift=1 also presses each ending turn late the same way (each ending gets its own random lateness)."""
import json, random, re, sys
from search import parse_seg, tokens
from worker import MAME_MEM, Worker

trials, seed, outp = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
P, KMAX, LO, ENDDRIFT = (float(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]), int(sys.argv[7])) if len(sys.argv) > 4 else (0.3, 2, 80, 0)
r = tokens(json.load(open("../best/L21_full_118.json"))["route"])
ends = {"118": r[110:], "user": r[110:112] + list("RRULLDRU")}
for log in ("search_L21_safeend_k110_mg32.log", "search_L21_safeend_k110_ot95_mg24.log", "search_L21_safe3_hist24_s11.log"):
    for m in re.finditer(r"SOLUTION.*?route=(\S+)", open(log).read()):
        t = tokens(m.group(1))
        if t[:110] == r[:110]:
            ends.setdefault(f"s{len(t)}_{''.join(t[110:])}", t[110:])
rng = random.Random(seed)
w = Worker(MAME_MEM, idle=True)
w.cmd("newgame"); w.cmd("level 21"); w.cmd("msave s")
live = {k: 0 for k in ends}
kept = 0
for n in range(trials):
    w.cmd("mload s L")
    ok = True
    held = "L"
    for i, d in enumerate(r[:110]):
        k = rng.randint(1, KMAX) if i >= LO - 1 and d != held and rng.random() < P else 0
        held = d
        if parse_seg(w.cmd(f"seg {d} 4 {k}" if k else f"seg {d} E 0"))["st"] != "ok":
            ok = False; break
    if not ok:
        continue
    kept += 1
    w.cmd("msave a")
    for name, e in ends.items():
        w.cmd(f"mload a {r[109]}")
        eh = r[109]
        for d in e:
            k = rng.randint(1, KMAX) if ENDDRIFT and d != eh and rng.random() < P else 0
            eh = d
            st = parse_seg(w.cmd(f"seg {d} 4 {k}" if k else f"seg {d} E 0"))["st"]
            if st != "ok":
                break
        live[name] += st in ("clear", "win") or st == "ok"
    print(n, kept, flush=True)
json.dump({"kept": kept, "live": live, "ends": {k: "".join(v) for k, v in ends.items()}}, open(outp, "w"), indent=1)
for k in sorted(live, key=lambda k: -live[k])[:12]:
    print(f"{live[k]:4d}/{kept}  {k[:60]}")
