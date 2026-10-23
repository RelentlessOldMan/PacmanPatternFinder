"""replay_human.py <watch log> <route> [variant ...]: replay a watched game's route in MAME with the
player's own lateness on each turn (frames from entering the turn tile to the turn, from the log), then
again with chosen turns put back on time, to find the press that killed.

A variant is a comma list of turn numbers to press on time ("-" = none, "all" = every turn on time)."""
import re
import sys

from search import parse_seg
from worker import MAME_MEM, Worker

OFF = 1
LINE = re.compile(r"f=(\d+) L=(\d+) t=(-?\d+),(-?\d+) d=(\d)")


def lateness(path):
    rows = [tuple(map(int, m.groups())) for m in map(LINE.match, open(path)) if m]
    out, ent, prev = [], rows[0][0], None
    for f, lv, c, r, d in rows:
        if prev and (c, r) != prev[1:3]:
            ent = f
        if prev and d != prev[3]:
            out.append(f - ent)
        prev = (f, c, r, d)
    return rows[0][1], out


def main():
    global OFF
    log, route = sys.argv[1], sys.argv[2]
    if sys.argv[3].startswith("off="):
        OFF = int(sys.argv.pop(3)[4:])
    level, late = lateness(log)
    w = Worker(MAME_MEM, idle=True)
    w.cmd("newgame"); w.cmd(f"level {level}"); w.cmd("msave start")
    for var in sys.argv[3:] or ["-"]:
        fix = set(range(1, 999)) - {int(x) for x in var[5:].split(",")} if var.startswith("only:") else set(range(1, 999)) if var == "all" else {int(x) for x in var.split(",") if x != "-"}
        w.cmd("mload start L")
        held, turn, res = "L", 0, "survived"
        for i, d in enumerate(route):
            if d != held:
                turn += 1
                k = 0 if turn in fix else max(0, late[turn - 1] - OFF) if turn <= len(late) else 0
                r = parse_seg(w.cmd(f"seg {d} 4 {k}" if k else f"seg {d} E 0"))
            else:
                r = parse_seg(w.cmd(f"seg {d} E 0"))
            held = d
            if r["st"] not in ("ok", "clear"):
                res = f"{r['st']} on move {i + 1} at {r['tile']}, {r['dots']} dots"
                break
        print(f"on time: {var:8s} -> {res}", flush=True)
    w.close() if hasattr(w, "close") else None


if __name__ == "__main__":
    main()
