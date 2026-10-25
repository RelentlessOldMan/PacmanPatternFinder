"""climb.py <route.json> <tag> [--jobs 4] [--beam 150]: hill climb on one-move neighbors (neigh.py). Each neighbor is
--prefix'ed and the rest re-searched (guide settings); the first verified faster clear (replay_route.py) becomes the
new base at once and its neighbors queue (prefixes already searched are skipped: the search is deterministic).
Runs in climb/<tag>_<round>_<i>_<alt>.{json,log}; every result in climb_<tag>.txt, each new best in climb_<tag>_best.txt."""
import argparse, json, os, queue, re, shutil, subprocess, sys, threading

ap = argparse.ArgumentParser()
ap.add_argument("route"); ap.add_argument("tag")
ap.add_argument("--jobs", type=int, default=4); ap.add_argument("--beam", type=int, default=150)
ap.add_argument("--ks", default="2,4,6,8", help="late presses tried (neigh.py)")
ap.add_argument("--guide", default="result_floor_L21_2fruit_trips.json", help="the re-search's --guide")
ap.add_argument("--guide-cost", default="10"); ap.add_argument("--guide-slack", default="25")
ap.add_argument("--extra", default="", help="more search.py flags for the re-search")
ap.add_argument("--sideways", type=int, default=0,
                help="when a round runs out, expand up to N clears that tie the best (other routes, same time)")
ap.add_argument("--done", nargs="*", default=[], help="earlier neigh summaries: (neighbors.txt, sweep.txt) pairs")
ap.add_argument("--done-climb", nargs="*", default=[], metavar="TAG",
                help="earlier climbs on the same base: skip their searched prefixes, take their ties")
args = ap.parse_args()
C = ("--levels 21 --minwin 1 --corner-minwin 1 --no-late --late-budget 0 --family-depth 6 --family-cap 30 --backtracks 60 "
     "--solutions 50 --workers 3 --reverse-any --need-fruits 2 --frame-cost 1.0 --booey 12 --cluster-cost 40 "
     f"--guide {args.guide} --guide-cost {args.guide_cost} --guide-slack {args.guide_slack} --beam {args.beam} {args.extra}").split()
os.makedirs("climb", exist_ok=True)
lock = threading.Lock()
done = set()  # prefixes searched
for nb, sw in zip(args.done[::2], args.done[1::2]):
    pre = {tuple(l.split()[:2]): l.split()[2] for l in open(nb)}
    done |= {pre[tuple(l.split()[:2])] for l in open(sw) if tuple(l.split()[:2]) in pre}
best = {"frames": json.load(open(args.route))["frames"], "file": args.route, "round": 0}
work = queue.Queue()
ties = []  # (route file) clears tying the best, not yet expanded (--sideways)
for tag in args.done_climb:
    pre = {}
    for f in os.listdir("climb"):
        if f.startswith(tag + "_neigh_r"):
            pre.update({(f[len(tag) + 8:-4], *l.split()[:2]): l.split()[2] for l in open("climb/" + f)})
    for l in open(f"climb_{tag}.txt"):
        if not l.startswith("#"):
            r, i, a, fr = l.split()
            done.add(pre[(r, i, a)])
            if fr == str(best["frames"]):
                ties.append(f"climb/{tag}_{r}_{i}_{a}.json")


def say(f, s):
    with open(f, "a") as o:
        o.write(s + "\n")


def enqueue(base, label=None):
    out = f"climb/{args.tag}_neigh_r{label or best['round']}.txt"
    subprocess.run([sys.executable, "neigh.py", base, out, args.ks], check=True, capture_output=True)
    while not work.empty():
        try:
            work.get_nowait()
        except queue.Empty:
            break
    n = 0
    for line in open(out):
        i, a, p = line.split()
        if p not in done:
            work.put((label or best["round"], i, a, p)); n += 1
    say(f"climb_{args.tag}.txt", f"# round {label or best['round']}: base {base} {best['frames']}: {n} new neighbors")


def worker():
    while True:
        try:
            rnd, i, a, p = work.get(timeout=5)
        except queue.Empty:
            with lock:
                if work.empty() and not any(t.is_alive() and t.name == "busy" for t in threading.enumerate()):
                    if not ties or args.sideways <= 0:
                        return
                    args.sideways -= 1
                    f = ties.pop(0)
                    enqueue(f, f"{best['round']}s{os.path.basename(f)[:-5]}")
            continue
        threading.current_thread().name = "busy"
        with lock:
            if p in done:
                threading.current_thread().name = "idle"; continue
            done.add(p)
        n = f"climb/{args.tag}_{rnd}_{i}_{a}"
        with open(n + ".log", "w") as log:
            subprocess.run(["cw", "run", "--estimate", "10m", "--owner", "Claude Code (PacmanPatternFinder)", "--",
                            sys.executable, "-u", "search.py", *C, "--prefix", p, "--out", n + ".json"],
                           stdout=log, stderr=subprocess.STDOUT)
        for f in (n + ".json.ckpt",):
            if os.path.exists(f):
                os.remove(f)
        m = re.search(r"RESULT cleared=(\w+) dots=\d+ frames=(\d+)", open(n + ".log").read())
        fr = int(m.group(2)) if m and m.group(1) == "True" else None
        say(f"climb_{args.tag}.txt", f"{rnd} {i} {a} {fr if fr else 'no-clear'}")
        if fr and fr == best["frames"]:
            with lock:
                ties.append(n + ".json")
        if fr and fr < best["frames"]:
            v = subprocess.run([sys.executable, "replay_route.py", n + ".json", "21"], capture_output=True, text=True).stdout
            vm = re.search(r"clear \S+ moves (\d+) frames", v)
            with lock:
                if vm and int(vm.group(1)) < best["frames"]:
                    best.update(frames=int(vm.group(1)), file=n + ".json", round=best["round"] + 1)
                    ties.clear()
                    shutil.copy(n + ".json", f"result_L21_climb_{best['frames']}.json")
                    say(f"climb_{args.tag}_best.txt", f"{best['frames']} round {best['round']} {n}.json")
                    enqueue(n + ".json")
        threading.current_thread().name = "idle"


enqueue(args.route)
ts = [threading.Thread(target=worker, name="idle") for _ in range(args.jobs)]
for t in ts:
    t.start()
for t in ts:
    t.join()
say(f"climb_{args.tag}.txt", f"# done: best {best['frames']} {best['file']}")
