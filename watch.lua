-- Watcher: logs a human's live game for watch.py to turn into routes. Doesn't touch the game,
-- except that with PACMAN_LEVEL=n it first skips (unthrottled) to the start of level n by really
-- completing levels, the same way server.lua's to_level does.
-- Log lines: "f=<frame> L=<level> t=<col>,<row> d=<dir 0R 1D 2L 3U> dots=<eaten> lives=<n> st=<4E04>"
-- written whenever the tile or direction changes, plus event lines (START, DEATH, CLEAR, LEVEL).
local HERE = debug.getinfo(1, "S").source:match("^@(.*[/\\])") or "./"
local mem = manager.machine.devices[":maincpu"].spaces["program"]
local function rd(a) return mem:read_u8(a) end

local target = tonumber(os.getenv("PACMAN_LEVEL") or "") or 1
local path = os.getenv("PACMAN_WATCH_LOG") or (HERE .. "watch_" .. os.date("%Y%m%d_%H%M%S") .. ".log")
local out = assert(io.open(path, "w"))
local function log(s) out:write(s .. "\n"); out:flush() end
log("WATCH target_level=" .. target)

local frame, last, was_dead, last_level, skipping = 0, nil, false, nil, false
local function level() return rd(0x4E13) + 1 end
-- 4E00 = 3 is game mode; without it the boot RAM test's patterns can look like play, and writing
-- the dot counter then fails the test and resets the machine over and over
local function playing() return rd(0x4E00) == 3 and rd(0x4E04) == 3 end

sub = emu.add_machine_frame_notifier(function()
  frame = frame + 1
  if not playing() then return end
  -- skip ahead: mark the level complete and let the game advance, at full emulation speed
  if level() < target then
    if not skipping then skipping = true; manager.machine.video.throttled = false end
    if rd(0x4E0E) < 244 then mem:write_u8(0x4E0E, 244) end
    return
  end
  if skipping then skipping = false; manager.machine.video.throttled = true end
  local lv = level()
  if lv ~= last_level then log(string.format("LEVEL %d f=%d", lv, frame)); last_level = lv; last = nil end
  local dead = rd(0x4DA5) ~= 0
  if dead and not was_dead then
    log(string.format("DEATH f=%d L=%d t=%d,%d dots=%d", frame, lv, 59 - rd(0x4D3A), rd(0x4D39) - 33, rd(0x4E0E)))
  end
  was_dead = dead
  if dead then last = nil; return end
  local key = string.format("L=%d t=%d,%d d=%d", lv, 59 - rd(0x4D3A), rd(0x4D39) - 33, rd(0x4D30))
  if key ~= last then
    log(string.format("f=%d %s dots=%d lives=%d st=%d", frame, key, rd(0x4E0E), rd(0x4E14), rd(0x4E04)))
    last = key
  end
end)
