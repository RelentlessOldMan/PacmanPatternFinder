"""reorder_check.py: rebuild a reorder.py walk from its moves and replay it, logging score jumps (fruit check)."""
import sys, json
import booeywalk as B, reorder as R


def build(walkfile, mirror, moves, slack=99):
    w = [list(t) for t in json.load(open(walkfile))["walk"]]
    if mirror:
        w = [[13, 23]] + [[27 - c, r] for c, r in w]
    late = {}
    for m in moves:
        if m[0] == "late":
            late[m[1]] = m[2]
        elif m[0] == "2opt":
            w = dict((ij, nw) for ij, nw in R.two_opt(w, m[1], 0, len(w), 99) if ij == tuple(m))[tuple(m)]
        else:
            i, j = m
            w = w[:i] + w[i:j + 1][::-1] + w[j + 1:]
    return w, late


if __name__ == "__main__":
    w, late = build(sys.argv[1], True, eval(sys.argv[2]))
    B.init(w)
    sc = B.srv.score
    orig = B.srv.wait
    log = []
    last = [sc()]
    def wait(n):
        orig(n); s = sc()
        if s - last[0] >= 100: log.append((B.srv.frame, s - last[0]))
        last[0] = s
    B.srv.wait = wait
    print(B.play(late), log)
