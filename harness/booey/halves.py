import os, json
os.environ["PACMAN_NOGHOSTS"] = "1"
from pathplay2 import run, srv
P = [tuple(t) for t in json.load(open('path21.json'))]
def w32(a): return (srv.rd(a+1) << 24) | (srv.rd(a) << 16) | (srv.rd(a+3) << 8) | srv.rd(a+2)
rows = []
def w(fr, t, k):
    rows.append((fr, srv.rd(0x4D09), srv.rd(0x4D07), srv.rd(0x4D06), w32(0x4D46), w32(0x4D7A), srv.rd(0x4D9D), srv.rd(0x4D2F)))
print(run(P, 0, {}, stop_frame=320, watch=w))
prev = None
for r in rows:
    fr, px, cx, cy, pp, cp, st, hd = r
    if prev and 225 <= fr <= 320:
        _, ppx, pcx, _, ppp, pcp, pst, _ = prev
        pb = ((ppp >> 31) & 1, (ppp >> 30) & 1); cb = ((pcp >> 31) & 1, (pcp >> 30) & 1)
        print(fr, 'pac', ppx, '->', px, 'bits', pb, 'stall', pst, '| clyde', pcx, '->', cx, 'y', cy, 'bits', cb, 'hd', hd)
    prev = r
