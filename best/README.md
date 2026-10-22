# Best patterns so far (2026-10-22)

Level 1 is played by hand. Routes are the direction to leave each junction/corner with (R D L U),
starting from Pac-Man's start position heading left. Every route eats both fruits and never reverses.

| Levels | File | Moves | Turns | Timing (checked) |
|---|---|---|---|---|
| 2–4 | `L2-4.json` | 117 | 83 | jitter 0–8f 30/30 on L2–4; every turn k frames late: L2 ok to 11, L3 ok to 12, L4 dies at 9 and 11 |
| 5–8 | `L5-8.json` | 168 | 117 | **every combination of 0–10f late on every turn is safe** (exhaust.py) |
| 9–14 | `L9-14.json` | 178 | 122 | every combination of 0–10f late is safe **if move 5 is pressed within 6f** |
| 15–20 | `L15-20.json` | 171 | 116 | every combination of 0–10f late is safe **if move 5 is pressed within 6f**; safe to 9f without that |
| 21+ | `harness/result_L21.json` (old) | 140 | 102 | old search, timing-weak; not redone yet |

**Move 5** is the Down at the bottom-left corner (tile 1,26) right after the opening runs left along the
bottom: its window is only 6 frames, so hold Down early there. It's in the user's own opening.

5–20 share the first 139 moves (`harness/trunk139.txt`, through the lower-left energizer) and only split
after that. 2–4 and 5–20 both start with the user's opening (first 30 moves).

Videos of 5, 9, 15 and 20 played on time to a full clear: `videos/`.
