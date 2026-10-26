"""video_walk.py <best/L21_speed_NNNN.json> <name> [--annotate]: record a walk route (per-frame joystick "inputs", as
reorder.py / save_best.py store them) in stock MAME 0.289 to snap/<name>.avi, then videos/<name>.mp4 with ffmpeg.
--annotate adds a bar under the maze with the joystick direction held on each frame and the route's frame count
(1 on the start state, stopping at the clear). --encode-only reuses snap/<name>.avi (video frame 0 is the start state,
input i is held on video frame i + 1)."""
import json, subprocess, sys
from itertools import groupby
from pathlib import Path
from search import Pool, make_starts, cleanup

ROOT = Path(__file__).resolve().parent.parent
d, name = json.load(open(sys.argv[1])), sys.argv[2]
annotate = "--annotate" in sys.argv
runs = [(k, len(list(g))) for k, g in groupby(d["inputs"])]


if "--encode-only" not in sys.argv:
    pool = Pool(1)
    start = make_starts(pool, [21])[0]

    def run(w):
        w.cmd(f"load {start} L")
        w.cmd(f"rec {name}.avi")
        f0 = int(w.cmd("peek").split()[1][2:])
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
    FONT = r"C\:/Windows/Fonts/consola.ttf"
    BAR, SIZE = 60, 26
    y = f"h-{BAR}+(({BAR}-{SIZE})/2)"
    ARROW = {"U": "up ↑", "D": "down ↓", "L": "left ←", "R": "right →", None: "none"}
    parts = [vf, f"pad=iw:ih+{BAR}:0:0:color=black",
             f"drawtext=fontfile='{FONT}':text='stick':x=24:y={y}:fontsize={SIZE}:fontcolor=gray"]
    i = 0
    for k, n in runs:  # input i is held on video frame i + 1
        parts.append(f"drawtext=fontfile='{FONT}':text='{ARROW[k]}':x=24+{SIZE}*4:y={y}:fontsize={SIZE}:"
                     f"fontcolor=yellow:enable='between(n,{i + 1},{i + n})'")
        i += n
    parts.append(f"drawtext=fontfile='{FONT}':text='%{{eif\\:min(n+1,{d['frames']})\\:d}} / {d['frames']} fr':"
                 f"x=w-tw-24:y={y}:fontsize={SIZE}:fontcolor=white")
    script = ROOT / "snap" / f"{name}.filter"
    script.write_text(",\n".join(parts), encoding="utf-8")
    vargs = ["-filter_script:v", str(script)]
else:
    vargs = ["-vf", vf]
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(ROOT / "snap" / f"{name}.avi"), *vargs,
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-c:a", "aac",
                str(ROOT / "videos" / f"{name}.mp4")], check=True)
print("videos/" + name + ".mp4")
