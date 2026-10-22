"""Check that a state saved by one worker loads identically in another, immediately."""
from worker import Worker

a, b = Worker(), Worker()
a.cmd("newgame"); b.cmd("newgame")
for d in "ULUL":
    a.cmd(f"seg {d} E 0")
bad = 0
for i in range(30):
    a.cmd(f"seg {'UDLR'[i % 4]} E 0")
    a.cmd(f"save sl{i}")
    ha = a.cmd("hash").split()[1]
    b.cmd(f"load sl{i} L")
    hb = b.cmd("hash").split()[1]
    a.cmd(f"load sl{i} L")
    ha2 = a.cmd("hash").split()[1]
    if not (ha == hb == ha2):
        bad += 1
        print(i, "save:", ha, "otherload:", hb, "selfload:", ha2)
print("mismatches:", bad, "/ 30")
a.close(); b.close()
