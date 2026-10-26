"""save_best.py <verified reorder result json> <walk name>: write best/L21_speed_<frames>.json (walk, late, inputs)."""
import sys, json
d = json.load(open(sys.argv[1]))
inp = json.load(open(sys.argv[1] + ".inputs.json"))
assert inp["frames"] == d["frames"], (inp["frames"], d["frames"])
out = {"levels": [21], "cleared": True, "dots": 244, "frames": d["frames"], "fruits": 2, "ghosts": 0, "kind": "walk",
       "how": f"reorder.py/polish.py: ghost-free floor walk {sys.argv[2]}, mirrored left-right (user's idea), reordered, live ghosts on pacemu; booeywalk.play(walk, late) replays it",
       "moves": d.get("moves", []), "walk": d["walk"], "late": d["late"],
       "inputs": inp["inputs"][1:], "inputs_note": "joystick per frame after the level-21 start state's load (None = released); verify_inputs.py"}
p = f"../best/L21_speed_{d['frames']}.json"
json.dump(out, open(p, "w")); print(p)
