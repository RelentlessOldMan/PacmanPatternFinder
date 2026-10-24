-- Shared harness helpers: coroutine-driven scripting on top of MAME's frame notifier.
-- Script code calls H.wait(n) etc. and runs one emulated frame per yield.
local H = {}

H.machine = manager.machine
H.mem = H.machine.devices[":maincpu"].spaces["program"]
H.frame = 0
H.lua_ticks = 0 -- profiling: time spent running this script's frame steps

local fields = {}
for _, port in pairs(H.machine.ioport.ports) do
  for name, f in pairs(port.fields) do fields[name] = f end
end
H.fields = fields

function H.rd(a) return H.mem:read_u8(a) end
function H.wr(a, v) if H.trace_poke then H.trace_poke(a, v) end H.mem:write_u8(a, v) end

function H.wait(n)
  for _ = 1, (n or 1) do coroutine.yield() end
end

-- Joystick: dir is one of "U","D","L","R" or nil (centered).
local JOY = { U = "P1 Up", D = "P1 Down", L = "P1 Left", R = "P1 Right" }
H.joy_dir = nil
function H.joy(dir)
  H.joy_dir = dir
  for d, name in pairs(JOY) do fields[name]:set_value(d == dir and 1 or 0) end
end

function H.tap(name, frames)
  fields[name]:set_value(1); H.wait(frames or 5)
  fields[name]:set_value(0); H.wait(frames or 5)
end

-- Save/load are scheduled by MAME; they complete at the next frame boundary.
function H.save(name) H.machine:save(name); H.wait(1) end
-- A single load occasionally restores one frame short (seen as Pac-Man one tile back); loading
-- twice has always landed exactly on the saved state.
function H.load(name) H.machine:load(name); H.wait(1); H.machine:load(name); H.wait(1) end

-- In-memory slots (only in our patched MAME, see mame-patches/): the same scheduled save/load at
-- the same frame boundary, but into this MAME's RAM, uncompressed, with no file.
H.has_mem = H.machine.mem_save ~= nil
function H.msave(slot) H.machine:mem_save(slot); H.wait(1) end
function H.mload(slot) H.machine:mem_load(slot); H.wait(1); H.machine:mem_load(slot); H.wait(1) end

-- RAM map (verified empirically in probe runs; coordinates are the game's internal ones:
-- internal X grows to the LEFT on screen, internal Y grows DOWN).
H.A = {
  ghost_pos = 0x4D00,   -- 4 ghosts x (Y,X) pixel pairs: blinky, pinky, inky, clyde
  pac_y = 0x4D08, pac_x = 0x4D09,
  pac_ty = 0x4D39, pac_tx = 0x4D3A,
  level = 0x4E13, lives = 0x4E14,
}

-- PACMAN_TRACE=<prefix> (for checking emu/pacemu against MAME): at every frame notifier write
-- 0x4000-0x4FFF to <prefix>.ram and "frame IN0 IN1" to <prefix>.txt (the values the CPU read since the
-- last notifier, "-" if none, "a/b" if they changed), then one "poke addr value" line per H.wr.
local trace
if os.getenv("PACMAN_TRACE") then
  local pre = os.getenv("PACMAN_TRACE")
  trace = { ram = assert(io.open(pre .. ".ram", "wb")), txt = assert(io.open(pre .. ".txt", "w")),
    seen = { [0] = {}, [1] = {} }, f = 0 }
  local function note(p, v) local s = trace.seen[p]; if s[#s] ~= v then s[#s + 1] = v end end
  trace.taps = { H.mem:install_read_tap(0x5000, 0x5000, "tr0", function(o, d) note(0, d) end),
    H.mem:install_read_tap(0x5040, 0x5040, "tr1", function(o, d) note(1, d) end) }
  local function fmt(s)
    if #s == 0 then return "-" end
    local o = {}
    for i, v in ipairs(s) do o[i] = string.format("%02X", v) end
    return table.concat(o, "/")
  end
  function trace.record()
    trace.ram:write(H.mem:read_range(0x4000, 0x4FFF, 8))
    trace.txt:write(string.format("%d %s %s\n", trace.f, fmt(trace.seen[0]), fmt(trace.seen[1])))
    trace.seen[0], trace.seen[1] = {}, {}
    trace.f = trace.f + 1
    trace.ram:flush(); trace.txt:flush()
  end
  H.trace_poke = function(a, v) trace.txt:write(string.format("poke %04X %02X\n", a, v)) end
end

function H.run(fn)
  local co = coroutine.create(function() fn(); H.machine:exit() end)
  H.sub = emu.add_machine_frame_notifier(function()
    if trace then trace.record() end
    H.frame = H.frame + 1
    if coroutine.status(co) == "dead" then return end
    local t = emu.osd_ticks()
    local ok, err = coroutine.resume(co)
    H.lua_ticks = H.lua_ticks + (emu.osd_ticks() - t)
    if not ok then
      print("LUAERROR " .. tostring(err))
      print(debug.traceback(co))
      H.machine:exit()
    end
  end)
end

return H
