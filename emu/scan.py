import sys
from emu import Pacman
prefix = sys.argv[1]
rows = [l.split() for l in open(prefix + ".txt")]
ram = open(prefix + ".ram", "rb").read()
def run(off, limit=None):
    m = Pacman(off); in0 = in1 = 0xFF
    for f, r in enumerate(rows[:limit]):
        if r[1] != "-": in0 = int(r[1].split("/")[0], 16)
        if r[2] != "-": in1 = int(r[2].split("/")[0], 16)
        m.frame(in0, in1)
        if m.ram() != ram[f * 4096:(f + 1) * 4096]:
            return f
    return len(rows[:limit])
if __name__ == "__main__":
    lo, hi, step = map(int, sys.argv[2:5])
    best = {}
    for off in range(lo, hi + 1, step):
        best[off] = run(off, 3000)
    top = sorted(best.items(), key=lambda kv: -kv[1])[:10]
    print(top)
