# Pac-Man pattern finder: handoff

Goal: find 1–3 **memorable, timing-tolerant** Pac-Man patterns for a MAME-based cabinet
(regular Midway Pac-Man). The published arcade patterns do NOT work on MAME (proven by the
user), so we discover new ones by having MAME play the game headless under Lua control.

Target: pattern A for levels 1..x, B for x..y, C for y..255 (256 not needed).
Rules: no reversing (double-backing) inside a pattern; on the high-value fruit levels grab both fruits;
~50 total turns is the memorability target (Procyon pattern ≈ 45–50).

## Setup at home (MAME + ROM are not in git)
1. Download MAME 0.289 (Windows 64-bit) and unpack into `mame-0.289/` in this folder
   (the code expects `mame-0.289/mame.exe`, see `harness/worker.py`).
2. Put your own `pacman.zip` ROM into `mame-0.289/roms/`.
3. Python 3.12, no extra packages. Run everything from `harness/`.
4. Smoke test: `python test_saveload.py` (expect `mismatches: 0 / 30`).

## How it works
- `harness/server.lua` – Lua command server inside MAME (`-video none -sound none -nothrottle`,
  ~110× real time). Commands over stdin: `newgame`, `level n` (reaches level n by really
  completing levels, needed so the difficulty pointer 0x4E0A advances), `save`/`load name heldDir`,
  `seg DIR policy lag [nxtK]` (run to the next junction/corner and leave it going DIR), `hash`, `peek`, `mem`, `dump`.
- `harness/lib.lua` – frame-coroutine helpers. `H.load` loads TWICE (one load sometimes lands one frame short).
- `harness/worker.py` – one MAME process per worker; `search.py` uses a pool of 10.
- `harness/maze.py` – maze model (`maze.txt`), nodes, BFS distances, dot clusters.
- `harness/search.py` – beam search over node decisions, never reversing. **Multi-sim**: each move is
  played from savestates on every target level at once and must survive on all of them.
  Timing robustness: each turn needs a press window ≥ `--minwin` (10 frames ≈ 167 ms) at junctions,
  ≥ `--corner-minwin` (5) at corners; corners tighter than minwin are also replayed with a *late* press
  ("late variant" sims, name suffix `*`) and must survive the pause too.
  Endgame planner (`--endgame 40`): once ≤40 dots remain, plays complete planned cleanup routes.
  Output: `result_*.json` (route string, per-segment windows), log `search_*.log`.
- `harness/validate.py result.json [--levels ..]` – replays a route straight through with random
  press jitter / late corners / late presses and reports how many clear.

Example: `python -u search.py --levels 1,2,3,4 --beam 96 --minwin 10 --out result_L1-4.json > search_L1-4.log`

## Game facts we found (see levels_diff.py / .out)
- RAM: 4D08/09 Pac Y/X, 4D39/3A tile (col=59−X, row=Y−33), 4D30 dir (0R 1D 2L 3U), 4DA5 death,
  4E0E dots eaten (244 = clear), 4E13 level (0-based), 4E04 state (3 = playing), 4E80-82 score BCD,
  4E0A difficulty row (0x68 + level-1, caps at level 21).
- Difficulty rows (ROM 0x0796): speeds change at 1 | 2–4 | 5–20 | 21+; identical rows {7,8} {16,18} {19,20};
  **levels 21–255 are identical** → one level-21 pattern covers 21–255. No blue ghosts at 17, 19, 20, 21+.
- Cruise Elroy (Blinky speed-up) dots-left threshold: 20 | 30 | 40 (3–5) | 50 (6–8) | 60 (9–11) | 80 (12–14) | 100 (15–18) | 120 (19+).
- Bottom nooks (24..26,23) and mirror: two corners 2 tiles apart, only ~6 frames window at level 2+ —
  every route has to pass them, which is why corners get a smaller min window.
- Pressing the next direction before Pac-Man leaves a corner tile changes the game; ≥4 frames after the
  turn registers is identical (no hidden extra window).

## Status (2026-10-21)
- Level 1 alone: cleared (`result_L1.json`, 104 moves / 81 turns). Dies on levels 2–5.
- Level 2 alone: cleared with late variants (`result_L2.json`, 121 moves / 87 turns); validated
  30/30 with up to 10f late corners, 5/20 at 20f.
- Levels 2–4 joint: stalled at 238/244 (`result_L2-4.json`). 1–4 joint (old settings) stalled at 214.
- User verdict: 2–4 / 3–4 sharing is not good enough. **Need 1–4 or better.**
- Endgame planner was just added; the 1–4 run with it was stopped at depth 30 (78 dots) — not yet evaluated.
- Turn counts (80+) are far above the ~50 target – memorability not addressed yet.

## Next steps
1. Rerun 1–4 with the endgame planner. If it still stalls, fix the search rather than tune it:
   - backtracking: rewind 20–30 moves when the end can't be finished (beam never revisits choices);
   - log which move kills which level (is level 1's slower speed the conflict?);
   - seed with big regional loops like human patterns and let the search repair details
     (this also helps the ~50-turn target).
2. Level 21 alone (covers 21–255), then validate downward to find y.
3. Middle pattern, both fruits on key levels (`--need-fruits 2`), save/resume from level starts.
4. Rank solutions by turns; produce a human-readable maze drawing of each pattern.
