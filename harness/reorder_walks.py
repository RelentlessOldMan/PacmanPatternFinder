"""reorder_walks.py: reorder.py with the ro5 settings (mirrored, fruit-fail; the 2367's) on chosen walks of a floor
result. reorder_walks.py <floor.json> <tag> <i,j,...> [--par 2] -> ro_<tag>w<i>m.log, result_L21_ro_<tag>w<i>m.json,
summary reorder_<tag>.txt (final line "all done")."""
import sys, subprocess, time
PY = sys.executable
f, tag, idx = sys.argv[1], sys.argv[2], [int(i) for i in sys.argv[3].split(",")]
PAR = int(sys.argv[sys.argv.index("--par") + 1]) if "--par" in sys.argv else 2
running = []
def reap():
    for j in running[:]:
        if j[1].poll() is not None:
            running.remove(j)
            done = [l for l in open("ro_%s.log" % j[0]) if l.startswith("done")]
            open("reorder_%s.txt" % tag, "a").write("%s | %s\n" % (j[0], done[-1].strip()[:80] if done else "no done line"))
for i in idx:
    while len(running) >= PAR:
        time.sleep(20); reap()
    name = "%sw%dm" % (tag, i)
    p = subprocess.Popen([PY, "-u", "reorder.py", f, "result_L21_ro_%s.json" % name, "--walk-index", str(i), "--mirror",
                          "--rounds", "300", "--beam", "32", "--before", "60", "--slack", "10", "--kmax", "20",
                          "--budget", "90", "--jobs", "2", "--fruit-fail"], stdout=open("ro_%s.log" % name, "w"),
                         stderr=subprocess.STDOUT)
    running.append((name, p))
while running:
    time.sleep(20); reap()
open("reorder_%s.txt" % tag, "a").write("all done %s\n" % time.ctime())
