-- record_inp.lua: run by record_inp.py with -record. Loads best/L21_skip.lua (the same skip the playback uses),
-- coins up and starts a game, then once level 21 is in play holds left one frame (where server.lua's start state
-- is) and plays the per-frame joystick from PACMAN_INPUTS (one line per frame: U D L R or - for centered).
-- Prints "CLEAR f=<frames since the start state's load + 1> score=<n>" or "DEAD", then exits 240 frames later.
local HERE = debug.getinfo(1, "S").source:match("^@(.*[/\\])") or "./"
dofile(HERE .. "../best/L21_skip.lua")
local m = manager.machine
local mem = m.devices[":maincpu"].spaces["program"]
local function rd(a) return mem:read_u8(a) end
local fields = {}
for _, port in pairs(m.ioport.ports) do for name, f in pairs(port.fields) do fields[name] = f end end
local JOY = { U = "P1 Up", D = "P1 Down", L = "P1 Left", R = "P1 Right" }
local function joy(d) for k, name in pairs(JOY) do fields[name]:set_value(k == d and 1 or 0) end end
local inputs = {}
for line in io.lines(os.getenv("PACMAN_INPUTS")) do inputs[#inputs + 1] = line end
local function bcd(a) local v = rd(a); return (v >> 4) * 10 + (v & 15) end
local function score() return bcd(0x4E82) * 10000 + bcd(0x4E81) * 100 + bcd(0x4E80) end

local frame, phase, t0, done_at = 0, "boot", nil, nil
local taps = { [600] = { "Coin 1", 1 }, [605] = { "Coin 1", 0 }, [670] = { "1 Player Start", 1 }, [675] = { "1 Player Start", 0 } }
record_sub = emu.add_machine_frame_notifier(function()
  frame = frame + 1
  local t = taps[frame]
  if t then fields[t[1]]:set_value(t[2]) end
  if phase == "boot" then
    if frame > 675 and rd(0x4E00) == 3 and rd(0x4E04) == 3 and rd(0x4E13) + 1 == 21 then
      joy("L"); phase, t0 = "run", frame
    end
  elseif phase == "run" then
    local i = frame - t0
    if rd(0x4DA5) ~= 0 then print("DEAD i=" .. i); phase, done_at = "end", frame
    elseif rd(0x4E0E) == 244 then print(string.format("CLEAR f=%d score=%d", i, score())); phase, done_at = "end", frame
    else local d = inputs[i]; joy(d ~= "-" and d or nil) end
  elseif frame - done_at >= 240 then
    m:exit()
  end
end)
