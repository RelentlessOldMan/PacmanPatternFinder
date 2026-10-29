# Pac-Man Pattern Finder

Finds memorable, timing-tolerant Pac-Man patterns by letting MAME play the game headless under
Lua control: a beam search over routes (junction to junction, no reversing), then every route is
replayed with each turn pressed 1–4 frames late to find the ones that forgive sloppy timing.

The point is not "perfect" frame-exact routes for a real arcade cabinet. It is routes that survive
crappy or emulated machines: input lag, a mushy stick or keyboard, presses that land a few frames
late. Routes are ranked by how much of that they forgive. Published arcade patterns often fail on MAME, so
these were found and checked on MAME 0.289.

## The patterns

Routes are the direction to leave each junction or corner (R D L U), starting from Pac-Man's start
heading left. Details, timing data and older patterns are in [`best/`](best/README.md).

| Levels | File | Moves / turns | Notes |
|---|---|---|---|
| 1 | `best/L1_allghosts_129.json` | 129 / 95 | all 16 ghosts, both fruits, full clear |
| 2 | `best/L2_allghosts_139.json` | 139 / 102 | all 16 ghosts, both fruits, full clear |
| 3 | `best/L3_allghosts_147.json` | 147 / 107 | all 16 ghosts, both fruits, full clear |
| 4 | `best/L4_allghosts_171.json` | 171 / 130 | all 16 ghosts, both fruits, full clear |
| 5–20 | `best/L5-20_keep70_115.json` | 115 / 78 | **leave the corners**: eats both fruits, leaves the corner pockets to eat by hand; any one turn can be pressed 1–4 frames late |
| 21+ | `best/L21_full_118.json` | 118 / 88 | **2-fruit full clear**, ~50 s; starts like 5–20 |
| 21+ (safe) | `best/L21_safe141.json` | 141 / 104 | the 118 to move 110, then an ending that dodges blue wherever it is, ~61 s |

The level 1–4 ghost routes need exact timing: a late press can cost a ghost or a life (see [`best/`](best/README.md)).
The 5–20 and 21+ routes are the timing-tolerant ones.

Every video is played by MAME exactly on time, with a line under the maze giving the move number, the press
and the frame count.

### Levels 1–4: all the ghosts

Videos: [level 1](videos/L1_16ghosts_129_level1.mp4),
[level 2](videos/L2_16ghosts_139_level2.mp4), [level 3](videos/L3_16ghosts_147_level3.mp4),
[level 4](videos/L4_16ghosts_171_level4.mp4).

![Level 1 pattern](best/L1_allghosts_129_screen.png)

![Level 2 pattern](best/L2_allghosts_139_screen.png)

![Level 3 pattern](best/L3_allghosts_147_screen.png)

![Level 4 pattern](best/L4_allghosts_171_screen.png)

### Levels 5–20: leave the corners

Videos: [level 5](videos/L5-20_keep70_115_level5.mp4) and [level 20](videos/L5-20_keep70_115_level20.mp4)
(the corner dots are left to eat by hand).

![Levels 5-20 pattern](best/L5-20_115_screen.png)

### Levels 21+: two fruits, full clear

Video: [level 21](videos/L21_118_level21.mp4).

![Levels 21+ pattern](best/L21_118_screen.png)

**Safe ending** (`best/L21_safe141.json`, video: [level 21](videos/L21_safe141_level21.mp4)): the 118's ending
(moves 111–118) works when you are on time, but if earlier presses drift a little, blue can be waiting in the
top left. The safe ending plays the 118 up to move 110, then goes along the top row to the top-right corner,
back along row 5, takes a lap down the left-middle corridor, along the bottom and out the right tunnel, and eats
the top-left dots last. It was searched against 24 simulated sloppy games (turns from move 80 on pressed 1–2
frames late at random) and then survived all 90 fresh ones it was checked on (`harness/drift_end.py`), against
33 of 46 for the 118's own ending. It costs about 11 s.

![Levels 21+ safe ending](best/L21_safe141_screen.png)

Plain drawn versions of every sheet, without game graphics, are in `best/` (made by `harness/pattern_sheet.py`).

For comparison, Don Goodrich's well-known level 21+ "9th key" pattern
([StrategyWiki](https://strategywiki.org/wiki/Pac-Man/Walkthrough)) is 117 moves / 84 turns with one
reverse and takes ~53 s. It clears on MAME when played exactly on time, but 131 single late presses
kill it versus 31 for the 118/88 (`harness/goodrich_late.py`).

### Level 21+ speed run (just for fun)

Video: [level 21 in 2316 frames](videos/L21_speed_2316_level21.mp4) (38.21 s from start to clear, both fruits;
the bar under the maze shows the joystick on every frame, at the game's own 60.606 fps). Route: `best/L21_speed_2316.json`. It is frame-exact and not meant for human play: it is stored as the
tile walk Pac-Man takes plus the joystick direction held on every frame, and replaying just those inputs in
stock MAME 0.289 clears in 2316 frames (`harness/video_walk.py`).

To watch it in your own MAME 0.289, download `best/L21_speed_2316.inp` and `best/L21_skip.lua` into one folder and run
`mame pacman -autoboot_script L21_skip.lua -playback L21_speed_2316.inp -input_directory .` from it. A .inp only
records inputs, so the skip script must run on playback too: it marks levels 1-20 cleared as each starts, at full
speed, then the recorded run plays on level 21 at normal speed (made by `harness/record_inp.py`, which plays the
.inp back and checks it clears in 2316 frames).

How it was found: start from a short ghost-free walk that eats every dot and both fruits, mirror it left to right
(the maze is symmetric, but the ghosts are not, so the mirrored walk meets them later), then reorder it: reverse
stretches of the walk, reconnect them by shortest paths, and press a few turns a few frames late, playing every
candidate with the real ghosts and keeping the ones that get furthest (`harness/reorder.py`). A fruit that
disappears uneaten counts as a failure. The ghost-free walks come from `harness/tripsets.py`: it solves the
shortest eat-every-dot walk (`harness/floor.py`) many times with small random costs, so each solve gives a
slightly different set of steps; it orders each set's steps in every way it can, then adds the cheapest side
trips through the fruit spot that land while each fruit is out. The fruit only counts as eaten when Pac-Man
crosses between the two tiles under it. The 2316 started from a 2287-frame ghost-free walk, mirrored, with three
stretches reversed and one turn pressed late. The fastest ghost-free walk found so far
takes 2272 frames. The log is in `harness/RUNS.md`.

## Running it

You need MAME 0.289 in `mame-0.289/` and your own legally obtained `pacman.zip` ROM in
`mame-0.289/roms/`. **No ROM or MAME binaries are included.** The search lives in `harness/`
(`search.py`, `rank_sols.py`, `server.lua`); `HANDOFF.md` has the full notes. `mame-patches/` has
optional MAME patches (in-memory save states, faster headless running).

## License

MIT, except `mame-patches/`, which is GPL-2.0-or-later like MAME. See [LICENSE](LICENSE).

Pac-Man is a trademark of Bandai Namco Entertainment Inc. This project is not affiliated with or
endorsed by Bandai Namco or the MAME project.
