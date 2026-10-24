"""Python side of pacemu.dll (see pacemu.c): Midway Pac-Man without video or sound."""
import ctypes
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROM_ZIP = HERE.parent / "mame-0.289" / "roms" / "pacman.zip"
PROGRAM = ["pacman.6e", "pacman.6f", "pacman.6h", "pacman.6j"]  # 0x0000-0x3FFF

_dll = ctypes.CDLL(str(HERE / "pacemu.dll"))
_dll.pm_new.restype = ctypes.c_void_p
_dll.pm_new.argtypes = [ctypes.c_char_p, ctypes.c_int32]
for name in ("pm_free", "pm_frame"):
    getattr(_dll, name).argtypes = [ctypes.c_void_p]
_dll.pm_set_inputs.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
_dll.pm_ram.restype = ctypes.POINTER(ctypes.c_uint8 * 0x1000)
_dll.pm_ram.argtypes = [ctypes.c_void_p]
_dll.pm_save.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_dll.pm_load.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
for name in ("pm_frames", "pm_resets", "pm_pc"):
    getattr(_dll, name).argtypes = [ctypes.c_void_p]
_dll.pm_regs.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint16 * 8)]
_dll.pm_edge.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
STATE_SIZE = _dll.pm_state_size()
REGS = ("AF", "BC", "DE", "HL", "IX", "IY", "SP", "PC")


def rom(zip_path=ROM_ZIP):
    with zipfile.ZipFile(zip_path) as z:
        return b"".join(z.read(n) for n in PROGRAM)


class Pacman:
    def __init__(self, vbl_offset=3, rom_bytes=None):
        self.h = _dll.pm_new(rom_bytes or rom(), vbl_offset)
        self._ram = _dll.pm_ram(self.h).contents

    def __del__(self):
        if getattr(self, "h", None):
            _dll.pm_free(self.h)

    def frame(self, in0=0xFF, in1=0xFF):
        _dll.pm_set_inputs(self.h, in0, in1)
        _dll.pm_frame(self.h)

    def ram(self):
        """0x4000-0x4FFF as bytes."""
        return bytes(self._ram)

    def rd(self, a):
        return self._ram[a - 0x4000]

    def edge_writes(self):
        """[(addr, old value)] written by the instruction that crossed the last frame end, oldest first."""
        out, i, a, o = [], 0, ctypes.c_int(), ctypes.c_int()
        while _dll.pm_edge(self.h, i, ctypes.byref(a), ctypes.byref(o)):
            out.append((a.value, o.value)); i += 1
        return out

    def boundary_views(self):
        """RAM as MAME could show it at the frame notifier: with the crossing instruction's writes
        all made, all but the last, ..., none (MAME stops it partway)."""
        ram = bytearray(self.ram())
        views = [bytes(ram)]
        for a, old in reversed(self.edge_writes()):
            ram[a - 0x4000] = old
            views.append(bytes(ram))
        return views

    def poke(self, a, v):
        a &= ~0xA000  # RAM mirrors
        assert 0x4000 <= a < 0x5000 and not 0x4800 <= a < 0x4C00, hex(a)
        self._ram[a - 0x4000] = v

    def save(self):
        buf = ctypes.create_string_buffer(STATE_SIZE)
        _dll.pm_save(self.h, buf)
        return buf.raw

    def load(self, state):
        _dll.pm_load(self.h, state)

    def regs(self):
        r = (ctypes.c_uint16 * 8)()
        _dll.pm_regs(self.h, ctypes.byref(r))
        return dict(zip(REGS, r))

    @property
    def resets(self):
        return _dll.pm_resets(self.h)

    @property
    def pc(self):
        return _dll.pm_pc(self.h)
