"""fruitfix.py: add a fruit-tile side trip to a reorder.py walk that clears with one fruit. Tries every visit of a
tile next to the fruit (row 17, cols 12/15) and inserts an out-and-back step onto it; late presses after the
insert shift with it."""
import sys, json
import booeywalk as B, reorder_check as C

FRUIT = {(12, 17): (13, 17), (15, 17): (14, 17)}


def tries(w, late):
    for j, t in enumerate(map(tuple, w)):
        if t in FRUIT and j + 1 < len(w) and tuple(w[j + 1]) != FRUIT[t] and (j == 0 or tuple(w[j - 1]) != FRUIT[t]):
            f = list(FRUIT[t])
            nw = w[:j + 1] + [f, list(t)] + w[j + 1:]
            nl = {(k + 2 if k > j else k): v for k, v in late.items()}
            yield j, nw, nl


if __name__ == "__main__":
    w, late = C.build(sys.argv[1], True, eval(sys.argv[2]))
    for j, nw, nl in tries(w, late):
        B.init(nw)
        r = B.play(nl)
        print(j, r, flush=True)
        if r[0] == "clear" and r[3] >= 2 and len(sys.argv) > 3:
            json.dump({"walk": nw, "late": nl, "frames": r[1], "fruits": r[3]}, open(sys.argv[3], "w"))
