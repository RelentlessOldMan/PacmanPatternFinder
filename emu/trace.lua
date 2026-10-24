-- trace.lua: record a deterministic MAME run for checking pacemu against it.
-- Env PACMAN_TRACE = output prefix; PACMAN_TRACE_FRAMES = frames to record (default 12000).
-- Writes <prefix>.ram: 4096 bytes of 0x4000-0x4FFF at every frame notifier, and <prefix>.txt:
-- per frame "frame IN0 IN1 PC time AF= .. SP=" where IN0/IN1 are the values the CPU read that frame
-- ("-" if not read; "a/b" if it read different values).
-- Inputs: boot, coin, start (like server.lua newgame), then the joystick changes every 8-40 frames
-- from a fixed pseudo-random sequence.
package.path = package.path .. ";" .. os.getenv("PACMAN_HARNESS") .. "/?.lua"
local H = require("lib")
local prefix = os.getenv("PACMAN_TRACE")
local nframes = tonumber(os.getenv("PACMAN_TRACE_FRAMES") or "12000")
local ram = assert(io.open(prefix .. ".ram", "wb"))
local txt = assert(io.open(prefix .. ".txt", "w"))
local cpu = H.machine.devices[":maincpu"]

local seen = { [0] = {}, [1] = {} }
local function note(port, v)
  local s = seen[port]
  if s[#s] ~= v then s[#s + 1] = v end
end
local t0 = H.mem:install_read_tap(0x5000, 0x5000, "in0", function(o, d, m) note(0, d) end)
local t1 = H.mem:install_read_tap(0x5040, 0x5040, "in1", function(o, d, m) note(1, d) end)

local function fmt(s)
  if #s == 0 then return "-" end
  local o = {}
  for i, v in ipairs(s) do o[i] = string.format("%02X", v) end
  return table.concat(o, "/")
end

local f = 0
local function record()
  local b = {}
  for a = 0x4000, 0x4FFF do b[#b + 1] = string.char(H.rd(a)) end
  ram:write(table.concat(b))
  local st = cpu.state
  txt:write(string.format("%d %s %s %04X %.9f AF=%04X BC=%04X DE=%04X HL=%04X IX=%04X IY=%04X SP=%04X\n", f,
    fmt(seen[0]), fmt(seen[1]), st["PC"].value, manager.machine.time:as_double(), st["AF"].value, st["BC"].value,
    st["DE"].value, st["HL"].value, st["IX"].value, st["IY"].value, st["SP"].value))
  seen[0], seen[1] = {}, {}
  f = f + 1
end

H.run(function()
  local seed = 12345
  local function rnd(n) seed = (seed * 1103515245 + 12345) % 2147483648; return seed % n end
  local plan = {}
  plan[600] = { "Coin 1", 1 }; plan[605] = { "Coin 1", 0 }
  plan[670] = { "1 Player Start", 1 }; plan[675] = { "1 Player Start", 0 }
  local nextjoy, dirs = 800, { nil, "U", "D", "L", "R" }
  while f < nframes do
    if plan[f] then H.fields[plan[f][1]]:set_value(plan[f][2]) end
    if f == nextjoy then
      H.joy(dirs[rnd(5) + 1]); nextjoy = f + 8 + rnd(33)
    end
    record()
    H.wait(1)
  end
  t0:remove(); t1:remove(); ram:close(); txt:close()
end)
