"""segb (server.lua) must equal "seg <opt> 4 k; hash; msave" for each k from the same state.

At every move of every best/ route, for all four directions: run k = 1..4 one at a time and
with one segb, compare each seg reply and hash, then load each pair of saved states and play the
route's next move from both (reply and hash again). Needs our patched MAME (memory slots).
"""
import sys
from concurrent.futures import ThreadPoolExecutor

from abtest import JOBS
from worker import ROOT, Worker

EXE = ROOT / "mame-0.289-mem" / "mame.exe"
K = 4


def check(lv, route):
    w = Worker(EXE, True)
    w.cmd("newgame"); w.cmd(f"level {lv}")
    held, n, bad = "L", 0, []
    for i, d in enumerate(route):
        w.cmd("msave t0")
        nxt = route[i + 1] if i + 1 < len(route) else d
        for opt in "UDLR":
            ref = []
            for k in range(1, K + 1):
                w.cmd(f"mload t0 {held}")
                ref.append(w.cmd(f"seg {opt} 4 {k}") + " " + w.cmd("hash").split()[1])
                w.cmd(f"msave r{k}")
            w.cmd(f"mload t0 {held}")
            got = w.cmd(f"segb {opt} 4 " + " ".join(f"b{k}" for k in range(1, K + 1))).split(" | ")
            n += K
            for k in range(1, K + 1):
                a, b = ref[k - 1], got[k - 1]
                if a == b and a.startswith("ok"):
                    # the saved states must play on the same too
                    w.cmd(f"mload r{k} {opt}"); a = w.cmd(f"seg {nxt} E 0") + " " + w.cmd("hash").split()[1]
                    w.cmd(f"mload b{k} {opt}"); b = w.cmd(f"seg {nxt} E 0") + " " + w.cmd("hash").split()[1]
                if a != b:
                    bad.append((i, opt, k, a, b))
        w.cmd(f"mload t0 {held}")
        r = w.cmd(f"seg {d} E 0")
        held = d
        if not r.startswith("ok"):
            break
    w.close()
    return n, bad


def main():
    with ThreadPoolExecutor(int(sys.argv[1]) if len(sys.argv) > 1 else 6) as ex:
        res = list(ex.map(lambda j: check(j[1], j[2]), JOBS))
    n = sum(r[0] for r in res)
    bad = [(JOBS[i][0],) + b for i, r in enumerate(res) for b in r[1]]
    for b in bad[:10]:
        print("DIFF", b)
    print(f"segb vs seg: {n} runs, " + ("ALL SAME" if not bad else f"{len(bad)} DIFFERENT"))


if __name__ == "__main__":
    main()
