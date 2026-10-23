"""A/B check of our patched MAME (memory savestate slots) against stock MAME 0.289.

Every route in best/*.json is played on every one of its levels, comparing the seg reply and the
RAM hash after every move:
  1. straight through, stock vs patched (plus a pass with random late presses);
  2. stepped the way a search plays it (load, seg, save, next move from that save), three ways:
     stock with files, patched with files, patched with memory slots;
then an old savestate file is loaded on both, a slot is copied to a file and back, and memory
load/seg/save is timed over many cycles to check the time per child stays flat.

  python abtest.py [patched mame.exe]     (default ../mame-0.289-mem/mame.exe)
"""
import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from worker import MAME, ROOT, Worker

MOD = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "mame-0.289-mem" / "mame.exe"
JOBS = [(f.stem, lv, json.loads(f.read_text())["route"])
        for f in sorted((ROOT / "best").glob("*.json")) for lv in json.loads(f.read_text())["levels"]]


def pol(route, lv, i, late):
    # the press for move i: on time, or (late pass) a seeded random 0..4 frames late
    if not late:
        return "E 0"
    k = random.Random(f"{route}{lv}{i}").randint(0, 4)
    return f"4 {k}" if k else "E 0"


def straight(exe, lv, route, late):
    w = Worker(exe)
    w.cmd("newgame"); w.cmd(f"level {lv}")
    out = []
    for i, d in enumerate(route):
        r = w.cmd(f"seg {d} {pol(route, lv, i, late)}")
        out.append((r, w.cmd("hash").split()[1]))
        if not r.startswith("ok"):
            break
    w.close()
    return out


def stepped(exe, lv, route, mem, tag):
    w = Worker(exe)
    save, load = ("msave", "mload") if mem else ("save", "load")
    w.cmd("newgame"); w.cmd(f"level {lv}")
    name = f"ab{tag}_0"
    w.cmd(f"{save} {name}")
    held, out = "L", []
    for i, d in enumerate(route):
        w.cmd(f"{load} {name} {held}")
        r = w.cmd(f"seg {d} E 0")
        out.append((r, w.cmd("hash").split()[1]))
        if not r.startswith("ok"):
            break
        prev, name, held = name, f"ab{tag}_{i + 1}", d
        assert w.cmd(f"{save} {name}") == "ok"
        if mem:
            w.cmd(f"mdrop {prev}")
        else:
            (ROOT / "state" / "pacman" / f"{prev}.sta").unlink(missing_ok=True)
    (ROOT / "state" / "pacman" / f"{name}.sta").unlink(missing_ok=True)
    w.close()
    return out


def compare(label, runs):
    """runs: {variant: [per-job move lists]}; report moves where any variant differs from the first."""
    names = list(runs)
    moves = diffs = 0
    for j, (stem, lv, _) in enumerate(JOBS):
        ref = runs[names[0]][j]
        for v in names[1:]:
            got = runs[v][j]
            if len(got) != len(ref):
                print(f"  {stem} L{lv}: {v} played {len(got)} moves, {names[0]} {len(ref)}")
                diffs += 1
            for i, (a, b) in enumerate(zip(ref, got)):
                if a != b:
                    diffs += 1
                    if diffs <= 5:
                        print(f"  {stem} L{lv} move {i}: {names[0]} {a} | {v} {b}")
        moves += len(ref)
    print(f"{label}: {moves} moves x {len(names)} ({', '.join(names)}): "
          f"{'IDENTICAL' if diffs == 0 else f'{diffs} DIFFERENCES'}")
    return diffs == 0


def run_all(fn, args_list):
    with ThreadPoolExecutor(8) as ex:
        return list(ex.map(lambda a: fn(*a), args_list))


def main():
    print(f"stock {MAME}\npatched {MOD}\n{len(JOBS)} level runs from best/*.json")
    ok = True
    for late in (False, True):
        runs = {v: run_all(straight, [(exe, lv, r, late) for _, lv, r in JOBS])
                for v, exe in (("stock", MAME), ("patched", MOD))}
        ok &= compare(f"straight{' (random late presses)' if late else ''}", runs)
    runs = {v: run_all(stepped, [(exe, lv, r, mem, f"{v}{j}") for j, (_, lv, r) in enumerate(JOBS)])
            for v, exe, mem in (("stock-file", MAME, False), ("patched-file", MOD, False),
                                ("patched-mem", MOD, True))}
    ok &= compare("stepped (search-style)", runs)

    # a state file saved by either build loads in the other (after a game is running, as in a search)
    for a, b, an, bn in ((MAME, MOD, "stock", "patched"), (MOD, MAME, "patched", "stock")):
        w = Worker(a)
        w.cmd("newgame"); w.cmd("level 7")
        for d in "LLDLLDRU":
            w.cmd(f"seg {d} E 0")
        w.cmd("save abx"); w.cmd("load abx U"); w.cmd("seg U E 0"); ha = w.cmd("hash").split()[1]; w.close()
        w = Worker(b)
        w.cmd("newgame"); w.cmd("load abx U"); w.cmd("seg U E 0"); hb = w.cmd("hash").split()[1]; w.close()
        (ROOT / "state" / "pacman" / "abx.sta").unlink(missing_ok=True)
        print(f"file saved by {an}, loaded by {bn}: {ha} {hb} {'SAME' if ha == hb else 'DIFFERENT'}")
        ok &= ha == hb

    # slot -> file -> slot round trip, and timing over many memory cycles
    w = Worker(MOD)
    w.cmd("newgame"); w.cmd("level 7")
    for d in "LLDLLDRULURULURDLDRRUU":
        w.cmd(f"seg {d} E 0")
    w.cmd("msave t0")
    w.cmd("mload t0 U"); w.cmd("seg U E 0"); h0 = w.cmd("hash").split()[1]
    w.cmd("mcopy t0 abcopy"); w.cmd("mcopy abcopy t1 in")
    w.cmd("mload t1 U"); w.cmd("seg U E 0"); h1 = w.cmd("hash").split()[1]
    w.cmd("load abcopy U"); w.cmd("seg U E 0"); h2 = w.cmd("hash").split()[1]
    (ROOT / "state" / "pacman" / "abcopy.sta").unlink(missing_ok=True)
    print(f"slot->file->slot: {h0} {h1} {h2} {'SAME' if h0 == h1 == h2 else 'DIFFERENT'}")
    ok &= h0 == h1 == h2
    per = []
    for block in range(10):
        t = time.perf_counter()
        for i in range(300):
            w.cmd("mload t0 U"); w.cmd(f"seg {'ULR'[i % 3]} E 0"); w.cmd("hash"); w.cmd(f"msave c{i % 5}")
        per.append((time.perf_counter() - t) / 300 * 1000)
    print("memory load+seg+hash+save, ms per child per 300-child block: " + " ".join(f"{x:.1f}" for x in per))
    w.close()
    print("ALL OK" if ok else "FAILURES")


if __name__ == "__main__":
    main()
