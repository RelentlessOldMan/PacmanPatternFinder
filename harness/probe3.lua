package.path = "C:/Playground/PacmanPatterns/harness/?.lua;" .. package.path
local H = require("lib")

local function st() return string.format("f=%d pac=%d,%d dir=%d dots(4E0E)=%d 4DA5=%d lives=%d 4E04=%d 4E00=%d level=%d",
  H.frame, H.rd(0x4D08), H.rd(0x4D09), H.rd(0x4D30), H.rd(0x4E0E), H.rd(0x4DA5), H.rd(0x4E14), H.rd(0x4E04), H.rd(0x4E00), H.rd(0x4E13)) end

H.run(function()
  H.wait(600)
  H.tap("Coin 1"); H.wait(60); H.tap("1 Player Start")
  while H.rd(0x4E04) ~= 3 do H.wait(1) end
  H.save("lvl1_start")

  -- cornering: junction (row 23, col 12) center x=140; press Up when x >= 140 - k
  for k = 10, -8, -1 do
    H.load("lvl1_start")
    H.joy("L")
    local pressed_at, turned_x, f0 = nil, nil, H.frame
    for i = 1, 60 do
      local x = H.rd(0x4D09)
      if not pressed_at and x >= 140 - k then H.joy("U"); pressed_at = x end
      H.wait(1)
      if not turned_x and H.rd(0x4D30) == 3 then turned_x = H.rd(0x4D09) end
    end
    print(string.format("CORNER k=%d pressed_x=%s turned_x=%s end pac=%d,%d", k, tostring(pressed_at), tostring(turned_x), H.rd(0x4D08), H.rd(0x4D09)))
  end

  -- death / dots watch: go left then down and idle
  H.load("lvl1_start")
  H.joy("L")
  local last = ""
  for i = 1, 0 do
    H.wait(1)
    local s = string.format("%d %d %d %d %d", H.rd(0x4E0E), H.rd(0x4DA5), H.rd(0x4E14), H.rd(0x4E04), H.rd(0x4E00))
    if s ~= last then print("WATCH " .. st()); last = s end
  end
end)

