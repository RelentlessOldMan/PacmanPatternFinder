"""Training run for build.bat's profile-guided build: late presses on the 5-20 and 21+ routes on
several levels, through emu_server like the search. Run with PACEMU_DLL = the instrumented DLL."""
import sys, random
sys.path.insert(0, "C:/Playground/PacmanPatternFinder/harness")
import emu_server as E
from emu_parity import ROUTES
rnd = random.Random(1)
s = E.Server(1)
for lv in (5, 9, 14, 21, 24):
    s.handle("newgame"); s.handle(f"level {lv}"); s.handle("msave st")
    route = ROUTES[21 if lv >= 21 else 5]
    for run in range(25):
        s.handle("mload st L"); held = "L"
        for d in route:
            if run and d != held and rnd.random() < 0.2:
                r = s.handle(f"segb {d} 4 t1 t2 t3 t4"); k = rnd.randint(1, 4)
                s.handle(f"mload t{k} {d}"); r = r.split(" | ")[k - 1]
            else:
                r = s.handle(f"seg {d} E 0")
            s.handle("hash")
            held = d
            if not r.startswith("ok"): break
print("trained")
