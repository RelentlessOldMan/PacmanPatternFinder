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
-- segment() reads everything it checks each frame as two blocks (one call into MAME each)
-- instead of ~25 single bytes; CM/CE hold them while a segment runs, nil otherwise
local CM, CE
local function snap() CM = H.mem:read_range(0x4D00, 0x4DA5, 8); CE = H.mem:read_range(0x4E0E, 0x4E82, 8) end
local function rd(a)
  if CM then
    if a >= 0x4D00 and a <= 0x4DA5 then return CM:byte(a - 0x4CFF) end
    if a >= 0x4E0E and a <= 0x4E82 then return CE:byte(a - 0x4E0D) end
  end
  return H.rd(a)
end
local function pac_tile()
  return 59 - rd(0x4D3A), rd(0x4D39) - 33
end
local function pac_px() return rd(0x4D09), rd(0x4D08) end -- internal x (grows left), y
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
    local gy, gx = rd(0x4D00 + g * 2), rd(0x4D01 + g * 2)
    local dd = math.abs(gx - x) + math.abs(gy - y)
    if dd < best then best = dd end
  end
  return best
end

local function bcd(v) return (v >> 4) * 10 + (v & 15) end
local function score() return bcd(rd(0x4E80)) + bcd(rd(0x4E81)) * 100 + bcd(rd(0x4E82)) * 10000 end
local function dead() return rd(0x4DA5) ~= 0 end
-- single-frame score jumps that can only come from a fruit (ghosts are 200/400/800/1600)
FRUIT_POINTS = { [100] = true, [300] = true, [500] = true, [700] = true, [1000] = true,
  [2000] = true, [3000] = true, [5000] = true }
local function dots() return rd(0x4E0E) end

-- segment: travel to the next node ahead and leave it heading `want`.
-- policy "E" = press immediately; integer p = press once within p px of node center.
-- lag = extra frames between trigger and press.
-- nxt (optional): press this direction as soon as the turn onto `want` registers, the way a
-- player presses the next turn as soon as they see Pac-Man come round the corner. `lead` is how
-- many frames that is before leaving the node tile, i.e. extra window for the next turn.
-- A segment's state lives in a table (n = frames so far) so segb can copy it at the press point.
local function seg_start(want, policy, lag, nxt, nxt_delay)
  local d = H.rd(0x4D30)
  local c, r = pac_tile()
  -- find next node ahead (the current tile counts)
  local mc, mr = c, r
  local guard = 0
  while not is_node(mc, mr) do
    mc, mr = wrapc(mc + DC[d][1]), mr + DC[d][2]
    guard = guard + 1
    if guard > 40 then return nil end
  end
  -- pac-man stops dead at a corner's center, so a press "past center" can't happen there
  if policy ~= "E" and not open(mc + DC[d][1], mr + DC[d][2]) and policy < 0 then policy = 0 end
  snap()
  return {
    want = want, policy = policy, lag = lag, nxt = nxt, nxt_delay = nxt_delay, d = d, mc = mc, mr = mr,
    n = 0, pressed = false, trigger = nil, entered = false, mind = 999, lastx = -1, lasty = -1, still = 0,
    -- win: frames from segment start until the turn is no longer "safe early" (4px before center)
    win = (want == d) and 99 or nil,
    fruits = 0, last_score = score(), lead_at = nil,
  }
end

local function seg_done(g, st)
  CM, CE = nil, nil
  return st, g.n, g.mc, g.mr, g.mind, g.win or 0, g.fruits, g.lead_at and (g.n - g.lead_at) or 0
end

-- the checks and presses before a frame runs
local function seg_before(g)
  if not g.win and dist_to(g.mc, g.mr, g.d) <= 4 then g.win = g.n end
  if not g.pressed then
    if not g.trigger then
      if g.policy == "E" or dist_to(g.mc, g.mr, g.d) <= g.policy then g.trigger = g.n end
    end
    if g.trigger and g.n - g.trigger >= g.lag then H.joy(NAME[g.want]); g.pressed = true end
  end
  if g.pressed and not g.lead_at and g.want ~= g.d and rd(0x4D30) == g.want then g.lead_at = g.n end
  if g.nxt and g.lead_at and g.n - g.lead_at == g.nxt_delay then H.joy(NAME[g.nxt]); g.nxt = nil end
end

-- after a frame has run: the segment's result if it ended, else nil
local function seg_after(g)
  g.n = g.n + 1
  snap()
  local s = score()
  if FRUIT_POINTS[s - g.last_score] then g.fruits = g.fruits + 1 end
  g.last_score = s
  if dead() then return "dead" end
  if dots() >= 244 then return "clear" end
  local m = ghost_min_dist(); if m < g.mind then g.mind = m end
  local tc, tr = pac_tile()
  if tc == g.mc and tr == g.mr then g.entered = true
  elseif g.entered then
    if rd(0x4D30) == g.want then return "ok" end
    return "miss"
  end
  local x, y = pac_px()
  if x == g.lastx and y == g.lasty then g.still = g.still + 1 else g.still = 0 end
  g.lastx, g.lasty = x, y
  if g.still > 200 then return "stuck" end
end

-- run frames until the segment ends (returns seg_done's results), or with `fork`, stop when the
-- press has just been triggered but not yet made (returns nothing; that frame has not run)
local function seg_run(g, fork)
  while true do
    seg_before(g)
    if fork and g.trigger and not g.pressed then return end
    H.wait(1)
    local st = seg_after(g)
    if st then return seg_done(g, st) end
  end
end

local function segment(want, policy, lag, nxt, nxt_delay)
  local g = seg_start(want, policy, lag, nxt, nxt_delay)
  if not g then return "nonode", 0, 0, 0, 999, 0, 0, 0 end
  return seg_run(g)
end

local function ram_hash()
  -- 0x4F80-0x4FBF is only stack below SP (0x4FC0 between frames; it reaches 0x4FA2 at most):
  -- stale bytes, like the return address left where the interrupt happened to land, that the
  -- game never reads, so they must not keep identical game states from merging
  local s = H.mem:read_range(0x4000, 0x4F7F, 8) .. H.mem:read_range(0x4FC0, 0x4FEF, 8)
  local h = 0
  for i = 1, #s do h = (h * 31 + s:byte(i)) % 2147483647 end
  return h
end

local function seg_reply(st, fr, mc, mr, mind, win, fruits, lead)
  local tc, tr = pac_tile()
  return string.format("%s %d %d %d %d %d %d %d %d %d %d", st, fr, mc, mr, mind, dots(), tc, tr, win, fruits, lead)
end

local function copy(t)
  local c = {}
  for k, v in pairs(t) do c[k] = v end
  return c
end

-- segb: the same as "seg <want> <policy> k" then "hash" then "msave <names[k]>", for k = 1..#names,
-- each from the same starting state -- but the frames up to the press, which those runs share,
-- are played once: the state there is kept in a slot and each k continues from it. The frame a
-- save or load lets run is a frame before any k presses, with the joystick as it was, so each k
-- sees exactly what its own run would. Replies "<seg reply> <hash>" per k, joined by " | ".
local function segb(want, policy, names)
  local held = H.joy_dir
  local out = {}
  local g = seg_start(want, policy, 1)
  if not g then
    for k = 1, #names do out[k] = "nonode 0 0 0 999 0 0 0 0 0 0 0" end
    return table.concat(out, " | ")
  end
  local r = { seg_run(g, true) }
  if #r > 0 then
    -- ended before the press point: no k ever presses, so they all play the same
    local line = seg_reply(table.unpack(r)) .. " " .. ram_hash()
    for k = 1, #names do out[k] = line; H.msave(names[k]) end
    return table.concat(out, " | ")
  end
  local fork = copy(g)
  H.msave("segb_fork")  -- the frame this lets run is the fork's next frame (no press yet)
  for k = 1, #names do
    if k > 1 then H.joy(held); H.mload("segb_fork") end
    g = copy(fork)
    g.lag = k
    local st = seg_after(g)
    if st then r = { seg_done(g, st) } else r = { seg_run(g) } end
    out[k] = seg_reply(table.unpack(r)) .. " " .. ram_hash()
    H.msave(names[k])
  end
  H.machine:mem_drop("segb_fork")
  return table.concat(out, " | ")
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
    elseif cmd == "prof" then
      -- profiling: seconds spent in this script's frame steps since the last "prof"
      reply(string.format("ok %.6f", H.lua_ticks / emu.osd_ticks_per_second())); H.lua_ticks = 0
    elseif cmd == "idle" then
      -- profiling: passes through the main loop's empty-queue wait (it reads 0x4C82 once a pass,
      -- 37 cycles) over the next N frames
      local n = 0
      local tap = H.mem:install_read_tap(0x4C82, 0x4C82, "idle", function(o, d, m) n = n + 1 end)
      H.wait(tonumber(a)); tap:remove(); reply("ok " .. n)
    elseif cmd == "load" then
      -- savestates don't carry the joystick; restore the direction held when it was saved
      local held = b ~= "" and b or nil
      H.joy(held); H.load(a); H.joy(held)
      local tc, tr = pac_tile(); reply(string.format("ok %d %d %d", tc, tr, dots()))
    elseif cmd:sub(1, 1) == "m" and cmd ~= "mem" and not H.has_mem then
      reply("err stock MAME has no memory slots")
    elseif cmd == "msave" then
      -- memory slot versions of save/load; mload replies like load. A failed save or load (it
      -- happens at the frame boundary, after the command returns) shows up as "err".
      local e = H.machine:mem_errors(); H.msave(a)
      reply(H.machine:mem_errors() == e and "ok" or "err msave " .. a)
    elseif cmd == "mload" then
      local held = b ~= "" and b or nil
      local e = H.machine:mem_errors()
      H.joy(held); H.mload(a); H.joy(held)
      local tc, tr = pac_tile()
      reply(H.machine:mem_errors() == e and string.format("ok %d %d %d", tc, tr, dots()) or "err mload " .. a)
    elseif cmd == "mdrop" then
      -- drop slots (space separated, any number)
      local n = 0
      for s in line:gmatch("%S+") do if s ~= cmd and H.machine:mem_drop(s) then n = n + 1 end end
      reply("ok " .. n .. " " .. H.machine:mem_count())
    elseif cmd == "mcopy" then
      -- "mcopy <slot> <file>": write a slot out as a state file (another worker can then load it);
      -- "mcopy <file> <slot> in": the reverse. Both happen at one frame boundary (a load then a
      -- save would let a frame run in between); the machine is left in that state.
      local e = H.machine:mem_errors()
      if c == "in" then H.machine:mem_import(a, b) else H.machine:mem_export(a, b) end
      H.wait(1)
      reply(H.machine:mem_errors() == e and "ok" or "err mcopy " .. a)
    elseif cmd == "seg" then
      local pol = (b == "E") and "E" or tonumber(b)
      reply(seg_reply(segment(LETTER[a], pol, tonumber(c) or 0, LETTER[d:sub(1, 1)], tonumber(d:sub(2)) or 0)))
    elseif cmd == "segb" then
      -- "segb <want> <policy> <slot1> <slot2> ...": see segb()
      local names = {}
      for w in line:gmatch("%S+") do names[#names + 1] = w end
      reply(segb(LETTER[a], tonumber(b), { table.unpack(names, 4) }))
    elseif cmd == "mem" then
      local t = {}
      for addr = tonumber(a, 16), tonumber(a, 16) + tonumber(b) - 1 do t[#t + 1] = string.format("%02x", H.rd(addr)) end
      reply("ok " .. table.concat(t))
    elseif cmd == "dump" then
      local t = {}
      for addr = 0x4C00, 0x4FEF do t[#t + 1] = string.format("%02x", H.rd(addr)) end
      reply("ok " .. table.concat(t))
    elseif cmd == "hash" then
      reply(string.format("ok %d f=%d", ram_hash(), H.frame))
    elseif cmd == "peek" then
      local tc, tr = pac_tile()
      reply(string.format("ok f=%d tile=%d,%d dir=%d dots=%d level=%d 4E04=%d score=%d", H.frame, tc, tr, H.rd(0x4D30), dots(), H.rd(0x4E13) + 1, H.rd(0x4E04), score()))
    else reply("err " .. line) end
  end
end)

