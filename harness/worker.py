"""MAME worker process wrapper: one headless MAME running server.lua, driven over pipes."""
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# MAME_EXE overrides the bundled install; ROMs are read from roms/ next to the exe
MAME = Path(os.environ.get("MAME_EXE", ROOT / "mame-0.289" / "mame.exe"))
# our patched build with memory savestate slots (mame-patches/); search.py uses it unless --no-ram
MAME_MEM = ROOT / "mame-0.289-mem" / "mame.exe"
STATE_DIR = ROOT / "state"


def below_normal():
    """Run this process below normal priority, as the MAME/pacemu child processes always did, so
    in-process pacemu threads stay behind foreground work too."""
    if os.name == "nt":
        import ctypes
        k = ctypes.windll.kernel32
        k.GetCurrentProcess.restype = ctypes.c_void_p
        k.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        k.SetPriorityClass(k.GetCurrentProcess(), 0x4000)  # BELOW_NORMAL_PRIORITY_CLASS


class Worker:
    def __init__(self, mame=MAME, idle=False, script=None, extra=()):
        """idle: our patched MAME skips Pac-Man's idle loop (see mame-patches/); stock ignores it.
        script: the Lua server to run (default server.lua beside this file).
        mame="emu": emu_server.py's Server (the same protocol on pacemu, emu/) in this process;
        "emu-proc": the same in a child process."""
        if str(mame) == "emu":  # in this process: commands are calls, no pipe (pacemu frees the GIL)
            from emu_server import Server
            below_normal()
            self.srv = Server(idle)
            self.cmd = self.srv.handle
            self.p = None
            return
        if str(mame) == "emu-proc":  # the same in its own process, over a pipe
            import sys
            self.p = subprocess.Popen(
                [sys.executable, str(Path(__file__).parent / "emu_server.py"), *([] if idle else ["--no-idle"])],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1, cwd=str(ROOT),
                creationflags=getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0))
            line = self._readline()
            assert line == "ready", line
            return
        mame = Path(mame).resolve()  # MAME runs from ROOT, so relative paths would break
        # MAME persists toggles/DIPs in cfg; always start from factory defaults
        try:
            (ROOT / "cfg" / "pacman.cfg").unlink(missing_ok=True)
        except PermissionError:
            pass  # another worker has it open; it was cleared when that one started
        self.p = subprocess.Popen(
            [str(mame), "pacman",
             "-rompath", str(mame.parent / "roms"),
             "-cfg_directory", str(ROOT / "cfg"),
             "-nvram_directory", str(ROOT / "nvram"),
             "-state_directory", str(STATE_DIR),
             "-video", "none", "-sound", "none", "-nothrottle", "-skip_gameinfo",
             "-autoboot_script", str(script or Path(__file__).parent / "server.lua"), *extra],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, bufsize=1, cwd=str(ROOT),
            # the patched build's speed/size switches (see mame-patches/); set PACMAN_NORENDER=0 to record video
            env={**os.environ, "PACMAN_IDLESKIP": "1" if idle else "0",
                 **{k: os.environ.get(k, "1") for k in ("PACMAN_SMALLSTATE", "PACMAN_NOAUDIO", "PACMAN_NORENDER")}},
            # searches run 10 unthrottled MAMEs; keep them behind foreground work
            creationflags=getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0))
        line = self._readline()
        assert line == "ready", line

    def _readline(self):
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError("MAME exited")
            line = line.strip()
            # MAME itself may print other things; protocol lines are the only ones we expect
            if line:
                return line

    def cmd(self, s):
        self.p.stdin.write(s + "\n")
        self.p.stdin.flush()
        return self._readline()

    def close(self):
        if self.p is None:
            return
        try:
            self.p.stdin.write("quit\n"); self.p.stdin.flush()
            self.p.wait(timeout=10)
        except Exception:
            self.p.kill()


if __name__ == "__main__":
    import time
    w = Worker()
    print(w.cmd("newgame"))
    print(w.cmd("save t_start"))
    print(w.cmd("peek"))
    t = time.time()
    # left to the first junction, then up
    for d in ["U", "R", "U", "L"]:
        print(d, w.cmd(f"seg {d} E 0"))
    print("4 segs in", time.time() - t)
    t = time.time()
    for i in range(50):
        w.cmd("load t_start"); w.cmd("seg U E 0"); w.cmd(f"save t_x{i % 5}")
    print("50 load+seg+save in", time.time() - t)
    w.close()

