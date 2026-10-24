"""compare.py <trace prefix> [vbl_offset]: play a MAME trace's inputs in pacemu and compare RAM
(0x4000-0x4FFF) with MAME's at every frame. Prints the first differing frame and bytes.
A trace is from emu/trace.lua or from the harness with PACMAN_TRACE set (harness/lib.lua); its
"poke" lines are Lua memory writes made at that frame notifier, applied here at the same point."""
import sys
from emu import Pacman

prefix = sys.argv[1]
m = Pacman(int(sys.argv[2])) if len(sys.argv) > 2 else Pacman()
frames, pokes = [], {}
for l in open(prefix + ".txt"):
    r = l.split()
    if r[0] == "poke":
        pokes.setdefault(len(frames) - 1, []).append((int(r[1], 16), int(r[2], 16)))
    else:
        frames.append(r)
ram = open(prefix + ".ram", "rb").read()
in0 = in1 = 0xFF
first = None
split = 0  # frames where MAME stopped partway through an instruction's writes
for f, r in enumerate(frames):
    if r[1] != "-": in0 = int(r[1].split("/")[0], 16)
    if r[2] != "-": in1 = int(r[2].split("/")[0], 16)
    m.frame(in0, in1)
    want, views = ram[f * 4096:(f + 1) * 4096], m.boundary_views()
    if want in views:
        split += want != views[0]
    else:
        got = views[0]
        diff = [i for i in range(4096) if want[i] != got[i]]
        print(f"frame {f}: {len(diff)} bytes differ, emu PC {m.pc:04X}")
        print("  ", " ".join(f"{0x4000 + i:04X}:{want[i]:02X}/{got[i]:02X}" for i in diff[:16]))
        first = f
        break
    for a, v in pokes.get(f, ()):
        m.poke(a, v)
print("identical through frame", (first if first is not None else len(frames)) - 1, "of", len(frames),
      "| split instructions", split, "| pokes", sum(map(len, pokes.values())), "| inputs changed mid-frame", sum("/" in r[1] + r[2] for r in frames),
      "| watchdog resets", m.resets)
