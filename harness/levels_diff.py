"""Which levels does the game set up differently? Dump RAM at the start of play per level."""
from concurrent.futures import ThreadPoolExecutor
from worker import Worker

LEVELS = list(range(1, 24)) + [50, 255]

def dump(lv):
    w = Worker(); w.cmd("newgame"); w.cmd(f"level {lv}")
    d = bytes.fromhex(w.cmd("dump").split()[1]); w.close()
    return lv, d

with ThreadPoolExecutor(10) as ex:
    dumps = dict(ex.map(dump, LEVELS))
base = 0x4C00
# bytes that vary across levels
vary = [i for i in range(len(dumps[1])) if len({dumps[l][i] for l in LEVELS}) > 1]
print("varying addrs:", [hex(base + i) for i in vary])
for l in LEVELS:
    print(f"{l:3d}", " ".join(f"{dumps[l][i]:02x}" for i in vary))
