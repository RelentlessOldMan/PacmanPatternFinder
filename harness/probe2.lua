package.path = "C:/Playground/PacmanPatterns/harness/?.lua;" .. package.path
local H = require("lib")

local function hex(a, n)
  local t = {}
  for i = 0, n - 1 do t[#t + 1] = string.format("%02x", H.rd(a + i)) end
  return table.concat(t)
end

local function pac() return string.format("pac=%d,%d", H.rd(0x4D08), H.rd(0x4D09)) end

H.run(function()
  H.wait(600)
  H.tap("Coin 1"); H.wait(60); H.tap("1 Player Start")
  -- wait until pac-man starts moving
  local x0 = H.rd(0x4D09)
  local start = H.frame
  while H.rd(0x4D09) == x0 do H.wait(1) end
  print("MOVE_START frame", H.frame, "after start press", H.frame - start)
  print("VRAM " .. hex(0x4000, 0x400))
  print("RAM " .. hex(0x4C00, 0x400))

  -- determinism + save/load check
  H.save("probe_a")
  print("after save", H.frame, pac())
  local trace1 = {}
  H.joy("U")
  for i = 1, 120 do H.wait(1); trace1[i] = hex(0x4D00, 10) end
  print("run1 end", pac())
  H.load("probe_a")
  print("after load", pac())
  local trace2 = {}
  H.joy("U")
  for i = 1, 120 do H.wait(1); trace2[i] = hex(0x4D00, 10) end
  print("run2 end", pac())
  local same, firstdiff = true, nil
  for i = 1, 120 do if trace1[i] ~= trace2[i] then same = false; firstdiff = firstdiff or i end end
  print("DETERMINISTIC", same, firstdiff)
  -- direction probes: log pos + candidate dir bytes for a while with varied inputs
  for _, d in ipairs({ "L", "D", "R", "U" }) do
    H.joy(d)
    for i = 1, 40 do
      H.wait(1)
      if i % 4 == 0 then print("DIR", d, pac(), "4D30=" .. H.rd(0x4D30), "4D3C=" .. H.rd(0x4D3C), "4D26/27=" .. hex(0x4D26, 2), "4D1C/1D=" .. hex(0x4D1C, 2)) end
    end
  end
end)
