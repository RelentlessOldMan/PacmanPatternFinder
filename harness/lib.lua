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
function H.wr(a, v) H.mem:write_u8(a, v) end

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

function H.run(fn)
  local co = coroutine.create(function() fn(); H.machine:exit() end)
  H.sub = emu.add_machine_frame_notifier(function()
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
