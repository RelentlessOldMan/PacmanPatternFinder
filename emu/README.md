# pacemu

Midway Pac-Man without video or sound, for the pattern search. It runs the real program ROM on a
Z80 core ([superzazu/z80](https://github.com/superzazu/z80), MIT, `z80.c`/`z80.h`) with MAME 0.289's
memory map, interrupt and frame timing, so RAM matches MAME frame for frame. The whole machine is one
flat struct, so a savestate is a memcpy.

- `build.bat`: MSVC build of `pacemu.dll` (run from PowerShell: `cmd /c emu\build.bat`).
- `emu.py`: the Python wrapper (`Pacman().frame(in0, in1)`, `ram()`, `save()`/`load()`).
- `trace.lua`: records MAME booting and playing randomly. `route_trace.py <route json> <level> <prefix>`
  records MAME playing a finished route through the normal harness, using `PACMAN_TRACE` in
  `harness/lib.lua`.
- `compare.py <prefix>`: plays a trace's inputs (and the harness's memory pokes) in pacemu and compares
  all of 0x4000-0x4FFF with MAME's at every frame.

## Verified identical to MAME (2026-10-23)

| trace | frames | result |
|---|---|---|
| boot, attract, coin, random joystick play | 12000 | identical every frame |
| 99-move 5-20 route (levels 1-4 by dot poke, then level 5) | 5648 | identical every frame |
| 118-move 21+ route (to level 21, full clear) | 13883 | identical every frame |

Two things had to match MAME exactly:
- At power-on MAME's Z80 has every register 0 except IX and IY, which are 0xFFFF. IY gets pushed by the
  interrupt handler, so the difference shows up on the stack.
- The vblank interrupt is taken at the first instruction boundary at least 3 cycles after the frame
  notifier (`vbl_offset` 3). The interrupt handler pushes the interrupted PC, so the stack shows any
  frame where the interrupt lands on a different instruction. Offsets 2 and 4 both fail within 320 frames.

MAME's Z80 can stop in the middle of an instruction at a frame end, so its RAM at the notifier can show
only the first few writes of the instruction crossing it. pacemu runs whole instructions, so it records
that instruction's writes and `compare.py` accepts MAME's RAM if it equals any prefix of them. Nothing
reads those bytes before the instruction finishes, so game state is the same either way.
