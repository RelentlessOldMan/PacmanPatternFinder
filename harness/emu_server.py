"""server.lua's command protocol on pacemu (emu/) instead of MAME: one command per line on stdin, one
reply line on stdout. worker.Worker starts this when given mame="emu". Frame rules: see emu/seg.h.

PACMAN_NOGHOSTS=1 in the environment: ghosts can't touch Pac-Man (ROM patch; for speed floors).

File saves go to state/emu/<name>.sta (raw pacemu states; MAME's go to state/pacman/). Not supported: rec, prof, idle.
"""
import os
import sys
import ctypes
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "emu"))
import emu  # noqa: E402

D = emu._dll
SEGN = 14  # seg reply fields (emu/seg.h)
D.pm_seg.argtypes = [ctypes.c_void_p] + [ctypes.c_int] * 6 + [ctypes.POINTER(ctypes.c_int32 * SEGN)]
D.pm_segb.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                      ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
D.pm_hash.restype = ctypes.c_int64
D.pm_hash.argtypes = [ctypes.c_void_p]
for name, n in (("pm_joy", 1), ("pm_set_idle", 1), ("pm_to_level", 1), ("pm_buttons", 2)):
    getattr(D, name).argtypes = [ctypes.c_void_p] + [ctypes.c_int] * n
D.pm_get_joy.argtypes = [ctypes.c_void_p]
D.pm_mark.argtypes = [ctypes.c_void_p]
D.pm_rom.argtypes = [ctypes.c_void_p]
D.pm_rom.restype = ctypes.POINTER(ctypes.c_uint8)
D.pm_set_maze.argtypes = [ctypes.c_char_p]

LETTER = {"R": 0, "D": 1, "L": 2, "U": 3}
ST = ["none", "ok", "clear", "dead", "miss", "stuck", "timeout", "nonode"]
STATE_DIR = HERE.parent / "state" / "emu"
S = emu.STATE_SIZE


_maze_loaded = False


def load_maze():
    global _maze_loaded
    if _maze_loaded:
        return
    _maze_loaded = True
    rows = [l.rstrip("\n").ljust(28)[:28] for l in open(HERE / "maze.txt")][:31]
    D.pm_set_maze("".join(rows).encode())


class Server:
    def __init__(self, idle=True):
        load_maze()
        self.m = emu.Pacman()
        self.h = self.m.h
        D.pm_set_idle(self.h, 1 if idle else 0)
        self.slots = {}
        self.frame = 0
        self.wait(2)  # lib.lua: the first notifier starts the script, which waits a frame before "ready"
        if os.environ.get("PACMAN_NOGHOSTS"):
            # 0x1763 LD A,B (the ghost on Pac-Man's tile, 0 = none) -> XOR A: no ghost ever touches him.
            # Patched after boot: the boot ROM test would fail on it. States hold no ROM, so this holds across loads.
            # Off during newgame (it hangs with it on, in the attract demo).
            self.rom = D.pm_rom(self.h)
            assert self.rom[0x1763] == 0x78
            self.rom[0x1763] = 0xAF

    # --- frames, joystick, save/load -------------------------------------------------
    def wait(self, n=1):
        f, h = D.pm_frame, self.h
        for _ in range(n):
            f(h)
        self.frame += n

    def joy(self, d):
        D.pm_joy(self.h, -1 if d is None else LETTER[d])

    def held(self):
        j = D.pm_get_joy(self.h)
        return None if j < 0 else "RDLU"[j]

    def save_state(self):
        return self.m.save()

    def msave(self, name):
        self.slots[name] = self.m.save()
        self.wait(1)

    def mload(self, state, held):
        self.joy(held)
        self.m.load(state)
        self.joy(held)
        D.pm_mark(self.h)  # the next seg's ghost count starts at the loaded state
        self.wait(1)

    def rd(self, a):
        return self.m.rd(a)

    def tile(self):
        return 59 - self.rd(0x4D3A), self.rd(0x4D39) - 33

    def gdist(self):
        """Closest ghost to Pac-Man in pixels (|dx| + |dy|), like seg.h ghost_min_dist."""
        x, y = self.rd(0x4D09), self.rd(0x4D08)
        return min(abs(self.rd(0x4D01 + g * 2) - x) + abs(self.rd(0x4D00 + g * 2) - y) for g in range(4))

    def dots(self):
        return self.rd(0x4E0E)

    def tap(self, in0=0xFF, in1=0xFF, frames=5):
        D.pm_buttons(self.h, in0, in1); self.wait(frames)
        D.pm_buttons(self.h, 0xFF, 0xFF); self.wait(frames)

    def score(self):
        b = lambda v: (v >> 4) * 10 + (v & 15)
        return b(self.rd(0x4E80)) + b(self.rd(0x4E81)) * 100 + b(self.rd(0x4E82)) * 10000

    # --- commands ----------------------------------------------------------------------
    def seg_reply(self, o):
        return f"{ST[o[0]]} " + " ".join(str(v) for v in o[1:SEGN])

    def handle(self, line):
        p = line.split()
        cmd, a, b, c = (p + ["", "", "", ""])[:4]
        if cmd == "seg":
            o = (ctypes.c_int32 * SEGN)()
            lag = int(p[3]) if len(p) > 3 else 0
            nxt, nd = (LETTER[p[4][0]], int(p[4][1:] or 0)) if len(p) > 4 and p[4] else (-1, 0)
            D.pm_seg(self.h, LETTER[a], b == "E", 0 if b == "E" else int(b), lag, nxt, nd, ctypes.byref(o))
            self.frame += o[1]
            return self.seg_reply(o)
        if cmd == "hash":
            return f"ok {D.pm_hash(self.h)} f={self.frame}"
        if cmd == "msave":
            self.msave(a); return "ok"
        if cmd == "mload":
            st = self.slots.get(a)
            if st is None:
                return "err mload " + a
            self.mload(st, b or None)
            tc, tr = self.tile(); return f"ok {tc} {tr} {self.dots()}"
        if cmd == "mdrop":
            n = sum(self.slots.pop(s, None) is not None for s in p[1:])
            return f"ok {n} {len(self.slots)}"
        if cmd == "segb":
            names = p[3:]
            K = len(names)
            o = (ctypes.c_int32 * (SEGN * K))()
            hs = (ctypes.c_int64 * K)()
            buf = ctypes.create_string_buffer(S * K)
            D.pm_segb(self.h, LETTER[a], int(b), K, o, hs, buf)
            raw = buf.raw
            out = []
            for k, name in enumerate(names):
                self.slots[name] = raw[S * k:S * (k + 1)]
                out.append(self.seg_reply(o[SEGN * k:SEGN * k + SEGN]) + f" {hs[k]}")
            return " | ".join(out)
        if cmd == "mget":
            st = self.slots.get(a)
            return "ok " + st.hex() if st is not None else "err mget " + a
        if cmd == "mset":
            self.slots[a] = bytes.fromhex(b); return "ok"
        if cmd == "mcopy":
            if c == "in":
                self.slots[b] = (STATE_DIR / f"{a}.sta").read_bytes()
                self.m.load(self.slots[b])
            else:
                if a not in self.slots:
                    return "err mcopy " + a
                (STATE_DIR / f"{b}.sta").write_bytes(self.slots[a])
                self.m.load(self.slots[a])
            self.wait(1)
            return "ok"
        if cmd == "save":
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            (STATE_DIR / f"{a}.sta").write_bytes(self.m.save()); self.wait(1); return "ok"
        if cmd == "load":
            f = STATE_DIR / f"{a}.sta"
            if not f.exists():
                return "err load " + a
            self.mload(f.read_bytes(), b or None)
            tc, tr = self.tile(); return f"ok {tc} {tr} {self.dots()}"
        if cmd == "newgame":
            patch = getattr(self, "rom", None)
            if patch:
                patch[0x1763] = 0x78
            self.wait(600); self.tap(in0=0xDF); self.wait(60); self.tap(in1=0xDF)
            while self.rd(0x4E04) != 3:
                self.wait(1)
            if patch:
                patch[0x1763] = 0xAF
            return f"ok {self.frame}"
        if cmd == "level":
            f0 = D.pm_frames(self.h); D.pm_to_level(self.h, int(a)); self.frame += D.pm_frames(self.h) - f0
            return f"ok {self.rd(0x4E13) + 1}"
        if cmd == "wait":
            self.wait(int(a)); return "ok"
        if cmd == "mem":
            return "ok " + "".join(f"{self.rd(x):02x}" for x in range(int(a, 16), int(a, 16) + int(b)))
        if cmd == "dump":
            return "ok " + "".join(f"{self.rd(x):02x}" for x in range(0x4C00, 0x4FF0))
        if cmd == "peek":
            tc, tr = self.tile()
            return (f"ok f={self.frame} tile={tc},{tr} dir={self.rd(0x4D30)} dots={self.dots()} "
                    f"level={self.rd(0x4E13) + 1} 4E04={self.rd(0x4E04)} score={self.score()}")
        if cmd == "reverse":  # reply mind= the closest ghost (pixels, like seg's mind) on the way
            n = 0
            tc, tr = self.tile()
            mind = self.gdist()
            while (tc, tr) != (int(b), int(c)):
                self.wait(1); n += 1; tc, tr = self.tile(); mind = min(mind, self.gdist())
                if self.rd(0x4DA5) or n > 600:
                    break
            if self.rd(0x4DA5):
                return "dead"
            if n > 600:
                return "timeout"
            self.joy(a); n = 0
            while self.rd(0x4D30) != LETTER[a] and n < 10:
                self.wait(1); n += 1; mind = min(mind, self.gdist())
            if self.rd(0x4DA5):
                return "dead"
            tc, tr = self.tile()
            return f"ok f={self.frame} tile={tc},{tr} dots={self.dots()} mind={mind}"
        return "err " + line


def main():
    idle = "--no-idle" not in sys.argv
    srv = Server(idle)
    out = sys.stdout
    out.write("ready\n"); out.flush()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        if line == "quit":
            break
        out.write(srv.handle(line) + "\n"); out.flush()


if __name__ == "__main__":
    main()
