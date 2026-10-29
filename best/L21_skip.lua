-- L21_skip.lua: plays back best/L21_speed_2316.inp, which starts on level 21. A .inp only holds inputs, so the
-- recording was made with this script skipping levels 1-20 (each is marked cleared the moment it starts, and the
-- game really advances), and it must run again on playback:
--   mame pacman -autoboot_script L21_skip.lua -playback L21_speed_2316.inp -input_directory .   (from the folder)
-- It runs unthrottled while skipping, then at normal speed from level 21. It only writes the dot counter (0x4E0E).
local mem = manager.machine.devices[":maincpu"].spaces["program"]
local skipping = false
-- 4E00 = 3 is game mode (the boot RAM test can look like play); 4E04 = 3 is a level in play
local function playing() return mem:read_u8(0x4E00) == 3 and mem:read_u8(0x4E04) == 3 end
L21_skip_sub = emu.add_machine_frame_notifier(function()
  if not playing() then return end
  if mem:read_u8(0x4E13) + 1 < 21 then
    if not skipping then skipping = true; manager.machine.video.throttled = false end
    if mem:read_u8(0x4E0E) < 244 then mem:write_u8(0x4E0E, 244) end
  elseif skipping then
    skipping = false; manager.machine.video.throttled = true
  end
end)
