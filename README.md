# Pac-Man Pattern Finder

Pac-Man routes found by letting MAME 0.289 play the game headless under Lua control and searching over every
turn. There are two kinds, each on its own page:

- **[Tolerant patterns](tolerant/README.md)**: routes for playing by hand on real or emulated machines that are
  not perfect (input lag, a mushy stick, presses a few frames late). Each one was checked by replaying it with its
  turns pressed late. Levels 5–20 and 21+, with pattern diagrams and videos.
- **[Perfect-game speedrun](#perfect-game-speedrun)**: frame-exact routes for the fastest perfect-score game:
  every dot, fruit and ghost on every level, measured level by level against David Race (THE GOAT)'s 2013 record.
  Not meant to be played by hand.

## Tolerant patterns: [`tolerant/`](tolerant/README.md)

Patterns for playing by hand, with diagrams and videos for each:

| Levels | Pattern | What it does |
|---|---|---|
| 5–20 | [`L5-20_keep70_115`](tolerant/README.md#levels-520-leave-the-corners) | both fruits; leaves the corner pockets to eat by hand; any one turn can be pressed 1–4 frames late |
| 21+ | [`L21_safe141`](tolerant/README.md#levels-21-two-keys-full-clear) | full clear, both keys, with an ending that survives blue being out of place |

## Perfect-game speedrun

The other half of the project: frame-exact routes for the fastest perfect-score game (every dot, fruit and ghost on
every level), measured against David Race (THE GOAT)'s 2013 record. These are not meant to be played by hand.
This part is being reorganized; until then its files are in [`best/`](best/README.md).

## Running it

You need MAME 0.289 in `mame-0.289/` and your own legally obtained `pacman.zip` ROM in
`mame-0.289/roms/`. **No ROM or MAME binaries are included.** The search lives in `harness/`
(`search.py`, `rank_sols.py`, `server.lua`); `HANDOFF.md` has the full notes. `mame-patches/` has
optional MAME patches (in-memory save states, faster headless running).

## License

MIT, except `mame-patches/`, which is GPL-2.0-or-later like MAME. See [LICENSE](LICENSE).

Pac-Man is a trademark of Bandai Namco Entertainment Inc. This project is not affiliated with or
endorsed by Bandai Namco or the MAME project.
