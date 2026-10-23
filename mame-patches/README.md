# MAME patches

MAME is GPL-2.0-or-later; these are changes to its source, not official MAME.

## memstate.patch (MAME 0.289)

Adds in-memory savestate slots to the Lua API: `machine:mem_save(slot)`, `mem_load(slot)`,
`mem_drop(slot)`, `mem_clear()`, `mem_has(slot)`, `mem_count()`, `mem_errors()`.

They are saved and loaded at the same safe point between frames as MAME's normal (scheduled)
file save/load, but into the MAME process's RAM, uncompressed. MAME's own `buffer_save` /
`buffer_load` run immediately, mid-frame, and its source marks them broken; each `buffer_load`
also slowed every later frame. A normal file save spends most of its ~12 ms compressing.

On the harness's per-child step (`harness/benchmem.py`), memory slots take it from ~23 ms to
~10.4 ms (load 1.1 ms, save 0.5 ms). `harness/abtest.py` checks the patched build plays exactly
like stock 0.289: the same seg results and RAM hashes on every move of every `best/` route, both
straight through and stepped with file or memory saves, and state files load across the two.

Each slot is ~783 KB of RAM.

### Build (Windows)

1. Install MSYS2 (`winget install MSYS2.MSYS2`), then in an MSYS2 shell:
   `pacman -S --needed git make mingw-w64-x86_64-gcc mingw-w64-x86_64-python`
2. Get the source and apply the patch:
   ```
   git clone --depth 1 --branch mame0289 https://github.com/mamedev/mame.git mame-0.289-src
   cd mame-0.289-src
   git apply ../PacmanPatternFinder/mame-patches/memstate.patch
   ```
3. Build only the Pac-Man driver (about 30 minutes on 8 cores):
   ```
   export MINGW64=/mingw64 PATH=/mingw64/bin:/usr/bin:$PATH
   make SUBTARGET=pacman SOURCES=src/mame/pacman/pacman.cpp NOWERROR=1 GCC_VERSION=$(gcc -dumpfullversion) PYTHON_EXECUTABLE=python -j8
   ```
   (`GCC_VERSION` is passed because the makefile failed to detect GCC 16.)
4. Copy `pacman.exe` to `mame-0.289-mem/mame.exe` in this repo, with `roms/pacman.zip` beside it.
5. Check it: `cd harness; python abtest.py` must end with `ALL OK`.
