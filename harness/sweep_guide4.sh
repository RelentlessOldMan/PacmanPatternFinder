#!/bin/bash
# sweep_guide4.sh: L21 speed --guide 2337 walk, booey 12, no noise: G x W x cc around 10/25/40; -> sweep_guide4.txt
cd "$(dirname "$0")"
C="--levels 21 --minwin 1 --corner-minwin 1 --no-late --late-budget 0 --family-depth 6 --family-cap 30 --backtracks 60 --solutions 50 --workers 3 --reverse-any --beam 300 --need-fruits 2 --frame-cost 1.0 --booey 12"
job(){ gc=$1 sl=$2 cc=$3; n=guide4_gc${gc}_sl${sl}_cc${cc}
  cw run --estimate 20m --owner "Claude Code (PacmanPatternFinder)" -- python -u search.py $C --cluster-cost $cc --guide result_floor_L21_2fruit_trips.json --guide-cost $gc --guide-slack $sl --out result_L21_$n.json > search_L21_$n.log 2>&1
  echo "$n | $(python replay_route.py result_L21_$n.json 21 2>&1 | tail -1) | $(grep -o 'route=.*' search_L21_$n.log | tail -1 | grep -oE '[LRUD][0-9]+' | tr '\n' ' ')" >> sweep_guide4.txt; }
export -f job; export C
for gc in 7 10 14; do for sl in 20 25 32; do for cc in 30 40 50; do echo $gc $sl $cc; done; done; done | xargs -P 4 -L 1 bash -c 'job $0 $1 $2'
