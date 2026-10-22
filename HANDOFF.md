# Pac-Man pattern finder: handoff

Goal: find 1–3 **memorable, timing-tolerant** Pac-Man patterns for a MAME-based cabinet
(regular Midway Pac-Man). The published arcade patterns do NOT work on MAME (proven by the
user), so we discover new ones by having MAME play the game headless under Lua control.

Target: pattern A for levels 1..x, B for x..y, C for y..255 (256 not needed).
Rules: no reversing (double-backing) inside a pattern; on the high-value fruit levels grab both fruits;
~50 total turns is the memorability target (Procyon pattern ≈ 45–50).

## Setup at home (MAME + ROM are not in git)
1. Download MAME 0.289 (Windows 64-bit) and unpack into `mame-0.289/` in this folder,
   **or** point `MAME_EXE` at an existing `mame.exe` (e.g. `$env:MAME_EXE = "D:\Mame\mame.exe"`).
   MAME 0.287 reproduces the 0.289 results exactly. cfg/nvram/savestates always go in this repo.
2. Put your own `pacman.zip` ROM into `roms/` next to that `mame.exe`.
3. Python 3.12, no extra packages. Run everything from `harness/`.
4. Smoke test: `python test_saveload.py` (expect `mismatches: 0 / 30`).

## How it works
- `harness/server.lua` – Lua command server inside MAME (`-video none -sound none -nothrottle`,
  ~110× real time). Commands over stdin: `newgame`, `level n` (reaches level n by really
  completing levels, needed so the difficulty pointer 0x4E0A advances), `save`/`load name heldDir`,
  `seg DIR policy lag [nxtK]` (run to the next junction/corner and leave it going DIR), `hash`, `peek`, `mem`, `dump`.
- `harness/lib.lua` – frame-coroutine helpers. `H.load` loads TWICE (one load sometimes lands one frame short).
- `harness/worker.py` – one MAME process per worker (started at below-normal priority); `search.py` uses
  a pool of 10 (~5.5 of 12 logical cores).
- `harness/maze.py` – maze model (`maze.txt`), nodes, BFS distances, dot clusters.
- `harness/search.py` – beam search over node decisions, never reversing. **Multi-sim**: each move is
  played from savestates on every target level at once and must survive on all of them.
  Timing robustness: each turn needs a press window ≥ `--minwin` (10 frames ≈ 167 ms) at junctions,
  ≥ `--corner-minwin` (5) at corners; corners tighter than minwin are also replayed with a *late* press
  ("late variant" sims, name suffix `*`) and must survive the pause too.
  Endgame planner (`--endgame 40`): once ≤40 dots remain, plays complete planned cleanup routes.
  Output: `result_*.json` (route string, per-segment windows), log `search_*.log`.
  The log attributes failures to levels: `on={'L2': 9, 'late': 3}` per depth, and per endgame batch
  `{'dead:L3': '42x avg34left'}` (failure:level, count, average dots left when it died).
- `harness/validate.py result.json [--levels ..]` – replays a route straight through with random
  press jitter / late corners / late presses / every turn exactly 0..12 frames late, and reports how many clear.
- Search options added 2026-10-22: `--prefix ROUTE` (play a fixed opening, search from its end),
  backtracking (`--backtracks 20`, beam snapshot every 5 moves; repeat failures rewind further),
  `--fixed-sims 8,10` (extra sims pressing every turn exactly K frames late; replaces late variants),
  `--jitter-sims N`, `--turn-cost F`. Savestate names carry a per-run prefix so runs can share `state/`.
- `harness/watch.lua` + `watch.py` – watch a human play: launch the real (windowed) MAME with
  `-autoboot_script harness/watch.lua` (env `PACMAN_WATCH_LOG`, optional `PACMAN_LEVEL=n` skips to level n),
  then `python watch.py log [--check 5,7,...]` turns the game into a route and checks it on those levels.

Example: `python -u search.py --levels 1,2,3,4 --beam 96 --minwin 10 --out result_L1-4.json > search_L1-4.log`

## Game facts we found (see levels_diff.py / .out)
- RAM: 4D08/09 Pac Y/X, 4D39/3A tile (col=59−X, row=Y−33), 4D30 dir (0R 1D 2L 3U), 4DA5 death,
  4E0E dots eaten (244 = clear), 4E13 level (0-based), 4E04 state (3 = playing), 4E80-82 score BCD,
  4E0A difficulty row (0x68 + level-1, caps at level 21).
- Difficulty rows (ROM 0x0796): speeds change at 1 | 2–4 | 5–20 | 21+; identical rows {7,8} {16,18} {19,20};
  **levels 21–255 are identical** → one level-21 pattern covers 21–255 (confirmed: L21 and L30 replay
  frame-identical; the L21 route dies at move 17 on 17–20). No blue ghosts at 17, 19, 20, 21+.
  Scatter/chase timing: 1 | 2–4 | 5+. Pac-Man is slower at 21+ than at 5–20.
- Cruise Elroy (Blinky speed-up) dots-left threshold: 20 | 30 | 40 (3–5) | 50 (6–8) | 60 (9–11) | 80 (12–14) | 100 (15–18) | 120 (19+).
- Bottom nooks (24..26,23) and mirror: two corners 2 tiles apart, only ~6 frames window at level 2+ —
  every route has to pass them, which is why corners get a smaller min window.
- Pressing the next direction before Pac-Man leaves a corner tile changes the game; ≥4 frames after the
  turn registers is identical (no hidden extra window).

## Status (2026-10-22 night)
- **The user's own opening** (recorded with watch.lua; level-7 "higher level" version, logs in `harness/watch/`):
  `LLDLLDRRURULURRURUURRRRDLDLLDLDDD` (33 moves, 95 dots). Survives every turn 0–10 frames late on 2–19.
  All searches below are seeded with its first 30 moves (`--prefix`).
- Fixed: the press-window measurement broke at the tunnel wrap (window 0), so every turn right after the
  tunnel was rejected as `shortwin`. Results before this fix never turn just out of the tunnel.
- **5–20 seeded** (levels 5,7,10,13,17,19, beam 128): CLEARED, `result_L5-20_human2.json`, 174 moves / 126 turns.
  Validated on all 16 levels (`validate_L5-20_human2.log`): **dies on L6 (move 146) and L14 (move 160)**,
  and every-turn-8..10-late fails on several levels. Rerun with levels 5,6,7,10,13,14,17,19 + `--fixed-sims 8,10`.
- **2–4 seeded**: CLEARED, `result_L2-4_human.json`, 165 moves / 116 turns (old route 146). Validated:
  jitter 30/30 all levels, fixed-late OK to 12 on L2, 11 on L3, but L4 dies at exactly 10 late (move 118).
  Rerun with `--fixed-sims 8,10`.
- Unseeded 5–20 (two runs) stalled at 240/244, dying on L17 (no blue ghosts, Elroy from 100 dots left).

## Status (2026-10-21, second machine)
- **Plan changed: level 1 is played by hand (user's call), so the blocks are 2–4 | 5–20 | 21–255.**
  Timing slack minwin 10 (junctions) / corner-minwin 5 confirmed by the user as the floor.
- **2–4 joint: CLEARED** (`result_L2-4_diag.json`, 202 moves / 146 turns, both fruits on each level;
  the endgame planner finished it at depth 198). Validated: jitter 0–8f 30/30 on every level;
  corners up to 10f late 28/30, 30/30, 29/30 on L2/L3/L4.
- **21–255: CLEARED** (`result_L21.json`, 140 moves / 102 turns, both keys, ~6 min search). Validated
  on L21 and L30: jitter 19/20, corners up to 10f late only 13/20 (always dies at move 65 or 113).
  Cause: the search's late variant only tests a corner pressed exactly `minwin` frames late;
  intermediate lateness (e.g. 3–7f) can kill.
- 1–4 joint with endgame planner: stalled at 229 (`result_L1-4_eg.json`); dropped since level 1 is manual.
- Failure attribution on 2–4: deaths spread evenly over L2/L3/L4; late variants are the top endgame killer.
- Old: level 1 alone (`result_L1.json`, 81 turns), level 2 alone (`result_L2.json`, 87 turns).
- Turn counts (100–146) are far above the ~50 target.

## Next steps
1. Search changes, then rerun 2–4 and 21:
   - per-turn cost in `score()` (prefer straight runs / big loops) to cut turns, keeping minwin 10/5;
   - late variants at several lateness values (e.g. 3, 6, 10f) at tight corners, not just `minwin`.
2. 5–20: search on a subset (e.g. 5, 9, 13, 17), validate on all distinct levels (7=8, 16=18, 19=20),
   add failing levels to the search set. If it can't share, split where the failures say (5–8 | 9–20?).
3. If turns stay high: seed with big regional loops like human patterns; backtracking on stalls.
4. Rank solutions by turns; produce a human-readable maze drawing of each pattern.
- Job sizes: a search runs 10 MAMEs (~5.5 of 12 logical cores, little RAM). Level 21 alone ~6 min;
  2–4 joint ~30 min; 1–4 joint 80 min. `validate.py` on 3 levels ~5 min.

### 2026-10-22 08:00
- Fixed: stepped sims ran 1 frame later than straight-through play (the savestate costs a frame); search.py `stepped_lag` presses 1 frame sooner. Verified frame-identical over 171 moves.
- Best 2–4: `result_L2-4_human3.json`, 117 moves / 83 turns (user prefix + search). Jitter 30/30 on L2–4; fixed 0–12 ok on L3, 0–11 on L2; L4 dies at fixed 9 and 11; corner-late 30/18/22 of 30.
- Still running at 08:00: `search_L5-20_all.log` (13 distinct levels, best 222 dots) and `search_L2-4_human4.log` (fixed 4,7,9,10,11 + jitter, best ~240).

### 2026-10-22 afternoon: shared trunk + three finishers
- Trunk: first 139 moves of `result_L5-20_human3.json` (`trunk139.txt`), through the lower-left energizer.
- Finishers: `result_fin_L5-8.json` (168 moves), `result_fin_L9-14.json` (178 moves/122 turns), `result_fin_L15-20.json` (171 moves/116 turns).
- `exhaust.py` checks every lateness combination (identical RAM states merge; never more than ~64 states at once).
  All three routes survive every combination of 0-10 frames late on every turn, provided move 5 (the Down at the
  bottom-left corner (1,26), 6-frame window) is pressed within 6 frames, i.e. held early (`--limit 5:6`).
  5-8 is safe even without that limit. Without it, move 5 at 9-10 frames late kills 11-13 and 15-18.
- Tried: making the 9-14 finisher survive every trunk ending (`--history-sims`); it dead-ends 7 moves after the trunk.
