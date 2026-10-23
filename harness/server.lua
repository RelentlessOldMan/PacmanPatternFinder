-- Command server: reads one command per line on stdin, replies one line on stdout.
-- Driven by search.py. Coordinates: maze col 0..27 (left->right), row 0..30 (top->bottom).
-- this script's own folder, so the harness works wherever it is checked out
local HERE = debug.getinfo(1, "S").source:match("^@(.*[/\\])") or "./"
package.path = HERE .. "?.lua;" .. package.path
local H = require("lib")

-- maze -------------------------------------------------------------------------------
local MAZE = {}
do
  local r = 0
  for line in io.lines(HERE .. "maze.txt") do
    MAZE[r] = line .. string.rep(" ", 28 - #line); r = r + 1
  end
end
local W, NROWS = 28, 31

local function open(c, r)
  if r < 0 or r >= NROWS then return false end
  if c < 0 or c >= W then return r == 14 end -- tunnel
  return MAZE[r]:sub(c + 1, c + 1) ~= "#"
end

-- dir codes match the game's: 0=R 1=D 2=L 3=U
local DC = { [0] = { 1, 0 }, [1] = { 0, 1 }, [2] = { -1, 0 }, [3] = { 0, -1 } }
local LETTER = { R = 0, D = 1, L = 2, U = 3 }
local NAME = { [0] = "R", [1] = "D", [2] = "L", [3] = "U" }

local function wrapc(c) return ((c + 2) % 32) - 2 end -- tunnel spans cols -2..29

-- node = tile where a non-straight move is possible (junction or corner)
local function is_node(c, r)
  if c < 0 or c >= W then return false end
  if not open(c, r) then return false end
  local n = 0
  local ex = {}
  for d = 0, 3 do
    if open(c + DC[d][1], r + DC[d][2]) then n = n + 1; ex[d] = true end
  end
  if n >= 3 then return true end
  if n == 2 and not ((ex[0] and ex[2]) or (ex[1] and ex[3])) then return true end
  return false
end

-- game state -------------------------------------------------------------------------
local function pac_tile()
  return 59 - H.rd(0x4D3A), H.rd(0x4D39) - 33
end
local function pac_px() return H.rd(0x4D09), H.rd(0x4D08) end -- internal x (grows left), y
local function center_px(c, r) return (29 - c) * 8 + 4, (r + 1) * 8 + 4 end

-- signed distance (px) of pac-man before the center of tile (c,r) when moving dir d
local function dist_to(c, r, d)
  local x, y = pac_px()
  local cx, cy = center_px(c, r)
  if d == 1 then return cy - y elseif d == 3 then return y - cy end
  -- horizontal: x wraps at 256 through the tunnel; no straight run is longer than 26 tiles, so
  -- anything beyond 248px ahead is really a few px past the center
  local v = ((d == 2) and (cx - x) or (x - cx)) % 256
  if v > 248 then v = v - 256 end
  return v
end

local function ghost_min_dist()
  local x, y = pac_px()
  local best = 999
  for g = 0, 3 do
    local gy, gx = H.rd(0x4D00 + g * 2), H.rd(0x4D01 + g * 2)
    local dd = math.abs(gx - x) + math.abs(gy - y)
    if dd < best then best = dd end
  end
  return best
end

local function bcd(v) return (v >> 4) * 10 + (v & 15) end
local function score() return bcd(H.rd(0x4E80)) + bcd(H.rd(0x4E81)) * 100 + bcd(H.rd(0x4E82)) * 10000 end
local function dead() return H.rd(0x4DA5) ~= 0 end
-- single-frame score jumps that can only come from a fruit (ghosts are 200/400/800/1600)
FRUIT_POINTS = { [100] = true, [300] = true, [500] = true, [700] = true, [1000] = true,
  [2000] = true, [3000] = true, [5000] = true }
local function dots() return H.rd(0x4E0E) end

-- segment: travel to the next node ahead and leave it heading `want`.
-- policy "E" = press immediately; integer p = press once within p px of node center.
-- lag = extra frames between trigger and press.
-- nxt (optional): press this direction as soon as the turn onto `want` registers, the way a
-- player presses the next turn as soon as they see Pac-Man come round the corner. `lead` is how
-- many frames that is before leaving the node tile, i.e. extra window for the next turn.
local function segment(want, policy, lag, nxt, nxt_delay)
  local d = H.rd(0x4D30)
  local c, r = pac_tile()
  -- find next node ahead (the current tile counts)
  local mc, mr = c, r
  local guard = 0
  while not is_node(mc, mr) do
    mc, mr = wrapc(mc + DC[d][1]), mr + DC[d][2]
    guard = guard + 1
    if guard > 40 then return "nonode", 0, 0, 0, 999, 0, 0 end
  end
  -- pac-man stops dead at a corner's center, so a press "past center" can't happen there
  if policy ~= "E" and not open(mc + DC[d][1], mr + DC[d][2]) and policy < 0 then policy = 0 end
  local f0 = H.frame
  local pressed = false
  local trigger_frame = nil
  local entered = false
  local mind = 999
  local lastx, lasty, still = -1, -1, 0
  -- win: frames from segment start until the turn is no longer "safe early" (4px before center)
  local win = (want == d) and 99 or nil
  local fruits, last_score = 0, score()
  local lead_at = nil
  local function done(st)
    return st, H.frame - f0, mc, mr, mind, win or 0, fruits, lead_at and (H.frame - lead_at) or 0
  end
  while true do
    if not win and dist_to(mc, mr, d) <= 4 then win = H.frame - f0 end
    if not pressed then
      if not trigger_frame then
        if policy == "E" or dist_to(mc, mr, d) <= policy then trigger_frame = H.frame end
      end
      if trigger_frame and H.frame - trigger_frame >= lag then H.joy(NAME[want]); pressed = true end
    end
    if pressed and not lead_at and want ~= d and H.rd(0x4D30) == want then lead_at = H.frame end
    if nxt and lead_at and H.frame - lead_at == nxt_delay then H.joy(NAME[nxt]); nxt = nil end
    H.wait(1)
    local s = score()
    if FRUIT_POINTS[s - last_score] then fruits = fruits + 1 end
    last_score = s
    if dead() then return done("dead") end
    if dots() >= 244 then return done("clear") end
    local g = ghost_min_dist(); if g < mind then mind = g end
    local tc, tr = pac_tile()
    if tc == mc and tr == mr then entered = true
    elseif entered then
      if H.rd(0x4D30) == want then return done("ok") end
      return done("miss")
    end
    local x, y = pac_px()
    if x == lastx and y == lasty then still = still + 1 else still = 0 end
    lastx, lasty = x, y
    if still > 200 then return done("stuck") end
  end
end

-- reach play start of level n (1-based) by really finishing levels 1..n-1: set the dots-eaten
-- counter to 244 and let the game run its normal level-complete (and intermission) path. Only
-- rewriting the level byte is NOT enough: the game keeps a separate pointer (0x4E0A) into its
-- difficulty table that only advances on a real level completion.
local function to_level(n)
  while H.rd(0x4E13) + 1 < n do
    local lv = H.rd(0x4E13)
    H.wr(0x4E0E, 244)
    while not (H.rd(0x4E13) == lv + 1 and H.rd(0x4E04) == 3) do H.wait(1) end
  end
end

local function reply(s) io.stdout:write(s .. "\n"); io.stdout:flush() end

H.run(function()
  H.wait(1)
  reply("ready")
  while true do
    local line = io.stdin:read("l")
    if not line then return end
    local cmd, a, b, c, d = line:match("^(%S+)%s*(%S*)%s*(%S*)%s*(%S*)%s*(%S*)")
    if cmd == "quit" then return
    elseif cmd == "newgame" then
      H.wait(600); H.tap("Coin 1"); H.wait(60); H.tap("1 Player Start")
      while H.rd(0x4E04) ~= 3 do H.wait(1) end
      reply("ok " .. H.frame)
    elseif cmd == "level" then
      to_level(tonumber(a)); reply("ok " .. H.rd(0x4E13) + 1)
    elseif cmd == "save" then H.save(a); reply("ok")
    elseif cmd == "rec" then
      -- video for showing a route: "rec <file.avi>" starts (in the snap directory), "rec" stops
      if a ~= "" then manager.machine.video:begin_recording(a, "avi") else manager.machine.video:end_recording() end
      reply("ok")
    elseif cmd == "wait" then H.wait(tonumber(a)); reply("ok")
    elseif cmd == "load" then
      -- savestates don't carry the joystick; restore the direction held when it was saved
      local held = b ~= "" and b or nil
      H.joy(held); H.load(a); H.joy(held)
      local tc, tr = pac_tile(); reply(string.format("ok %d %d %d", tc, tr, dots()))
    elseif cmd == "seg" then
      local pol = (b == "E") and "E" or tonumber(b)
      local st, fr, mc, mr, mind, win, fruits, lead = segment(LETTER[a], pol, tonumber(c) or 0, LETTER[d:sub(1, 1)], tonumber(d:sub(2)) or 0)
      local tc, tr = pac_tile()
      reply(string.format("%s %d %d %d %d %d %d %d %d %d %d", st, fr, mc, mr, mind, dots(), tc, tr, win, fruits, lead))
    elseif cmd == "mem" then
      local t = {}
      for addr = tonumber(a, 16), tonumber(a, 16) + tonumber(b) - 1 do t[#t + 1] = string.format("%02x", H.rd(addr)) end
      reply("ok " .. table.concat(t))
    elseif cmd == "dump" then
      local t = {}
      for addr = 0x4C00, 0x4FEF do t[#t + 1] = string.format("%02x", H.rd(addr)) end
      reply("ok " .. table.concat(t))
    elseif cmd == "hash" then
      local s = H.mem:read_range(0x4000, 0x4FEF, 8)
      local h = 0
      for i = 1, #s do h = (h * 31 + s:byte(i)) % 2147483647 end
      reply(string.format("ok %d f=%d", h, H.frame))
    elseif cmd == "peek" then
      local tc, tr = pac_tile()
      reply(string.format("ok f=%d tile=%d,%d dir=%d dots=%d level=%d 4E04=%d score=%d", H.frame, tc, tr, H.rd(0x4D30), dots(), H.rd(0x4E13) + 1, H.rd(0x4E04), score()))
    else reply("err " .. line) end
  end
end)

