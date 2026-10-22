"""MAME worker process wrapper: one headless MAME running server.lua, driven over pipes."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAME = ROOT / "mame-0.289" / "mame.exe"
STATE_DIR = ROOT / "state"


class Worker:
    def __init__(self, mame=MAME):
        mame = Path(mame)
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
             "-autoboot_script", str(Path(__file__).parent / "server.lua")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, bufsize=1, cwd=str(ROOT))
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

