-- Probe: list input ports/fields, then coin up, start, and dump candidate RAM each second.
local machine = manager.machine
local mem = machine.devices[":maincpu"].spaces["program"]

for tag, port in pairs(machine.ioport.ports) do
  for name, _ in pairs(port.fields) do
    print(string.format("PORT %s FIELD %s", tag, name))
  end
end

local function field(name)
  for _, port in pairs(machine.ioport.ports) do
    if port.fields[name] then return port.fields[name] end
  end
end

local coin, start = field("Coin 1"), field("1 Player Start")
local frame = 0

_G.sub = emu.add_machine_frame_notifier(function()
  frame = frame + 1
  if frame == 600 then coin:set_value(1) elseif frame == 605 then coin:set_value(0) end
  if frame == 700 then start:set_value(1) elseif frame == 705 then start:set_value(0) end
  if frame % 30 == 0 and frame > 600 then
    local function b(a) return mem:read_u8(a) end
    print(string.format("f=%d pac(4D08,4D09)=%d,%d tile(4D39,4D3A)=%d,%d blinky(4D00,4D01)=%d,%d level=%d lives=%d",
      frame, b(0x4D08), b(0x4D09), b(0x4D39), b(0x4D3A), b(0x4D00), b(0x4D01), b(0x4E13), b(0x4E14)))
  end
  if frame == 1800 then machine:exit() end
end)

