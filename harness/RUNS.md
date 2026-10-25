# Search run log

One entry per run, newest first. Every run writes `<out>.json` (best route), `<out>.json.sols.jsonl`
(all solutions, `--solutions`) and a log; all are committed. `.ckpt` files are resume checkpoints
(1 GB+, not committed). Output names are never reused.

The 99 route (5-20 final, corners by hand) =
`LLDLLDRRURULURRURUURRRRDLDLLDLDDRRRURULDLUUULDRUURDLDRDLDDDRDRRRDRRDLLULURRRRULULDLULURULLLURDDDDDD`

"Late" = a press 1-4 frames after the last frame that still corners cleanly (`--branch 4`).
"Survives 1 late" = every single late press on every level is followed (`--late-budget 1`).

## 2026-10-24

### L1, L2, L3, L4 each: all 16 ghosts (4 per energizer) + both fruits, full clear
- `result_L<N>_2fruit_16ghosts_{late1,ontime}` (`--levels N --all-ghosts --need-fruits 2 --branch 4 --late-budget 1|0
  --branch-cap 64 --beam 96 --gap-cost 5 --family-depth 6 --family-cap 12`): late1 stalled on every level; ontime
  "cleared" in 1-2 min, but those routes eat only 9-12 ghosts: BUG, a fright ending in the frame a load lets run
  (before the move's seg started counting) went unseen. Fixed: loads mark 0x4DA6/0x4DD0 of the loaded state
  (`pm_mark`; server.lua keeps them per saved slot). These results are invalid.
- Rerun as `result_L<N>_2fruit_16ghosts_v2_{late1,ontime}` after `emu_parity.py --levels 1,2,21` (`parity_ghosts2.log`).
- v2 (parity OK): L1 ontime "cleared" with 12 ghosts, L2-4 dead-ended (late1 and ontime). Second BUG: an energizer
  eaten while still blue from the last one, with 0 eaten, resets nothing (0x4DD0 stays 0). Now a +50 while blue with
  < 4 eaten is a miss, a clear on an energizer is a miss, and `--all-ghosts` also rejects any clear with < 16 ghosts.
  v2 results invalid too. Rerun as `..._16ghosts_v3_...` (`parity_ghosts3.log`).
- v3 (parity OK): **L1 ontime clears with 16 ghosts + 2 fruits**, 128/93 (straight replay: 16 ghosts, score 14800).
  `rank_sols.py --levels 1 --budget 1 --need-fruits 2 --all-ghosts` (new flag: a lost ghost counts as a kill) on its 50:
  best 73 single late presses kill (weak at moves 48-52, 76, 92, 114-115) -> `rank_L1_16ghosts_v3.log`. L1 late1 and
  L2-4 (both modes) dead-ended at beam 96 / 20 backtracks.
- Ranked #1 saved as `best_L1_16ghosts_129.json` (129/95, 73 single killers); MAME video (on time, clears):
  `videos/L1_16ghosts_129_level1.mp4`.
- `..._16ghosts_wide_...`: same with `--beam 300 --backtracks 60 --family-cap 30`.
  Results: late1 dead-ended on all 4 levels; ontime L1 and L2 dead-ended too (L1 found at beam 96 but not 300);
  **L3 ontime 148/107 and L4 ontime 171/130 clear with 16 ghosts + 2 fruits.** Ranked (`--budget 1 --all-ghosts`):
  L3 best 147/107, 103 single killers -> `best_L3_16ghosts_147.json`; L4 best 171/130, 68 -> `best_L4_16ghosts_171.json`.
  MAME videos (on time, both clear): `videos/L3_16ghosts_147_level3.mp4`, `videos/L4_16ghosts_171_level4.mp4`.
- L2 retries: `result_L2_2fruit_16ghosts_b600_ontime` (`--beam 600 --backtracks 100 --family-cap 40`),
  `result_L2_2fruit_16ghosts_fd10_ontime` (`--beam 200 --family-depth 10 --family-cap 20 --backtracks 100`).
  b600 dead-ended at move 38; **fd10 clears with 16 ghosts + 2 fruits** (141/110). Ranked: best 139/102, 69 single
  killers -> `best_L2_16ghosts_139.json`; MAME video (on time, clears) `videos/L2_16ghosts_139_level2.mp4`.
- The four `best_L<N>_16ghosts_*.json` moved to `best/L<N>_allghosts_*.json` with pattern sheets; README shows 1-4 / 5-20 / 21+.

### L21 speed (for fun): tie/beat the ~42 s (~2545 frames) world-record clear; tight timing, then reversals
- Found: search `frames` missed the frame each move's state load runs (1 per move), so every earlier frame total is
  low by ~moves. Fixed in make_child. True times by `replay_route.py <route> 21` (new; straight replay on pacemu):
  `best/L21_full_118.json` 3039 frames (50.14 s).
- `result_L21_speed_fc{0.25,1}` (`--levels 21 --minwin 1 --corner-minwin 1 --no-late --late-budget 0 --frame-cost F
  --beam 300 --family-depth 6 --family-cap 30 --backtracks 60 --solutions 50`, new `--frame-cost`, no fruit needed):
  116/90 2975 frames (49.09 s) at 0.25; 121/92 3095 at 1.
- New `--reverse`: an "x" move keeps going to the last uneaten dot before the next node (when the rest up to the node
  is eaten) and turns back there (server `reverse`). `result_L21_revtest` (beam 30, 4 workers): 116 moves, 2938 frames.
- `result_L21_speed_rev_{fc0.25,fc0.5,fc0.25_b1000}`: the speed runs with `--reverse` (beam 300, 300, 1000).
  Results 2685 / 2812 / 2684 frames (44.30 / 46.40 / 44.29 s, replayed). The 2684 (b1000) route passes THROUGH a
  ghost (one move's mind = 1 px: the tile-swap glitch): these runs had no `--min-ghost`, and "x" moves didn't measure
  ghost distance at all (mind=999). The 2685 route is clean: closest 12 px on segs, 38 px on its "x" moves.
  Fixed: `reverse` now replies `mind=` (closest ghost on the way; emu_server.py and server.lua), run_rev uses it.
- `result_L21_speed_rev_fc{0.1,0.15,0.25}_cc{40,10,0}_s200` (beam 300, `--cluster-cost`, 200 solutions): none
  better (best 2685 again at fc0.25 cc40). Same no-min-ghost caveat.
- `result_L21_speed_rev_{mg8,mg8_b1000,mg12}` (`--reverse --min-ghost 8/8/12`, fc 0.25, beam 300/1000/300): all three
  find the same clean 102-move route, 2685 frames (44.30 s). Target 41.6 s (~2521 frames): 164 frames short.

### L2-4: keep ghosts away (user: no passing ghosts in the lower left near the end of the 97)
- On the 97, ghosts come within 19-20 px (2.5 tiles) at moves 75-83, lower left (scratchpad permove.py).
- New `search.py --min-ghost PX --min-ghost-from N`: drop a move if any sim lets a ghost come closer than PX
  pixels (|dx|+|dy|) after move N.
- `result_L2-4_2fruit_late1_user40_g24` (user's 40, `--prefix-on-time 26 --min-ghost 24 --min-ghost-from 40`):
  56 routes, 3.5 min, best 102/73; ranked (`..._g24.ranked.json`, `rank_..._g24.log`): all have 8+ single
  killers: late presses at moves 13/14/18 (in the opening, not late-tested) kill at moves 72-76.
- `result_L2-4_2fruit_late1_user40_g24_ot0` (same, `--prefix-on-time 0`: late presses tested from move 1):
  73 routes, all 0 single killers, but best 122/92 (`..._g24_ot0.ranked.json`, `rank_..._g24_ot0.log`).
- Instead, from the first user40 run: two 102/64 routes with 0 single killers keep ghosts 24+ px away from move 54
  on (on time; the lower left now 25-49 px). `--budget 2` (`..._user40.102.b2.ranked.json`,
  `rank_L2-4_2fruit_late1_user40_102_b2.log`): 60 killing pairs (the 97: 224) -> `harness/best_L2-4_2fruit_102.json`.
  Videos: `videos/L2-4_102_level2.mp4`, `..._level4.mp4`.
- seg replies gain two fields (emu/seg.h + server.lua): `ghosts` eaten this move, `gmiss` = an energizer ran out
  (0x4DA6 blue -> 0) or was replaced, or the level cleared, with fewer than 4 eaten (0x4DD0). `search.py --all-ghosts`
  fails such moves. Parity `emu_parity.py --levels 2,5,21` -> `parity_ghosts.log`: 0 differ.

### L2-4, 2 fruits, corners left, survives 1 late
- The user's own level-4 play (logged by `C:/mame/pacman_logs/level4_logger.lua`, copied to
  `harness/watch/play_L4_20261024_123629.log`): 50 moves, 132 dots, eats the 4 ghosts, no reverses:
  `LLDLLDRRURULURRURUUURDRRDLDLLDDRURUULLLLLULDRDDDDD` (= the 5-20 route for 18 moves). Clears its 50 moves on
  time on L2, L3 and L4.
- Keep the 5-20 keep-70 route (`result_L2-4_2fruit_late1_keepK`): K=70 and K=50 die on time at move 35 on L2;
  K=26 was stopped (user: keeping under 35 moves isn't worth it, start from their route instead).
- From the user's 50 moves: `result_L2-4_2fruit_late1_user50_ot26` (late presses tested from move 27; if the prefix
  fails, `..._ot50` plays all 50 on time). Same flags as the 5-20 runs, `--levels 2,3,4`.
  Result: the 50 moves survive late presses from 27 on, but every way on dies by move 56 (ghosts close).
  On time the route eats the upper-left energizer at move 45 and only 1 ghost (L3/L4, move 49; none on L2);
  the user's 4 came from their own timing (scratchpad ghosts.py).
- Probe (2 min each, scratchpad u<K>.log): keeping 48/46/44/42 of the user's moves dead-ends by d=44-64;
  40/38/36 still alive. Full search from 40: `result_L2-4_2fruit_late1_user40`, log `search_L2-4_2fruit_late1_user40.log`.
  CLEARED in 3 min, 58 routes, best 97/61. Ranked (`rank_sols.py --levels 2-4 --budget 1 --need-fruits 2`,
  whole route) -> `result_L2-4_2fruit_late1_user40.ranked.json`, log `rank_L2-4_2fruit_late1_user40.log`:
  28 routes with 0 single killers, incl. three 97-move ones. Those three with `--budget 2`
  (`..._user40.97.b2.ranked.json`, log `rank_L2-4_2fruit_late1_user40_97_b2.log`): best 97/61 with 224 killing
  pairs -> `harness/best_L2-4_2fruit_97.json`. Videos (on time, MAME): `videos/L2-4_97_level2.mp4`, `..._level4.mp4`.

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
| 76 | CLEARED, 52 routes, 27 min (not ranked). Best 128/89 |
| 79 | stopped by the user (keep-70 chosen), 0 routes yet; log partial |

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

### L21 ghost-free floor (no fruit): `floor.py`, `PACMAN_NOGHOSTS=1`
- New `PACMAN_NOGHOSTS=1` (emu_server.py): ROM 0x1763 `LD A,B` -> `XOR A` after boot, so no ghost touches Pac-Man
  (off during `newgame`, which hangs in the attract demo with it on). Pac-Man's own timing is unchanged: the 2685
  route replays at 2685 with it on.
- New `floor.py`: fewest tile steps from the start visiting every dot (scipy milp, flow-connected), then ~300 Euler
  orderings driven frame by frame on pacemu (earliest presses, like seg "E"; turn back on any tile). The driver
  reproduces the 2685 route at exactly 2685 frames.
- `result_floor_L21_nofruit.json` / `floor_L21_nofruit.log`: 30 min milp limit: 291 steps (proven >= 287 from an
  earlier cut-based attempt, stopped). Best ordering 2062 frames (34.02 s), vs our 2684 and the ~2521 record.


### L21 ghost-free floor, both fruits
- `floor.py --steps-from result_floor_L21_nofruit.json --fruits 2`: the 291-step walk plus a side trip to the fruit
  tile while each fruit is out. Seeds 1-5 (`floor_L21_2fruit_trips{,_s2..s5}.log`): all 2337 frames (38.56 s),
  335 steps; seeds 2-5 stopped early as duplicates (`result_floor_L21_2fruit_trips.json`). `--fruit-visits 2` milp
  (`floor_L21_2fruit_fv2.log`): 295 steps, best 2346 with trips. `--fruit-visits 3`: 297 steps, no walk drove clean
  (crashed at the end: no best).
- Driving that ghost-free walk with ghosts on: dead at step 68/291 (frame 490, 60 dots).

### L21 speed with any-dot turn-backs (`--reverse-any`)
- New `--reverse-any` (search.py): besides "x", moves "x<i>" turn back on any uneaten dot ahead (index i on the
  path to the next node). Server `reverse` now also counts fruits eaten. After a turn-back the child's tile is the
  one its next load sees (the load frame can cross a tile edge; fixes BADLOADs). replay_route.py plays "x<i>".
- `result_L21_revany_test.json` / `search_L21_revany_test.log` (beam 30, need-fruits 2): stalled 243/244.
- `result_L21_revany_b{300,1000}` (need-fruits 2, no family/backtrack flags): 3216 / 3031. Without
  `--family-depth 6 --family-cap 30 --backtracks 60 --solutions 50` the search is much worse.
- `result_L21_revany_fam_{b300,b1000,nf2_b300,nf2_b1000}` (with those flags, fc 0.25): **2621** (43.25 s, 106 moves,
  both fruits, replayed) at beam 300, with or without need-fruits; 2694 at beam 1000. New best (was 2685).
- `sweep_revany.sh` -> `sweep_revany.txt`: fc {0.15,0.25,0.4} x beam {200,400} x family-cap {20,30,50} x seed {1,2}.
  Result: none better than 2621 (range 2621-3103); `--seed` changes nothing (it only drives the endgame).
- `--prefix` now plays turn-back moves. `result_L21_polish_test` (prefix = first 60 moves of the 2621, beam 300):
  2686, so re-searching a tail from a fixed prefix doesn't find the original's own ending.
- Beam score is dots*10 - frames*fc: at fc 0.25 a dot's ~8 frames cost only 2, so the beam grabs dots and ignores
  time. `sweep_revany2.sh` -> `sweep_revany2.txt` (fc {0.6,1.0,1.25} x `--cluster-cost` {0,20,40}, beam 300):
  **fc 1.0 cc 40: 2562 frames (42.27 s), 109 moves, both fruits** (`result_L21_revany_fc1.0_cc40.json`, replayed).
  fc 1.25 cc 40: 2421 (39.95 s) but one fruit. cc 0 is bad at high fc (3003-3146).
- `sweep_revany3.sh` -> `sweep_revany3.txt`: need-fruits 2, fc {1.0,1.25,1.6} x cc {40,60,90}.
  Result (`sweep_revany3.txt`): best 2562 again (fc 1.0 cc 40, same route); the rest 2877-3263, fc 1.6 fails.
- `sweep_fruitfix.sh` -> `sweep_fruitfix.txt`: the 2421 route (it skips fruit 1, out moves ~23-47) as `--prefix`
  K = 20..44 moves, then need-fruits 2, cc 40, fc 1.0/1.25: best 2642; K 44 fails. No gain.
- New `--score-noise X` (search.py): a fixed random 0..X per (--seed, route) on each beam score, so seeds differ.
  `sweep_noise.sh` -> `sweep_noise.txt`: fc {1.0,1.25} x noise {15,40} x seeds 1-8, need-fruits 2, cc 40.
  Result: **2560 frames (42.24 s), 108 moves, both fruits** (`result_L21_nz_fc1.0_n40_s3.json`, replayed), new best;
  many seeds land on the 2562 again. fc 1.25 worse. s6/s8 "2443/2502" are 243-dot partials (stalled), not clears.
- `sweep_wide.sh` -> `sweep_wide.txt`: beam {600,1000} x fc {0.9,1.0,1.1} x cc {30,40,50}, need-fruits 2.
  Result: best 2562 again (b600 fc1.1 cc40). Wider beams don't help. Most of the fast-looking ones (2431-2499) are
  243-dot partials holding ONE fruit: with need-fruits 2 they can never count (the level ends on the last dot), yet
  they fill the beam.
- Fruitless pruning (search.py): a child whose fruit came and went uneaten (seg's `gone` - fruits eaten > 2 - need)
  is dropped. Server `reverse` (emu + Lua) now replies fruits= and gone= too.
  `sweep_prune.sh` -> `sweep_prune.txt` (beam {300,600,1000} x fc {0.8..1.1} x cc {30,40}): best 2562; 7 of 24 runs
  die by move ~40 (no candidate reached fruit 1 in time: the score never pulls toward an uneaten fruit).
- New `--fruit-pull P`: score -P per tile from the fruit while one is out. `sweep_pull.sh` -> `sweep_pull.txt`:
  P {3,8,15} x fc {0.9,1.0,1.1} x cc {30,40}, beam 300.
  Result: worse at every setting (best 2600 at P 3; P 15 up to 3802). Dropped.
- `sweep_noise2.sh` -> `sweep_noise2.txt`: fc 1.0 cc 40 beam 300 need-fruits 2, noise {25,40,60} x seeds 9-24 (48
  runs, with fruitless pruning): best 2562 (several seeds), 2576, 2577. The 2560 stands.
- `sweep_noise3.sh` -> `sweep_noise3.txt`: fc {0.95,1.05} x cc {35,45} x seeds 1-8, noise 40: best 2560 (fc 1.05
  cc 45 s3), then 2578, 2583. No gain.

**L21 speed, standing best (2026-10-24): `result_L21_nz_fc1.0_n40_s3.json`, 2560 frames = 42.24 s, 108 moves, both
fruits, full clear, replayed on pacemu.** Closest ghost 21 px on any move (no booey needed); tightest window 5 frames.
vs ~2521 (41.6 s record): 39 frames (0.64 s) short. Ghost-free floors: 2062 no fruit, 2337 both fruits.

### L21 speed: deliberate booeys (2026-10-24; this route only, never routes the user plays)
- `booey_probe.py 150 21`: 150 random walks from the L21 start until death. 99 deaths head-on (killer heading
  opposite Pac-Man). Redoing the move before the deadly one pressed k = 1..12 frames late (seg "4 k") rescued 50;
  32 of those went through the ghost (closest ghost ~1 px: same-frame tile swap), the rest dodged it.
- New `--booey K` (search.py): a move that dies is retried after redoing the move before it k = 1..K frames late;
  the first k that lives makes a child, route token e.g. "R2" (replay_route.py plays it as seg "R 4 2"). Cand
  keeps its parent (states kept alive). Test `result_L21_booey12_n40_s3.json` (best settings + noise 40 s3 +
  booey 12): ~20-30 rescues per depth, half through ghosts; result 2666 (no booey in it); 21/56 solutions had one
  (best 2719 `...LULUR2R`, replays as a clear at exactly 2719).
- `sweep_booey.sh` -> `sweep_booey.txt`: booey {12,6} x seeds 1-8.
  Result (`sweep_booey.txt`): best 2666 (s3), the rest 2752-3010; K 6 and 12 give the same routes (the first k that
  works is small). Booeys rescue moves but the extra children push the beam elsewhere: no gain over 2560.
- New `--guide FILE[:i]` / `--guide-cost G` / `--guide-slack W` (search.py): follow a floor.py ghost-free walk.
  The score's "nearest dot" term becomes the distance to the guide's next uneaten dot, and each eaten dot outside
  the guide's first len(eaten)+W costs G. floor.py `--keep N` saves the N fastest distinct walks ("walks").
  Test `result_L21_guide_trips_gc20_b12.json` (2337 walk, G 20, W 0, cc 0, booey 12): 3903 frames, 179 moves:
  with no slack, eating a dot early is penalized, so the search turns back to avoid dots. Hence the slack.
- `floor.py --steps-from result_floor_L21_nofruit.json --fruits 2 --keep 40` -> `result_floor_L21_2fruit_keep40.json`.
- `sweep_guide.sh` -> `sweep_guide.txt`: 2337 walk, G {3,10} x W {10,25} x cc {0,40}, booey 12.
  Result (`sweep_guide.txt`): **G 10 W 25 cc 40: 2458 frames (40.56 s), 100 moves, both fruits, full clear, replayed**
  (`result_L21_guide_gc10_sl25_cc40.json`): under the ~2521 (41.6 s) target, 102 frames better than 2560. Its "R9"
  is a booey-retry move, but it dodged (9 frames waiting at a corner; the next move's closest ghost 20 px), not a
  pass-through; closest ghost on the whole route 14 px; tightest window 5. G 3 W 25 cc 40: 2465 (no late move).
  Slack 10 and cc 0 are much worse (2655-3104).
- `sweep_guide2.sh` -> `sweep_guide2.txt`: G 10 W 25 cc 40 guided by each of the 12 kept floor walks (2337-2346).

**L21 speed, standing best (2026-10-25): `result_L21_neigh_2438.json`, 2438 frames = 40.23 s (was 2458, `result_L21_guide_gc10_sl25_cc40.json`).**
  Result (`sweep_guide2.txt`): all 12 give the same 2458 route: the kept walks share one milp step set and agree on
  their first ~97 dots, then differ in 2-11 places of 244, too little to matter with slack 25.
- `sweep_guide3.sh` -> `sweep_guide3.txt`: guide 2337 walk (trips) and the fv2 walk (other step set, 2346), noise 40
  seeds 1-8.
- `sweep_guide4.sh` -> `sweep_guide4.txt`: 2337 walk, no noise, G {7,10,14} x W {20,25,32} x cc {30,40,50}.
  (Goal from the user: sub-40 s = 2423 frames or fewer.)
  Result (`sweep_guide3.txt`): noise hurts guided search: best 2518 (trips s7), others 2532-3204; fv2 walk 3114+;
  trips s2 stalled (61 moves). 2458 (noise-free) stands.
- Video: `videos/L21_speed_2458_level21.mp4` (new `harness/video_route.py`: plays a route via replay_route.play in
  stock MAME 0.289, so x / late moves work): clears at exactly 2458 frames in MAME too.
  Result (`sweep_guide4.txt`): 12 of 27 settings land on the same 2458 route (every W 25/32 with cc 40/50 at G 10/14, and G 7
  W 25 cc 40/50); nothing better. Slack 20 and cc 30 are worse. The 2458 is a stable optimum for this search.

### L21 speed: sub-40 push (target <= 2423 frames, user 2026-10-25)
- 2458 vs the 2337 ghost-free walk per dot count (scratchpad lag.py -> `lag_2458.json`, `lag_floor.json`): ghost
  losses ~10-40 frames each around moves 8, 16-18, 25, 43-44, 53-55, 64-65, 71-73 (the fruit trips sit at
  different moves in the two, which muddles the rest). End gap 121.
- `sweep_prefix.sh` -> `sweep_prefix.txt`: --prefix = the 2458's first K moves (K 5..95 step 5), re-search on with
  the guide settings, beam {300,600}.
- Result: nothing under 2458. K >= 15 (except 50, 55) all rebuild the same 2458 route exactly; K 5/10/50/55 get
  2507-2765. The search re-converges on 2458 from anywhere along it.
- `--booey-depth N` (search.py): a death also retries the move 2 (.. N) back pressed late (then the moves after it on
  time). `result_L21_guide_bd2.json` (best settings + depth 2): 2458 again (12 two-back rescues).
- floor.py `--avoid JSON..`: milp cut: use a step outside each saved walk's step set, for new ghost-free guides.
  `chain_avoid.sh`: 4 chained (each avoids all before), milp 10 min, both fruits, keep 12 ->
  `result_floor_L21_avoid{1..4}.json` / `floor_L21_avoid{1..4}.log`.
- `neigh.py` -> `neigh_2458.txt`: the 737 one-move neighbors of the 2458 (at each move: another exit, a turn-back,
  or the turn pressed 2/4/6/8 frames late; the search itself only presses late to rescue deaths).
  `sweep_neigh.sh neigh_2458.txt n1`: --prefix each, re-search the rest (guide settings, beam 150) ->
  `neigh/n1_*`, `sweep_neigh_n1.txt`.
- n1 result (stopped at 322 + in-flight of 737, 2026-10-25 03:07): **2448 frames (40.39 s)**, move 67 (climb/neigh labels count from 0: "66") "L" pressed 2
  frames late ("L2") then the rest re-searched: `result_L21_neigh_2448.json` (= `neigh/n1_66_L2.json`), 99 moves,
  both fruits, minwin 5. Many other neighbors tie at 2458 with different routes.
- Round 2 (hill climb): `neigh_2448.txt` = the 2448's 740 neighbors minus 219 already run in n1 with the same prefix
  (the search is deterministic) -> `sweep_neigh.sh neigh_2448.txt n2`, `sweep_neigh_n2.txt`.
- n2 (stopped at ~100 of 521): **2438 frames (40.23 s)**, move 79 (label "78") "R" pressed 8 frames late ("R8"), rest re-searched:
  `result_L21_neigh_2438.json` (= `neigh/n2_78_R8.json`), 100 moves, both fruits, minwin 5.
- New `climb.py`: automates the hill climb (first verified improvement becomes the base at once; searched prefixes
  skipped). `climb.py result_L21_neigh_2438.json c1 --done <n1, n2 lists>` -> `climb/c1_*`, `climb_c1.txt`
  (every result), `climb_c1_best.txt` + `result_L21_climb_<frames>.json` (each new best).
- c1 stopped at ~285/465 (no improvement; several 2438 ties) to add `--sideways N` (when a round runs out, expand
  clears that tie the best) and `--done-climb TAG` (resume: skip a climb's searched prefixes, take its ties).
  Resumed as `climb.py result_L21_neigh_2438.json c2 --sideways 30 --done-climb c1 --done ...` -> `climb_c2.txt`.
- `chain_avoid.sh`: avoid1 = 291 steps, walks 2336/2337 (`result_floor_L21_avoid1.json`); avoid2's milp walk had no
  Euler ordering that drives clean (no result), so 3-4 failed too. (Claude Code's memory guard also reaped some idle
  watch loops at ~03:30: another process held 12.8 GB.)
- c2 finished round 0 (465 total): no improvement. Sideways: every 2438 "tie" re-searched to the same route (no new
  neighbors): 2438 is a one-move local optimum with late presses 2/4/6/8.
- neigh.py/climb.py `--ks` (late presses tried), climb.py `--guide`. `climb.py result_L21_neigh_2438.json c3 --ks 1..12
  --done-climb c1 c2 --done ...`: 1062 new neighbors -> `climb_c3.txt`.
- `climb.py result_L21_neigh_2438.json c4 --jobs 2 --guide result_floor_L21_avoid1.json` (alongside c3): the same
  neighbors re-searched following the avoid1 ghost-free walk (another step set) -> `climb_c4.txt`.
- c3 done (1062, late presses 1..12): no improvement over 2438.
- `climb.py result_L21_neigh_2438.json c5 --jobs 2 --beam 200 --guide-cost 7 --guide-slack 32` (alongside c4): other
  re-search settings -> `climb_c5.txt`.
- Video: `videos/L21_speed_2438_level21.mp4` (video_route.py; stock MAME 0.289 replays it: clear, 2438).
- Status 2026-10-25 08:22: c4 648/740 and c5 391/740 done, no improvement over 2438 (left running; results in
  `climb_c4.txt`, `climb_c5.txt`). **L21 speed, standing best: `result_L21_neigh_2438.json`, 2438 frames = 40.23 s**
  (sub-40 needs <= 2423).
- Correction: the 2438 never passes through a ghost (closest 7 px, move 70); its late presses are dodges.
- New `neigh2.py` (pairs: two turns from move 50 on, the second within the next 6, both pressed late by 2 or 8) and
  climb.py `--neigh/--neigh-args`. `climb.py result_L21_neigh_2438.json c6 --jobs 2 --neigh neigh2.py --neigh-args
  "2,8 50 6"`: 780 pairs -> `climb_c6.txt`.
- 2438's late presses (moves from 1): 60 R9 (from the 2458), 67 L2 (round 1), 69 D1 (a --booey rescue in round 1's re-search), 79 R8 (round 2). neigh/climb file labels (`n1_66_L2`, `n2_78_R8`) number moves from 0.
- Annotated video: `video_route.py ... --annotate` -> videos/L21_speed_2438_level21_annotated.mp4 (move n/100, press, late presses in yellow, frame count); replay cleared at 2438.
- Annotated video redone with one line under the maze (move n + press, late presses yellow, frame count); still clears at 2438.
- c4, c5 done (740 each), c6 done 11:19 (780 pairs, ks 2,8): no gain. c6: 50 tie 2438, then 22x2439, 5x2440,
  6x2441; 143 no-clear. 2438 is a local best for single changes and for 2/8-frame pairs.
- c7: `climb.py result_L21_neigh_2438.json c7 --jobs 4 --neigh neigh2.py --neigh-args "4,6 50 6"` (same pairs, presses
  4 or 6 late) -> `climb_c7.txt`.

### L21 118: safer upper-left ending (user hits blue's loop at the end)
- User's own ending (after move 112 at (6,5): R R U L L D R U) dies ON TIME at move 117 (8,1): blue loops
  down the left side, along row 5, up col 6 and right along the top row into Pac-Man; pink follows behind.
- `result_L21_safeend_k{96,102,110}_mg32` (prefix = 118's first K on time, --min-ghost 32 from K, --branch 4
  --late-budget 1): K96/K102 dead at once; K110 39 clears, best 124/93 (3289 fr): after 110 `LUULLLLLULDRDD` (left
  tunnel -> up col 21 -> row 5 leftward -> top-left corner -> down col 6), ghosts >= 32 px on time.
- `rank_sols` b1 L21 (`cmp_L21_118_vs_safe124`): 118 31 killers (ending: 108-110 late -> die at 114; 77 L2 ->
  117); safe124 34 (all 11 new at move 112, the tunnel: moves 96-107 3-4 late, also 14/62/77). Not better.
- `result_L21_safeend_k110_ot95_mg{32,24}`: same but late presses tested from move 96 (--prefix-on-time 95).
  mg32: no clear (every move-111 option dies in some late-press sim from moves 96-110). mg24 running.
  mg24 done: 7 clears, best 128/94 (3372 fr), survives single late presses from move 96 on.
- (A video of the 124 was made, then deleted at the user's request: they prefer the 118 ending and winging it.)

### L21 118: drift test of the endings, then a search robust to where blue is ("safe safe safe")
- User: the 124 (tunnel) ending fails for them (blue in the tunnel); they prefer the 118 ending and winging it, but
  want a very safe ending. Video of the 124 deleted (it was gitignored, never pushed).
- Spread-out drift kills the 118 mid-route: 1 frame late on 10% of turns dies at moves 37/45/46/78 in 8/8 tries.
  The 118 survives any ONE late press; combined drift is another matter.
- `drift_end.py` (moves 1-79 on time, 80-110 each turn 1-2 late w.p. 0.3, every ending on time from the result):
  s1 (60 tries, 44 alive at 110): s128 `UURRRURDLLLLLULDRR` 44/44, 118 30/44, user 24/44, rest <= 24.
  s2 (80 tries, 52 alive): s128 50/52, 118 27, user 27. Ending also drifted (`0.3 2 80 1`, s3): s128 38/45, 118 33/45,
  user 23/45. Harsher drift (p 0.5 k<=3, or from move 60) leaves almost nobody alive at 110.
- `drift_hist.py 24 11 hist_L21_drift80_s11.json` (24 drifted games alive at 110, from 38 tries; lateness runs on to
  move 160) -> `search.py --prefix <118 first 110> --history-sims ... --late-rel --beam 96` =
  `result_L21_safe3_hist24_s11`: an ending that survives all 24 (drifted ending presses included).
  19 clears; best 141/104 (3860 fr): after 110 `UUURDRURDLLLLLDDDRRDRURRURULURR` (top row right, up into the top-right
  corner, back along row 5, a big lap down col 6 / along the bottom / out the right tunnel, then the top-left last).
  Fresh drift (`drift_L21_ends_v_s4_e1`, sloppy ending presses too): s141 46/46, s128 38/46, 118 33/46, user 23/46.
  `drift_L21_ends_v_s5_e0` (on-time ending): s141 44/44, s128 43/44. On time the closest ghost is 20 px (last move).
- Video: `video_route.py result_L21_safe141.json 21 L21_safe141_level21 --annotate` -> clears at 3727 fr (61.5 s).
- Annotated videos for every README video (L1-4, 5-20 L5/L20, 118, safe141, speed 2458; same names); best/L21_safe141*.png sheets; READMEs + HANDOFF list the safe ending; 118 time corrected to 3040 fr (~50 s).

## 2026-10-25 speed-run pattern sheet
- `pattern_sheet.py` now draws routes with "x" turn-backs and late presses ("R9"): such routes are walked on pacemu
  (replay_route.play, `--level N`, default 21); the subtitle counts turn-backs and lists the late presses.
- best/L21_speed_2438.png and best/L21_speed_2438_screen.png; the screen one is in the README speed-run section.

## 2026-10-25 where the 2438 loses time (`lag_route.py`)
- New `lag_route.py <route.json>`: per move frames, tiles, new dots, tiles over eaten ground ("empty"). Pac-Man's
  speed depends only on his path, so ghosts cost time only through detours and waits.
- 2438: 104 empty tiles vs 91 in the ghost-free 2337 walk (an empty tile is ~6.7 frames: 9 tiles in 60-61 frames).
  Fruit trips: 2438 22 (moves 29-33) + 25 (76-82) = 47; floor 36 + 16 = 52. Everything else: 2438 57 vs floor 39.
- 2438 empty stretches outside the fruit trips: moves 6+8 (6, dots 12-16), 16-18 (8, after the x1 at move 15,
  dots 37), 25-26 (3), 36 (2), 43-44 (8), 48, 51 (2 each), 54-56 (8), 64-65 (6), 69 (4), 73, 88, 98 (2 each), 95, 100 (1).
  Floor by then: 3 empty by dot 26, 9 by dot 60.
- Late presses cost ~20 frames (move 60 R9: 38 fr for 4 tiles vs ~22; move 79 R8: 29 for 3 vs ~19).
- Gap 101 frames ~ 13 extra empty tiles (~87) + waits; sub-40 needs ~2-3 fewer empty tiles net.
