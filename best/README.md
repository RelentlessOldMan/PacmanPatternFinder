# Patterns (2026-10-24)

Levels 1–4 are played by hand. Routes are the direction to leave each junction or corner (R D L U),
starting from Pac-Man's start position heading left. Neither route reverses.

| Levels | File | Moves / turns | Time | What it does |
|---|---|---|---|---|
| 5–20 | `L5-20_keep70_115.json` | 115 / 78 | 2971 frames (~50 s) | eats both fruits; leaves the corner pockets to eat by hand; its first 70 moves are the old 99 |
| 21+ | `L21_full_118.json` | 118 / 88 | 2922 frames (~48 s) | full clear, both keys; its first 15 moves are the 5–20 route |

Pattern sheets: `L5-20_115_screen.png`, `L21_118_screen.png` (plain drawn versions: `L5-20_115.png`,
`L21_118.png`). Videos: `../videos/`.

**Timing data** (`harness/rank_sols.py`): each turn is replayed pressed 1–4 frames past the point where
Pac-Man would corner cleanly, alone and in pairs. `killers1` counts single late presses that kill; the
JSON files list them (`single_killers`) and the moves they kill at.
- 5–20: no single killers on any level 5–20 (the search required it). 532 pairs of late presses kill,
  spread over moves 40-112, worst on L15-18.
- 21+: 31 single killers on level 21. Moves 30 and 110 die at 1 frame late, move 17 at 2, moves 13, 26
  and 27 at 3–4. For comparison, Goodrich's 9th key pattern has 131 (`harness/goodrich_late.py`).

Levels 21–255 play identically, so the 21+ route covers all of them.

## Older patterns

Kept for reference. Except the 99, they were found by earlier versions of the search and not re-tested the way the two above were.

| Levels | File | Moves / turns | Notes |
|---|---|---|---|
| 5–20 | `L5-20_nopockets_99.json` | 99 / 67 | the previous 5–20 route (2026-10-23); one fruit, 66 single late killers (move 27 pressed 4 late dies at move 84). Sheets `L5-20_99*.png`, video `../videos/L5-20_99_level5.mp4` |
| 2–4 | `L2-4.json` | 117 / 83 | |
| 5–8 | `L5-8.json` | 168 / 117 | full clear; shares its first 139 moves with the two below |
| 9–14 | `L9-14.json` | 178 / 122 | full clear |
| 15–20 | `L15-20.json` | 171 / 116 | full clear |

Their timing checks (`exhaust.py`) measured lateness from when Pac-Man left the previous junction, not
from the turn, so they mostly tested pressing early. A real level-7 game pressing 2–4 frames past the
turn died with one of them, which is why `rank_sols.py` measures from the turn.
