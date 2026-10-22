"""Does pressing the next turn as soon as the previous turn registers give the identical game?"""
import json, sys
from worker import Worker

route = json.load(open(sys.argv[1]))["route"] + "D"   # + the zigzag move the search couldn't take
w = Worker()

def play(early, k=0):
    w.cmd("load start_L1 L")
    out = []
    for i, d in enumerate(route):
        nxt = route[i + 1] + str(k) if early and i + 1 < len(route) else "-"
        seg = w.cmd(f"seg {d} E 0 {nxt}").split()
        out.append((seg, w.cmd("hash").split()[1]))
        if seg[0] != "ok":
            break
    return out

base = play(False)
for k in range(1, 6):
    early = play(True, k)
    diff = [i for i, (a, b) in enumerate(zip(base, early)) if a[1] != b[1]]
    print(f"press {k} frames after turn registers: moves {len(early)}/{len(base)} first divergence {diff[:1] or 'none'}")
w.close()
