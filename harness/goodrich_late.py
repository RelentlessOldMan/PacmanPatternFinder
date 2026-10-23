import sys, runpy, io, contextlib
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
with contextlib.redirect_stdout(io.StringIO()):
    G = runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "goodrich.py"))
TOK = G["TOK"]
import rank_sols as R
from search import parse_seg
print([t for t in TOK if not isinstance(t,str)], len(TOK))
R.LEVELS[:] = [21]; w = R.worker()
def play(late_at=None, k=0):
    w.cmd("mload start21 L"); held='L'; fr=0
    for i,t in enumerate(TOK):
        if isinstance(t,str):
            cmd = f"seg {t} 4 {k}" if (i==late_at and k) else f"seg {t} E 0"
            r = parse_seg(w.cmd(cmd)); fr += r["fr"]
            if r["st"] not in ("ok","clear"): return (i+1, r["st"], r["tile"], r["dots"])
            if r["st"]=="clear": return ("clear", i+1, fr, r["dots"])
            held=t
        else:
            out = w.cmd(f"reverse {t[1]} {t[2][0]} {t[2][1]}")
            if not out.startswith("ok"): return (i+1, out)
            held=t[1]
    out = w.cmd("reverse D 12 28"); w.cmd("wait 8"); pk = w.cmd("peek")
    return ("end", out, pk, fr)

print("on time:", play())
kills=[]; held='L'; nturn=0
for i,t in enumerate(TOK):
    if isinstance(t,str):
        if t!=held:
            nturn+=1
            for k in (1,2,3,4):
                r=play(i,k)
                if r[0]!="end": kills.append((i+1,k,r)); print("kill", i+1, k, r, flush=True)
        held=t
    else: held=t[1]
print("turns tested", nturn, "single late presses that kill", len(kills), "moves", sorted({m for m,_,_ in kills}))
