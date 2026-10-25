"""video_route.py <route.json> <level> <name> [--annotate]: record a route played exactly on time in stock MAME 0.289
(replay_route.play, so "x" turn-backs and late presses like "R9" work) to snap/<name>.avi, then
videos/<name>.mp4 with ffmpeg. --annotate adds one line under the maze: the move number and press (late presses like
"right 9 frames late" in yellow) and the frame count."""
import json, subprocess, sys
from pathlib import Path
from replay_route import play
from search import Pool, make_starts, cleanup, tokens

ROOT = Path(__file__).resolve().parent.parent
route, level, name = json.load(open(sys.argv[1]))["route"], int(sys.argv[2]), sys.argv[3]
annotate = "--annotate" in sys.argv
pool = Pool(1)
start = make_starts(pool, [level])[0]


class Srv:  # replay_route.play talks to an emu_server-style handle()
    def __init__(self, w):
        self.handle = w.cmd


ends = []  # frame (from the start state's load) each move ends on


def run(w):
    w.cmd(f"load {start} L")
    w.cmd(f"rec {name}.avi")
    out = play(Srv(w), route, lambda i, m, st, fr: ends.append(fr))
    w.cmd("wait 240")
    w.cmd("rec")
    return out, ends


out, ends = pool.submit(run).result()  # (ends comes back: the pool may run this elsewhere)
print(out, flush=True)
pool.close()
cleanup(set(), "*")


def esc(s):
    return s.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace(",", "\\,")


vf = "scale=iw*3:ih*3:flags=neighbor"
if annotate:
    FONT = "C\\:/Windows/Fonts/consola.ttf"
    BAR, SIZE = 60, 28
    parts = [vf, f"pad=iw:ih+{BAR}:0:0:color=black"]
    toks, word = tokens(route), {"L": "left", "R": "right", "U": "up", "D": "down"}
    y = f"h-{BAR}+(({BAR}-{SIZE})/2)"
    for i, m in enumerate(toks):
        a, b = (ends[i - 1] if i else 0), ends[i] - 1
        if m[0] == "x":
            what, color = "turn back", "white"
        elif len(m) > 1:
            what, color = f"{word[m[0]]} {m[1:]} frame{'s' if m[1:] != '1' else ''} late", "yellow"
        else:
            what, color = word[m], "white"
        parts.append(f"drawtext=fontfile='{FONT}':text='{esc(f'move {i + 1}  {what}')}':x=24:y={y}:"
                     f"fontsize={SIZE}:fontcolor={color}:enable='between(n,{a},{b})'")
    parts.append(f"drawtext=fontfile='{FONT}':text='%{{eif\\:n\\:d}} fr':x=w-tw-24:y={y}:fontsize={SIZE}:"
                 f"fontcolor=white")
    script = ROOT / "snap" / f"{name}.filter"
    script.write_text(",\n".join(parts))
    vargs = ["-filter_script:v", str(script)]
else:
    vargs = ["-vf", vf]
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(ROOT / "snap" / f"{name}.avi"), *vargs,
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-c:a", "aac",
                str(ROOT / "videos" / f"{name}.mp4")], check=True)
print("videos/" + name + ".mp4")
