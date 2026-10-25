# Patterns (2026-10-24)

Routes are the direction to leave each junction or corner (R D L U), starting from Pac-Man's start
position heading left. None of them reverses.

| Levels | File | Moves / turns | Time | What it does |
|---|---|---|---|---|
| 1 | `L1_allghosts_129.json` | 129 / 95 | 4646 frames (~77 s) | full clear, both fruits, all 16 ghosts |
| 2 | `L2_allghosts_139.json` | 139 / 102 | 4676 frames (~77 s) | full clear, both fruits, all 16 ghosts |
| 3 | `L3_allghosts_147.json` | 147 / 107 | 4568 frames (~75 s) | full clear, both fruits, all 16 ghosts |
| 4 | `L4_allghosts_171.json` | 171 / 130 | 5089 frames (~84 s) | full clear, both fruits, all 16 ghosts |
| 5–20 | `L5-20_keep70_115.json` | 115 / 78 | 2971 frames (~50 s) | eats both fruits; leaves the corner pockets to eat by hand; its first 70 moves are the old 99 |
| 21+ | `L21_full_118.json` | 118 / 88 | 3040 frames (~50 s) | full clear, both keys; its first 15 moves are the 5–20 route |
| 21+ (safe) | `L21_safe141.json` | 141 / 104 | 3727 frames (~61 s) | the 118 to move 110, then a safe ending that survives blue being out of place (see below) |

Pattern sheets: `L<N>_allghosts_<moves>_screen.png`, `L5-20_115_screen.png`, `L21_118_screen.png`, `L21_safe141_screen.png` (plain
drawn versions without `_screen`). Videos: `../videos/`.

**Timing data** (`harness/rank_sols.py`): each turn is replayed pressed 1–4 frames past the point where
Pac-Man would corner cleanly, alone and in pairs. `killers1` counts single late presses that kill; the
JSON files list them (`single_killers`) and the moves they kill at.
- 5–20: no single killers on any level 5–20 (the search required it). 532 pairs of late presses kill,
  spread over moves 40-112, worst on L15-18.
- 1–4: found played exactly on time; none of the searches that also tried late presses finished.
  A single late press that kills or loses a ghost: L1 73 (weakest moves 48–52, 75–76, 92, 114–115),
  L2 69 (moves 51, 64, 93, 126), L3 103 (moves 43–44, 56, 60, 71, 93, 118, 142), L4 68 (moves 38, 56, 99,
  109, 151–153, 163). The four sets of four ghosts leave almost no slack.
- 21+: 31 single killers on level 21. Moves 30 and 110 die at 1 frame late, move 17 at 2, moves 13, 26
  and 27 at 3–4. For comparison, Goodrich's 9th key pattern has 131 (`harness/goodrich_late.py`).

Levels 21–255 play identically, so the 21+ route covers all of them.

## Older patterns

Kept for reference. Except the 99, they were found by earlier versions of the search and not re-tested the way the two above were.

| Levels | File | Moves / turns | Notes |
|---|---|---|---|
| 5–20 | `L5-20_nopockets_99.json` | 99 / 67 | the previous 5–20 route (2026-10-23); one fruit, 66 single late killers (move 27 pressed 4 late dies at move 84). Sheets `L5-20_99*.png`, video `../videos/L5-20_99_level5.mp4` |
| 2–4 | `../harness/best_L2-4_2fruit_102.json` | 102 / 64 | one route for levels 2–4, both fruits, keeps ghosts 3+ tiles away from move 54 on; no single late killers. Videos `../videos/L2-4_102_level2.mp4`, `_level4.mp4` |
| 2–4 | `L2-4.json` | 117 / 83 | |
| 5–8 | `L5-8.json` | 168 / 117 | full clear; shares its first 139 moves with the two below |
| 9–14 | `L9-14.json` | 178 / 122 | full clear |
| 15–20 | `L15-20.json` | 171 / 116 | full clear |

Their timing checks (`exhaust.py`) measured lateness from when Pac-Man left the previous junction, not
from the turn, so they mostly tested pressing early. A real level-7 game pressing 2–4 frames past the
turn died with one of them, which is why `rank_sols.py` measures from the turn.

## Level 21+ safe ending

`L21_safe141.json` is the 118 up to move 110, then a 31-move ending: after move 113 (up the middle-left corridor
to the top row) go right along the top, up into the top-right corner, back left along row 5, down the long
corridor, along the bottom, out the right tunnel, up the left side, and eat the top-left dots last.

Why: the 118's ending (moves 111–118) is fine on time, but if earlier presses drift, blue's loop can meet you in
the top left. `harness/drift_end.py` plays the 118 with every turn from move 80 to move 110 pressed 1–2 frames
late with chance 0.3, then tries each ending. With the ending also pressed sloppily, the 141 survived 46/46 games,
the 118's ending 33/46. With an on-time ending it survived 44/44. It was found by `search.py --history-sims` on 24
such games (`harness/drift_hist.py`), so every one of them had to survive. Drift spread over the first half of the
route usually kills the 118 at moves 37, 45–46 or 78 anyway; this only fixes the end.
