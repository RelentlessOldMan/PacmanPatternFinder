# Search run log

One entry per run, newest first. Every run writes `<out>.json` (best route), `<out>.json.sols.jsonl`
(all solutions, `--solutions`) and a log; all are committed. `.ckpt` files are resume checkpoints
(1 GB+, not committed). Output names are never reused.

The 99 route (5-20 final, corners by hand) =
`LLDLLDRRURULURRURUURRRRDLDLLDLDDRRRURULDLUUULDRUURDLDRDLDDDRDRRRDRRDLLULURRRRULULDLULURULLLURDDDDDD`

"Late" = a press 1-4 frames after the last frame that still corners cleanly (`--branch 4`).
"Survives 1 late" = every single late press on every level is followed (`--late-budget 1`).

## 2026-10-24

### Compare 100/67 vs keep70 115/78 (timing), and videos of both
- Narrowest press window over L5-20, on time: 100 has one 7-frame turn, the rest 10+; 115 has one 6- and one
  7-frame turn, the rest 10+ (scratchpad windows.py).
- `rank_sols.py cmp_100_vs_keep70.sols.jsonl --levels 5-20 --budget 2 --need-fruits 2` ->
  `cmp_100_vs_keep70.b2.ranked.json`, log `rank_cmp_100_vs_keep70_b2.log`. Both: 0 single killers.
  Killing pairs of late presses: 100 -> 892 (585 die at move 90, worst L6-8); 115 -> 532 (worst L15-18).
- Videos (on time, MAME): `videos/L5-20_100_level5.mp4`, `..._level20.mp4`,
  `videos/L5-20_keep70_115_level5.mp4`, `..._level20.mp4` (scratchpad video_route.py).

### Keep more of the 99: force its first K moves (`--prefix-on-time 26`, late-tested from move 27)
Same flags as the p26 run, `--prefix <first K moves of the 99>`. Out `result_L5-20_2fruit_late1_keepK.json`,
log `search_L5-20_2fruit_late1_keepK.log`.
| K | result |
|---|---|
| 83 | impossible: with move 27 pressed 4 late, both ways at move 84 die |
| 70 | CLEARED, 51 routes, 13 min; ranked (`..._keep70.ranked.json`, `rank_..._keep70.log`): all 0 single killers on L5-20. Best 115/78 -> `harness/best_L5-20_2fruit_keep70_115.json` |

### L5-20, 2 fruits, corners left, survives 1 late, only 26 moves on time - CLEARED, 0 killers
- out: `result_L5-20_2fruit_late1_p26.json` (+ `.sols.jsonl`, 55 routes), log `search_L5-20_2fruit_late1_p26.log`
- same flags as the L7-20 run below but `--levels 5..20 --prefix <first 26 moves of the 99>`; 35 min (1 core, throttled).
- Ranked (`rank_sols.py ... --levels 5-20 --budget 1 --need-fruits 2`, whole route incl. the opening) ->
  `result_L5-20_2fruit_late1_p26.ranked.json`, log `rank_L5-20_2fruit_late1_p26.log`:
  **all 55 have 0 single late killers on L5-20**. Shortest 100 moves / 67 turns -> `harness/best_L5-20_2fruit_100.json`
  (= the 99 for 27 moves). 15 routes are 100 moves (67-71 turns).

### Videos and critical-move image of the 104/73 candidate
- Route: `harness/best_L5-20_2fruit_104.json` (104 moves / 73 turns, from the L56zero ranking).
- `videos/L5-20_104_level5.mp4`, `..._level19.mp4` (on time, MAME, both clear), `..._level19_move27_4late.mp4`
  (move 27 pressed 4 frames late: dies between moves 75 and 76, right of the ghost house).
- `best/L5-20_104_move27.png` (made by `harness/critical_move_104.py`).

### Rank the 50 L7-20 2-fruit routes on L5-6, then on L7-20 (whole route)
- `rank_sols.py result_L7-20_2fruit_late1.json.sols.jsonl --levels 5-20 --late-levels 5,6 --budget 1 --need-fruits 2`
  -> `result_L7-20_2fruit_late1.L56.ranked.json`, log `rank_L7-20_2fruit_late1_L56.log`.
  All 50 clear L5-20 on time with both fruits. 13 have no single late killer on L5-6 (eight 104-move ones, 73-75 turns).
- Those 13 (`result_L7-20_2fruit_late1.L56zero.sols.jsonl`), late presses on L7-20 over the whole route
  (incl. the opening the search played on time) -> `result_L7-20_2fruit_late1.L56zero.L7-20.ranked.json`,
  log `rank_L7-20_2fruit_late1_L56zero_L7-20.log`. Each has exactly 2 killers: move 27 pressed 4 frames late
  dies at move 76 on L19 and L20. Next: search 5-20 with only 26 moves played on time.

### L7-20, 2 fruits, corners left, survives 1 late - CLEARED
- out: `result_L7-20_2fruit_late1.json` (+ `.sols.jsonl`, 50 routes), log `search_L7-20_2fruit_late1.log`
- `--levels 7..20 --leave-pockets --need-fruits 2 --branch 4 --late-budget 1 --branch-cap 64 --prefix-on-time
  --prefix <first 40 moves of the 99> --beam 96 --safe-after 3 --gap-cost 5 --family-depth 6 --family-cap 12`
- 50 min. Best 104 moves / 73 turns. All 50 follow the 99 for 41 moves, then differ.
- The first two tries under this name died at once: the user's 33-move mod opening misses the first fruit on
  L7, and `--prefix-on-time` dropped fruit counts (fixed in b161fd6).

### Full clear from 99 move 84, survives late presses - all STALLED
Prefix = first 84 moves of the 99, `--levels 5..20`, no pockets left, `--prefix-on-time`
(these ran before the b161fd6 fix, but didn't need fruits).
| out / log | late | settings | result |
|---|---|---|---|
| `result_pockets_late_p84` / `search_pockets_late_p84.log` | 2 | cap 32 | stalled 190/244 |
| `result_pockets_late1_p84` / `search_pockets_late1_p84.log` | 1 | cap 64, beam 64 | stalled 218/244 |
| `result_pockets_late1b_p84` / `search_pockets_late1b_p84.log` | 1 | cap 64, beam 160, backtracks 40, ~2 h | stalled 224/244 (181-move partial) |
Deaths mostly late mixes, L19, L5, L12.

### Full clear from 99 move 84/85, on time only - CLEARED
| out / log | prefix | result |
|---|---|---|
| `result_pockets_p84` (+ `.sols.jsonl`, 11) / `search_pockets_p84.log` | 84 | 131 moves / 97 turns, = the 99 for 88 moves |
| `result_pockets_p85` / `search_pockets_p85.log` | 85 | 152 moves / 109 turns |
- Videos (on time, MAME): `videos/L5-20_131_fullclear_level5.mp4`, `..._level12.mp4`.

### Late-press ranking of corner routes (`rank_corners.log`, `corners_short.sols.ranked.json`)
`rank_sols.py --budget 2` over L5-20 on the 99 + 5 shortest p84 full clears. The 99: 66 single late
killers, 2749 killing mixes, weak moves 84 and 90-97 (top right). Full clear 131: 162 / 4946, worst move
118 (bottom right, L12/13).
