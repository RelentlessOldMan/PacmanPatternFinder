"""race_corner.py: Race's opening x0RDLDL L U R through his Clyde booey at (2-3,26), every late press 0-12 on the last 4 moves."""
import sys, itertools
sys.path.insert(0, r'C:\Playground\PacmanPatternFinder\harness')
from emu_server import Server
import replay_route
srv = Server(); srv.handle('newgame'); srv.handle('level 21'); srv.handle('msave s')
def late(m, k): return m + (str(k) if k else '')
hits = 0
moves = ['R', 'D', 'L', 'D', 'L', 'L', 'U', 'R']
for ks in itertools.product(range(0, 13), repeat=4):
    route = ['x0'] + moves[:4] + [late(moves[4], ks[0]), late(moves[5], ks[1]), late(moves[6], ks[2]), late(moves[7], ks[3])] + ['U']
    srv.handle('mload s L')
    st, n, fr = replay_route.play(srv, ''.join(route))
    if n == len(route) and st in ('ok', 'clear'):
        hits += 1; print('THROUGH', ''.join(route), fr, flush=True)
print('hits', hits)
