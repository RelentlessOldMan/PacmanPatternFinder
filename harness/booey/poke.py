import json, ctypes
from pathplay2 import run, srv
from emu_server import D
D.pm_ram.restype = ctypes.POINTER(ctypes.c_uint8)
ram = D.pm_ram(srv.h)
P = [tuple(t) for t in json.load(open('path21.json'))]
j26 = P.index((1, 26))
def rot(k):  # rotate Pac's normal speed pattern left by k bits (k half-steps of phase)
    a = 0x4D46 - 0x4000
    v = (ram[a+1] << 24) | (ram[a] << 16) | (ram[a+3] << 8) | ram[a+2]
    v = ((v << k) | (v >> (32 - k))) & 0xFFFFFFFF if k else v
    ram[a+1], ram[a], ram[a+3], ram[a+2] = v >> 24, (v >> 16) & 255, (v >> 8) & 255, v & 255
hits = []
for k in range(16):
    for b in range(24, 42):
        dead = []
        def w(fr, t, kk):
            if fr == 240: rot(k)
            if srv.rd(0x4DA5) and not dead: dead.append(fr)
        res = run(P, 0, {j26: b}, stop_frame=330, watch=w)
        if not dead: hits.append((k, b))
print('survivors past frame 330:', hits)
