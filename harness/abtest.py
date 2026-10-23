"""A/B check of our patched MAME (memory savestate slots) against stock MAME 0.289.

Every route in best/*.json is played on every one of its levels, comparing the seg reply and the
RAM hash after every move:
  1. straight through, stock vs patched vs patched with idle skip (plus a pass with random late
     presses);
  2. stepped the way a search plays it (load, seg, save, next move from that save), four ways:
     stock with files, patched with files, patched with memory slots, and those with idle skip;
then state files are loaded across the builds, a slot is copied to a file and back at every
move, and memory load/seg/save is timed over many cycles to check the time per child stays flat.

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


def straight(exe, lv, route, late, idle=False):
    w = Worker(exe, idle)
    w.cmd("newgame"); w.cmd(f"level {lv}")
    out = []
    for i, d in enumerate(route):
        r = w.cmd(f"seg {d} {pol(route, lv, i, late)}")
        out.append((r, w.cmd("hash").split()[1]))
        if not r.startswith("ok"):
            break
    w.close()
    return out


def stepped(exe, lv, route, mem, tag, idle=False):
    w = Worker(exe, idle)
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
        runs = {v: run_all(straight, [(exe, lv, r, late, idle) for _, lv, r in JOBS])
                for v, exe, idle in (("stock", MAME, False), ("patched", MOD, False), ("patched-idle", MOD, True))}
        ok &= compare(f"straight{' (random late presses)' if late else ''}", runs)
    runs = {v: run_all(stepped, [(exe, lv, r, mem, f"{v}{j}", idle) for j, (_, lv, r) in enumerate(JOBS)])
            for v, exe, mem, idle in (("stock-file", MAME, False, False), ("patched-file", MOD, False, False),
                                      ("patched-mem", MOD, True, False), ("patched-mem-idle", MOD, True, True))}
    ok &= compare("stepped (search-style)", runs)

    # a state file saved by either build loads in the other (after a game is running, as in a search)
    for (a, ai, an), (b, bi, bn) in (((MAME, False, "stock"), (MOD, False, "patched")),
                                     ((MOD, False, "patched"), (MAME, False, "stock")),
                                     ((MAME, False, "stock"), (MOD, True, "patched-idle")),
                                     ((MOD, True, "patched-idle"), (MAME, False, "stock"))):
        w = Worker(a, ai)
        w.cmd("newgame"); w.cmd("level 7")
        for d in "LLDLLDRU":
            w.cmd(f"seg {d} E 0")
        w.cmd("save abx"); w.cmd("load abx U"); w.cmd("seg U E 0"); ha = w.cmd("hash").split()[1]; w.close()
        w = Worker(b, bi)
        w.cmd("newgame"); w.cmd("load abx U"); w.cmd("seg U E 0"); hb = w.cmd("hash").split()[1]; w.close()
        (ROOT / "state" / "pacman" / "abx.sta").unlink(missing_ok=True)
        print(f"file saved by {an}, loaded by {bn}: {ha} {hb} {'SAME' if ha == hb else 'DIFFERENT'}")
        ok &= ha == hb

    # slot -> file -> slot round trip at every move of a route: the next move must play the same
    # from the slot, from the file written from it, and from a slot read back from that file
    stem, lv, route = JOBS[0]
    w = Worker(MOD, True)
    w.cmd("newgame"); w.cmd(f"level {lv}")
    held, bad = "L", 0
    for i, d in enumerate(route):
        w.cmd("msave t0")
        assert w.cmd("mcopy t0 abcopy") == "ok" and w.cmd("mcopy abcopy t1 in") == "ok"
        got = []
        for load in ("mload t0", "load abcopy", "mload t1"):
            w.cmd(f"{load} {held}")
            got.append((w.cmd(f"seg {d} E 0"), w.cmd("hash").split()[1]))
        bad += len(set(got)) > 1
        held = d
        if not got[0][0].startswith("ok"):
            break
    (ROOT / "state" / "pacman" / "abcopy.sta").unlink(missing_ok=True)
    print(f"slot->file->slot, {stem} L{lv}, {i + 1} moves: {'SAME' if bad == 0 else f'{bad} DIFFERENT'}")
    ok &= bad == 0
    w.close()
    for idle in (False, True):
        w = Worker(MOD, idle)
        w.cmd("newgame"); w.cmd("level 7")
        for d in "LLDLLDRULURULURDLDRRUU":
            w.cmd(f"seg {d} E 0")
        w.cmd("msave t0")
        per = []
        for block in range(10):
            t = time.perf_counter()
            for i in range(300):
                w.cmd("mload t0 U"); w.cmd(f"seg {'ULR'[i % 3]} E 0"); w.cmd("hash"); w.cmd(f"msave c{i % 5}")
            per.append((time.perf_counter() - t) / 300 * 1000)
        print(f"memory load+seg+hash+save{' (idle skip)' if idle else ''}, ms per child per 300-child block: "
              + " ".join(f"{x:.1f}" for x in per))
        w.close()
    print("ALL OK" if ok else "FAILURES")


if __name__ == "__main__":
    main()
