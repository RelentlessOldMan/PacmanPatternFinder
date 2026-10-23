"""bench.py's per-child sequence, three ways: stock MAME with files, patched with files, patched
with memory slots (see mame-patches/). One worker at a time.

  python benchmem.py
"""
import time

from bench import NEXT, POLS, ROUTE
from worker import MAME, ROOT, Worker

MOD = ROOT / "mame-0.289-mem" / "mame.exe"


def run(exe, mem):
    save, load = ("msave", "mload") if mem else ("save", "load")
    w = Worker(exe)
    w.cmd("newgame"); w.cmd("level 7")
    for d in ROUTE:
        w.cmd(f"seg {d} E 0")
    held = ROUTE[-1]
    w.cmd(f"{save} bench0")
    steps = {"load": 0.0, "seg": 0.0, "hash": 0.0, "save": 0.0}
    n = 0
    t_all = time.perf_counter()
    for rep in range(16):
        for opt in NEXT:
            for pol in POLS:
                for name, s in (("load", f"{load} bench0 {held}"), ("seg", f"seg {opt} {pol}"),
                                ("hash", "hash"), ("save", f"{save} bench{n % 5 + 1}")):
                    t = time.perf_counter()
                    w.cmd(s)
                    steps[name] += time.perf_counter() - t
                n += 1
    total = (time.perf_counter() - t_all) / n * 1000
    w.close()
    return total, {k: v / n * 1000 for k, v in steps.items()}


def main():
    for label, exe, mem in (("stock, files", MAME, False), ("patched, files", MOD, False),
                            ("patched, memory", MOD, True)):
        total, st = run(exe, mem)
        print(f"{label:16s} " + "  ".join(f"{k} {v:5.2f}" for k, v in st.items()) + f"   total {total:5.2f} ms")


if __name__ == "__main__":
    main()
