"""poke_route.py <route> <move idx (0-based)> <late list>: diagnostic only. Rotate Pac-Man's speed pattern by k steps
(RAM poke) after move idx-1 and press move idx with each lateness; report which phases would let it through."""
import sys
import os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from emu_server import Server
from search import tokens
import replay_route as rr
route, idx = sys.argv[1], int(sys.argv[2])
lates = [int(x) for x in sys.argv[3].split(',')]
srv = Server(); srv.handle("newgame"); srv.handle("level 21"); srv.handle("msave s0")
def rot(k):
    v = (srv.rd(0x4D47) << 24) | (srv.rd(0x4D46) << 16) | (srv.rd(0x4D49) << 8) | srv.rd(0x4D48)
    v = ((v << k) | (v >> (32 - k))) & 0xFFFFFFFF if k else v
    for a, x in ((0x4D47, v >> 24), (0x4D46, (v >> 16) & 255), (0x4D49, (v >> 8) & 255), (0x4D48, v & 255)):
        srv.m._ram[a - 0x4000] = x
R = tokens(route)
for late in lates:
    for k in range(16):
        r = list(R); r[idx] = r[idx][0] + (str(late) if late else '')
        srv.handle("mload s0 L")
        res = rr.play(srv, r, on_move=lambda i, m, st, f: rot(k) if i == idx - 1 else None)
        print(idx + 1, r[idx], 'phase+', k, res, flush=True)
