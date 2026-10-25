#!/bin/bash
# sweep_pull.sh: L21 speed with --fruit-pull (and fruitless pruning), need-fruits 2, beam 300; -> sweep_pull.txt
cd "$(dirname "$0")"
C="--levels 21 --minwin 1 --corner-minwin 1 --no-late --late-budget 0 --family-depth 6 --family-cap 30 --backtracks 60 --solutions 50 --workers 3 --reverse-any --need-fruits 2 --beam 300"
job(){ fp=$1 fc=$2 cc=$3; n=pull${fp}_fc${fc}_cc${cc}
  cw run --estimate 60m --owner "Claude Code (PacmanPatternFinder)" -- python -u search.py $C --fruit-pull $fp --frame-cost $fc --cluster-cost $cc --out result_L21_$n.json > search_L21_$n.log 2>&1
  echo "$n | $(python replay_route.py result_L21_$n.json 21 2>&1 | tail -1)" >> sweep_pull.txt; }
export -f job; export C
for fp in 3 8 15; do for fc in 0.9 1.0 1.1; do for cc in 30 40; do echo $fp $fc $cc; done; done; done | xargs -P 4 -L 1 bash -c 'job $0 $1 $2'
