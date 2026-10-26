"""record_inp.py <best/L21_speed_NNNN.json> <out.inp>: record a walk route's per-frame joystick as a MAME 0.289 .inp
(written to best/), from power-on: coin, start, best/L21_skip.lua skips to level 21, then the route
(record_inp.lua). Then plays the .inp back with only L21_skip.lua and checks it ends the same way."""
import json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAME = ROOT / "mame-0.289" / "mame.exe"
d, out = json.load(open(sys.argv[1])), sys.argv[2]
inp = ROOT / "snap" / (Path(out).stem + ".inputs.txt")
inp.write_text("\n".join(k or "-" for k in d["inputs"]) + "\n")
(ROOT / "cfg" / "pacman.cfg").unlink(missing_ok=True)
base = [str(MAME), "pacman", "-rompath", str(MAME.parent / "roms"), "-cfg_directory", str(ROOT / "cfg"),
        "-nvram_directory", str(ROOT / "nvram"), "-input_directory", str(ROOT / "best"), "-noplugins",
        "-video", "none", "-sound", "none", "-nothrottle", "-skip_gameinfo"]
r = subprocess.run(base + ["-record", out, "-autoboot_script", str(Path(__file__).parent / "record_inp.lua")],
                   env={**os.environ, "PACMAN_INPUTS": str(inp)}, capture_output=True, text=True, cwd=str(ROOT))
print("record:", [l for l in r.stdout.splitlines() if l.startswith(("CLEAR", "DEAD"))])
# playback with only the skip script, checked by a tiny watcher that prints the same CLEAR line
watch = ROOT / "snap" / "inp_watch.lua"
watch.write_text(f"""dofile([[{ROOT / 'best' / 'L21_skip.lua'}]])
local mem = manager.machine.devices[":maincpu"].spaces["program"]
local function rd(a) return mem:read_u8(a) end
local function bcd(a) local v = rd(a); return (v >> 4) * 10 + (v & 15) end
local t0, done = nil, false
watch_sub = emu.add_machine_frame_notifier(function()
  if done then return end
  if not t0 then
    if rd(0x4E00) == 3 and rd(0x4E04) == 3 and rd(0x4E13) + 1 == 21 then t0 = 0 end
    return
  end
  t0 = t0 + 1
  if rd(0x4DA5) ~= 0 then print("DEAD i=" .. t0); done = true
  elseif rd(0x4E0E) == 244 then
    print(string.format("CLEAR f=%d score=%d", t0, bcd(0x4E82) * 10000 + bcd(0x4E81) * 100 + bcd(0x4E80))); done = true
  end
end)
""")
(ROOT / "cfg" / "pacman.cfg").unlink(missing_ok=True)
p = subprocess.run(base + ["-playback", out, "-exit_after_playback", "-autoboot_script", str(watch)],
                   capture_output=True, text=True, cwd=str(ROOT))
print("playback:", [l for l in p.stdout.splitlines() if l.startswith(("CLEAR", "DEAD"))])
