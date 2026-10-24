"""critical_move_104.py <out.png>: image of the 104-move route's critical move 27 and where its late press kills (75->76)."""
import json, sys
sys.path.insert(0, ".")
from PIL import Image, ImageDraw, ImageFont
import maze
from pattern_sheet import walk, draw_maze, draw_leg, centre, PW, PH, BG, FONT, BOLD

route = json.load(open("best_L5-20_2fruit_104.json"))["route"]
tiles, at = walk(route)
PAD, HEAD = 24, 120
img = Image.new("RGB", (PAD * 3 + PW * 2, HEAD + PH + PAD + 60), BG)
d = ImageDraw.Draw(img)
big, mid, small = ImageFont.truetype(BOLD, 34), ImageFont.truetype(BOLD, 22), ImageFont.truetype(FONT, 13)
d.text((PAD, 16), "104-move route: the critical move 27", font=big, fill=(255, 255, 255))
d.text((PAD, 62), "Move 27 is a LEFT turn. Press it 4 frames late and you die ~49 moves later, between moves 75 and 76",
       font=ImageFont.truetype(FONT, 20), fill=(230, 230, 230))
d.text((PAD, 88), "(levels 19 and 20 only). It's the only single late press that kills on levels 5-20.",
       font=ImageFont.truetype(FONT, 20), fill=(230, 230, 230))

def panel(ox, a, b, mark, label, col, title):
    oy = HEAD
    eaten = set(tiles[:at[a - 1] + 1]) if a > 1 else set()
    draw_maze(d, ox, oy, [t for t in maze.DOTS if t not in eaten])
    path = tiles[at[a - 1]:at[b - 1] + 2]
    draw_leg(d, ox, oy, path, col, [(m, tiles[at[m - 1]]) for m in range(a, b + 1)], small, True)
    x, y = centre(tiles[at[mark - 1]], ox, oy)
    if mark == 76:
        (x1, y1), (x2, y2) = centre(tiles[at[74]], ox, oy), centre(tiles[at[75]], ox, oy)
        x, y = (x1 + x2) // 2, (y1 + y2) // 2
    for r in (22, 28):
        d.ellipse([x - r, y - r, x + r, y + r], outline=(255, 255, 0), width=3)
    d.text((ox, oy + PH + 10), title, font=mid, fill=(255, 255, 0))
    d.text((ox, oy + PH + 38), label, font=ImageFont.truetype(FONT, 18), fill=(230, 230, 230))

panel(PAD, 21, 28, 27, "moves 21-28; dots shown as left at move 21", (80, 150, 255), "Move 27: turn LEFT here, on time")
panel(PAD * 2 + PW, 70, 77, 76, "moves 70-77; dots shown as left at move 70", (255, 70, 70), "Dies on the way from 75 up to 76")
img.save(sys.argv[1])
