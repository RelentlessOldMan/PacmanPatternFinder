package.path = "C:/Playground/PacmanPatterns/harness/?.lua;" .. package.path
local H = require("lib")
H.run(function()
  H.wait(600); H.tap("Coin 1"); H.wait(60); H.tap("1 Player Start")
  while H.rd(0x4E04) ~= 3 do H.wait(1) end
  print("play L1 at", H.frame)
  H.fields["Rack Test (Cheat)"]:set_value(1)
  local last = ""
  for i = 1, 1500 do
    H.wait(1)
    if H.rd(0x4E13) == 1 then H.fields["Rack Test (Cheat)"]:set_value(0) end
    local s = string.format("4E04=%d 4E00=%d lvl=%d dots=%d pac=%d,%d", H.rd(0x4E04), H.rd(0x4E00), H.rd(0x4E13), H.rd(0x4E0E), H.rd(0x4D08), H.rd(0x4D09))
    if s ~= last then print(H.frame, s); last = s end
  end
end)
