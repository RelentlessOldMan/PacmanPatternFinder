# MAME patches

MAME is GPL-2.0-or-later; these are changes to its source, not official MAME.

## memstate.patch (MAME 0.289)

Adds in-memory savestate slots to the Lua API: `machine:mem_save(slot)`, `mem_load(slot)`,
`mem_drop(slot)`, `mem_clear()`, `mem_has(slot)`, `mem_count()`, `mem_errors()`, and
`mem_export(slot, file)` / `mem_import(file, slot)`, which copy a slot to a normal state file or
back at one frame boundary (a load followed by a save would let a frame run in between, so the
file would be one frame later than the slot).

They are saved and loaded at the same safe point between frames as MAME's normal (scheduled)
file save/load, but into the MAME process's RAM, uncompressed. MAME's own `buffer_save` /
`buffer_load` run immediately, mid-frame, and its source marks them broken; each `buffer_load`
also slowed every later frame. A normal file save spends most of its ~12 ms compressing.

On the harness's per-child step (`harness/benchmem.py`), memory slots take it from ~23 ms to
~10.4 ms (load 1.1 ms, save 0.5 ms). `harness/abtest.py` checks the patched build plays exactly
like stock 0.289: the same seg results and RAM hashes on every move of every `best/` route, both
straight through and stepped with file or memory saves, and state files load across the two.

Each slot is ~783 KB of RAM.

## idleskip.patch (MAME 0.289, optional, apply after memstate.patch)

Pac-Man's main loop at 0x238D spins checking an empty task queue for about 71% of every frame
(measured: ~969 passes of 37 cycles out of 50,688 cycles per frame); everything the game does
happens in the vblank interrupt or in queued tasks. With the environment variable
`PACMAN_IDLESKIP=1` (set by `harness/worker.py` for `Worker(..., idle=True)`, which search.py
uses by default in RAM mode; `--no-idle-skip` turns it off), the patched driver puts the Z80 to
sleep until the next interrupt when it reaches that loop with the queue empty, so far fewer
instructions are emulated. Without the variable it behaves exactly like the memstate build.

The only RAM difference is the interrupt's return address left on the stack below SP (0x238D vs
0x2390), which the game never reads; `server.lua`'s `hash` skips that dead stack area
(0x4F80-0x4FBF) so states still merge. `abtest.py` checks seg results and hashes against stock.

## smallstate.patch (MAME 0.289, apply after the others)

A stock Pac-Man savestate is 783,159 bytes before compression. With the environment variable
`PACMAN_SMALLSTATE=1` (set by `harness/worker.py` for every MAME it starts) three things the game
never reads are left out, and a state is 7,859 bytes (1.3 KB as a compressed file):
- the sound stream's buffered audio samples (~769 KB); only the audio right after a load is wrong
- the palette colour tables (~5 KB), which Pac-Man sets once from its colour PROMs; they aren't
  restored on load either, so the palette stays as it was set at startup
- the tilemap scroll tables (~2 KB); Pac-Man never scrolls

What's left is about 3 KB of game RAM (video, colour, work and sprite RAM) plus CPU registers,
timers and latches. Files saved this way don't load in stock MAME; `abtest.py` sets the variable
to 0 for its stock-compatibility check.

### Build (Windows)

1. Install MSYS2 (`winget install MSYS2.MSYS2`), then in an MSYS2 shell:
   `pacman -S --needed git make mingw-w64-x86_64-gcc mingw-w64-x86_64-python`
2. Get the source and apply the patch:
   ```
   git clone --depth 1 --branch mame0289 https://github.com/mamedev/mame.git mame-0.289-src
   cd mame-0.289-src
   git apply ../PacmanPatternFinder/mame-patches/memstate.patch
   git apply ../PacmanPatternFinder/mame-patches/idleskip.patch
   git apply ../PacmanPatternFinder/mame-patches/smallstate.patch
   ```
3. Build only the Pac-Man driver (about 30 minutes on 8 cores):
   ```
   export MINGW64=/mingw64 PATH=/mingw64/bin:/usr/bin:$PATH
   make SUBTARGET=pacman SOURCES=src/mame/pacman/pacman.cpp NOWERROR=1 GCC_VERSION=$(gcc -dumpfullversion) PYTHON_EXECUTABLE=python -j8
   ```
   (`GCC_VERSION` is passed because the makefile failed to detect GCC 16.)
4. Copy `pacman.exe` to `mame-0.289-mem/mame.exe` in this repo, with `roms/pacman.zip` beside it.
5. Check it: `cd harness; python abtest.py` must end with `ALL OK`.
