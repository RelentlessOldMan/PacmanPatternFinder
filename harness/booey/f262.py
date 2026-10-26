import json
from pathplay2 import run, srv
P = [tuple(t) for t in json.load(open('path21.json'))]
j29, j26 = P.index((1, 29)), P.index((1, 26))
def w32(a): return (srv.rd(a+1) << 24) | (srv.rd(a) << 16) | (srv.rd(a+3) << 8) | srv.rd(a+2)
for d in range(0, 4):
  for b in range(20, 42):
    snap = {}
    def w(fr, t, k):
        if fr in (261, 262):
            pp = w32(0x4D46)
            snap[fr] = (srv.rd(0x4D09), srv.rd(0x4D08), srv.rd(0x4D07), srv.rd(0x4D06), (pp >> 31) & 1, (pp >> 30) & 1, srv.rd(0x4D9D), srv.rd(0x4DA4))
    res = run(P, d, {j26: b} if b else {}, stop_frame=700, watch=w)
    print(d, b, res, snap.get(261), snap.get(262))
