"""route_trace.py <route json> <level> <trace prefix>: play a finished route in stock MAME (newgame,
level, then every move on time like the search) with PACMAN_TRACE set, for compare.py."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "harness"))
from search import parse_seg  # noqa: E402
from worker import MAME, Worker  # noqa: E402

route, level, prefix = json.load(open(sys.argv[1]))["route"], int(sys.argv[2]), sys.argv[3]
os.environ["PACMAN_TRACE"] = str(Path(prefix).resolve())
w = Worker(MAME)
print(w.cmd("newgame"), w.cmd(f"level {level}"))
for i, d in enumerate(route):
    r = parse_seg(w.cmd(f"seg {d} E 0"))
    if r["st"] not in ("ok", "clear"):
        print(f"{r['st']} on move {i + 1} at {r['tile']}, {r['dots']} dots")
        break
else:
    print("route done:", r["st"], r["dots"], "dots")
w.cmd("wait 120")
w.close()
