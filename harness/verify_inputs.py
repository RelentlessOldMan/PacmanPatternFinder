"""verify_inputs.py: record the per-frame joystick of a run, then replay just those inputs on a fresh pacemu and
count frames the replay_route.py way (calibrated on the 2438 route), with every score jump and any catch.
verify_inputs.py <reorder result json>  -> also writes <json>.inputs.json"""
import sys, json
from emu_server import Server
import booeywalk as B
import replay_route as rr


def record(fn):
    s = Server(); s.handle("newgame"); s.handle("level 21"); s.handle("msave s")
    s.handle("mload s L")
    log = []
    oj, ow = s.joy, s.wait
    cur = [None]
    s.joy = lambda d: (cur.__setitem__(0, d), oj(d))[1]
    def w(n=1):
        for _ in range(n):
            log.append(cur[0]); ow(1)
    s.wait = w
    out = fn(s)
    return log, out


def replay(inputs):
    s = Server(); s.handle("newgame"); s.handle("level 21"); s.handle("msave s"); s.handle("mload s L")
    f0, sc, jumps = s.frame, s.score(), []
    f0 -= 1
    for i, d in enumerate(inputs[1:]):
        s.joy(d); s.wait(1)
        s2 = s.score()
        if s2 - sc >= 100: jumps.append((s.frame - f0, s2 - sc))
        sc = s2
        if s.rd(0x4DA5): return "caught", s.frame - f0, jumps
        if s.dots() >= 244: return "clear", s.frame - f0, jumps
    return "ran out", s.frame - f0, jumps


# the run's own "mload s L" logs one frame (the load runs a frame); replay that load, then the rest. Frames count
# the load frame, like replay_route.py ("frames = 1  # the start state's load runs a frame") and booeywalk.play.
d = json.load(open(sys.argv[1]))
def pw(s):
    B.srv, B.P = s, None
    B.init(d["walk"])
    return B.play(d["late"])
inp2, out2 = record(pw)
r2 = replay(inp2)
print("walk via booeywalk:", out2, " inputs replayed:", r2[0], r2[1], "fruit/score jumps", r2[2])
json.dump({"inputs": inp2, "frames": r2[1]}, open(sys.argv[1] + ".inputs.json", "w"))
