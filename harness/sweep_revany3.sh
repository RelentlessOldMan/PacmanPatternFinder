#!/bin/bash
# sweep_revany3.sh: L21 speed sweep need-fruits 2, high --frame-cost and --cluster-cost (--reverse-any); -> sweep_revany3.txt
cd "$(dirname "$0")"
C="--levels 21 --minwin 1 --corner-minwin 1 --no-late --late-budget 0 --family-depth 6 --family-cap 30 --backtracks 60 --solutions 50 --workers 3 --reverse-any --beam 300 --need-fruits 2"
job(){ fc=$1 cc=$2; n=nf2_fc${fc}_cc${cc}
  cw run --estimate 60m --owner "Claude Code (PacmanPatternFinder)" -- python -u search.py $C --frame-cost $fc --cluster-cost $cc --out result_L21_revany_$n.json > search_L21_revany_$n.log 2>&1
  echo "$n | $(python replay_route.py result_L21_revany_$n.json 21 2>&1 | tail -1)" >> sweep_revany3.txt; }
export -f job; export C
for fc in 1.0 1.25 1.6; do for cc in 40 60 90; do echo $fc $cc; done; done | xargs -P 4 -L 1 bash -c 'job $0 $1'
