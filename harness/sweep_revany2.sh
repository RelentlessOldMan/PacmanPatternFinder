#!/bin/bash
# sweep_revany2.sh: L21 speed sweep at high --frame-cost with --cluster-cost (--reverse-any); -> sweep_revany2.txt
cd "$(dirname "$0")"
C="--levels 21 --minwin 1 --corner-minwin 1 --no-late --late-budget 0 --family-depth 6 --family-cap 30 --backtracks 60 --solutions 50 --workers 3 --reverse-any --beam 300"
job(){ fc=$1 cc=$2; n=fc${fc}_cc${cc}
  cw run --estimate 60m --owner "Claude Code (PacmanPatternFinder)" -- python -u search.py $C --frame-cost $fc --cluster-cost $cc --out result_L21_revany_$n.json > search_L21_revany_$n.log 2>&1
  echo "$n | $(python replay_route.py result_L21_revany_$n.json 21 2>&1 | tail -1)" >> sweep_revany2.txt; }
export -f job; export C
for fc in 0.6 1.0 1.25; do for cc in 0 20 40; do echo $fc $cc; done; done | xargs -P 4 -L 1 bash -c 'job $0 $1'
