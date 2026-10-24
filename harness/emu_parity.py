"""Check emu_server.py (pacemu) gives the same replies as MAME's server.lua: the same commands to both,
every reply compared (frame counters "f=" ignored).

    python emu_parity.py [--levels 5,7,21] [--random 200]
"""
import argparse
import random
import re

from worker import MAME_MEM, Worker

ROUTES = {
    5: "LLDLLDRRURULURRURUURRRRDLDLLDLDDRRRURULDLUUULDRUURDLDRDLDDDRDRRRDRRDLLULURRRRULULDLULURULLLURDDDDDD",
    21: "LLDLLDRRURULURRRDLDLUULLDLULURDLDRRUUURULURDLLDLDRDRUUULDLULLDDRDRDRDRRDLDRDLLULULURUUURULURRRDLDLLDLDDDLULURUUUULDRRR",
}


def norm(s):
    return re.sub(r"f=\d+", "f=*", s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--levels", default="5,7,21")
    ap.add_argument("--random", type=int, default=100, help="random late-press runs per level")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    a, b = Worker(MAME_MEM, idle=True), Worker("emu")
    bad = n = 0

    def both(c):
        nonlocal bad, n
        x, y = norm(a.cmd(c)), norm(b.cmd(c))
        n += 1
        if x != y:
            bad += 1
            if bad <= 20:
                print(f"DIFF {c!r}\n  mame {x}\n  emu  {y}", flush=True)
        return x

    levels = [int(v) for v in args.levels.split(",")]
    both("newgame")
    for lv in levels:
        both("newgame"), both(f"level {lv}")
        both("hash"); both(f"msave start{lv}")
    rnd = random.Random(args.seed)
    for lv in levels:
        route = ROUTES[21 if lv >= 21 else 5]
        # on time, then random late presses (seg D 4 k) and segb forks, with saves and loads
        for run in range(args.random + 1):
            both(f"mload start{lv} L")
            held = "L"
            for i, d in enumerate(route):
                if run and d != held and rnd.random() < 0.15:
                    r = both(f"segb {d} 4 t1 t2 t3 t4") if rnd.random() < 0.3 else both(f"seg {d} 4 {rnd.randint(1, 6)}")
                    if "|" in r:
                        k = rnd.randint(1, 4); both(f"mload t{k} {d}"); r = r.split(" | ")[k - 1]
                else:
                    r = both(f"seg {d} E 0")
                if rnd.random() < 0.05:
                    both("hash"); both("msave x"); both(f"mload x {d}")
                held = d
                if not r.startswith("ok"):
                    break
            both("hash")
        print(f"L{lv}: {n} commands, {bad} differ", flush=True)
    a.close(); b.close()
    print("ALL OK" if not bad else f"{bad} DIFFERENT")


if __name__ == "__main__":
    main()
