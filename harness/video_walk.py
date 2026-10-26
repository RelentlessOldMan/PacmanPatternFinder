"""video_walk.py <best/L21_speed_NNNN.json> <name> [--annotate]: record a walk route (per-frame joystick "inputs", as
reorder.py / save_best.py store them) in stock MAME 0.289 to snap/<name>.avi, then videos/<name>.mp4 with ffmpeg.
--annotate adds a bar under the maze with the held direction (late presses' waits are just held directions) and the
frame count."""
import json, subprocess, sys
from itertools import groupby
from pathlib import Path
from search import Pool, make_starts, cleanup

ROOT = Path(__file__).resolve().parent.parent
d, name = json.load(open(sys.argv[1])), sys.argv[2]
annotate = "--annotate" in sys.argv
runs = [(k, len(list(g))) for k, g in groupby(d["inputs"])]
pool = Pool(1)
start = make_starts(pool, [21])[0]


def run(w):
    w.cmd(f"load {start} L")
    w.cmd(f"rec {name}.avi")
    f0 = int(w.cmd("peek").split()[1][2:])
    out = None
    for k, n in runs:
        w.cmd(f"joy {k or ''}")
        w.cmd(f"wait {n}")
    p = w.cmd("peek")
    w.cmd("wait 240")
    w.cmd("rec")
    return p, f0


p, f0 = pool.submit(run).result()
print(p, "frames since load + 1:", int(p.split()[1][2:]) - f0 + 1, flush=True)
pool.close()
cleanup(set(), "*")

vf = "scale=iw*3:ih*3:flags=neighbor"
if annotate:
    FONT = "C\:/Windows/Fonts/consola.ttf"
    BAR, SIZE = 60, 26
    y = f"h-{BAR}+(({BAR}-{SIZE})/2)"
    parts = [vf, f"pad=iw:ih+{BAR}:0:0:color=black",
             f"drawtext=fontfile='{FONT}':text='level 21  both fruits':x=24:y={y}:fontsize={SIZE}:fontcolor=white",
             f"drawtext=fontfile='{FONT}':text='%{{eif\:n\:d}} fr':x=w-tw-24:y={y}:fontsize={SIZE}:fontcolor=white"]
    script = ROOT / "snap" / f"{name}.filter"
    script.write_text(",\n".join(parts))
    vargs = ["-filter_script:v", str(script)]
else:
    vargs = ["-vf", vf]
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(ROOT / "snap" / f"{name}.avi"), *vargs,
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-c:a", "aac",
                str(ROOT / "videos" / f"{name}.mp4")], check=True)
print("videos/" + name + ".mp4")
