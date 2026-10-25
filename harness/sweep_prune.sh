#!/bin/bash
# sweep_prune.sh: L21 speed with fruitless pruning, beams 300-1000 near fc 1.0 / cc 40 (need-fruits 2, --reverse-any); -> sweep_prune.txt
cd "$(dirname "$0")"
C="--levels 21 --minwin 1 --corner-minwin 1 --no-late --late-budget 0 --family-depth 6 --family-cap 30 --backtracks 60 --solutions 50 --workers 3 --reverse-any --need-fruits 2"
job(){ b=$1 fc=$2 cc=$3; n=prune_b${b}_fc${fc}_cc${cc}
  cw run --estimate 60m --owner "Claude Code (PacmanPatternFinder)" -- python -u search.py $C --beam $b --frame-cost $fc --cluster-cost $cc --out result_L21_$n.json > search_L21_$n.log 2>&1
  echo "$n | $(python replay_route.py result_L21_$n.json 21 2>&1 | tail -1)" >> sweep_prune.txt; }
export -f job; export C
for b in 300 600 1000; do for fc in 0.8 0.9 1.0 1.1; do for cc in 30 40; do echo $b $fc $cc; done; done; done | xargs -P 4 -L 1 bash -c 'job $0 $1 $2'
