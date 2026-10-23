"""Time each harness command inside the search's real per-child sequence (load, seg, hash, save),
to see where a search's time goes.

  python bench.py            (one worker, level 7, ~1 minute)
"""
import time

from worker import Worker

ROUTE = "LLDLLDRULURULURDLDRRUU"  # into level 7's maze, away from the start
NEXT = "ULR"  # options from there, with a few press timings each
POLS = ["E 0", "4 1", "4 2", "4 3", "4 4"]


def main():
    w = Worker()
    w.cmd("newgame"); w.cmd("level 7")
    held = "L"
    for d in ROUTE:
        w.cmd(f"seg {d} E 0"); held = d
    w.cmd("save bench0")
    steps = {"load": 0.0, "seg": 0.0, "hash": 0.0, "save": 0.0}
    frames, n = 0, 0
    t_all = time.perf_counter()
    for rep in range(8):
        for opt in NEXT:
            for pol in POLS:
                for name, s in (("load", f"load bench0 {held}"), ("seg", f"seg {opt} {pol}"),
                                ("hash", "hash"), ("save", f"save bench{n % 5 + 1}")):
                    t = time.perf_counter()
                    out = w.cmd(s)
                    steps[name] += time.perf_counter() - t
                    if name == "seg":
                        frames += int(out.split()[1])
                n += 1
    total = (time.perf_counter() - t_all) / n * 1000
    print(f"{n} children, {frames / n:.1f} frames per seg on average")
    for name, t in steps.items():
        ms = t / n * 1000
        print(f"  {name:5s} {ms:6.2f} ms  {ms / total:5.1%}")
    print(f"  total {total:6.2f} ms per child")
    w.close()


if __name__ == "__main__":
    main()
