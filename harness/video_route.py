"""video_route.py <route.json> <level> <name>: record a route played exactly on time in stock MAME 0.289
(replay_route.play, so "x" turn-backs and late presses like "R9" work) to snap/<name>.avi, then
videos/<name>.mp4 with ffmpeg."""
import json, subprocess, sys
from pathlib import Path
from replay_route import play
from search import Pool, make_starts, cleanup

ROOT = Path(__file__).resolve().parent.parent
route, level, name = json.load(open(sys.argv[1]))["route"], int(sys.argv[2]), sys.argv[3]
pool = Pool(1)
start = make_starts(pool, [level])[0]


class Srv:  # replay_route.play talks to an emu_server-style handle()
    def __init__(self, w):
        self.handle = w.cmd


def run(w):
    w.cmd(f"load {start} L")
    w.cmd(f"rec {name}.avi")
    out = play(Srv(w), route)
    w.cmd("wait 240")
    w.cmd("rec")
    return out


print(pool.submit(run).result(), flush=True)
pool.close()
cleanup(set(), "*")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(ROOT / "snap" / f"{name}.avi"), "-vf",
                "scale=iw*3:ih*3:flags=neighbor", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-c:a", "aac",
                str(ROOT / "videos" / f"{name}.mp4")], check=True)
print("videos/" + name + ".mp4")
