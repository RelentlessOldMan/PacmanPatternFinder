#!/bin/bash
# sweep_guide2.sh: L21 speed each kept floor walk as --guide (G 10, W 25, cc 40), booey 12; -> sweep_guide2.txt
cd "$(dirname "$0")"
C="--levels 21 --minwin 1 --corner-minwin 1 --no-late --late-budget 0 --family-depth 6 --family-cap 30 --backtracks 60 --solutions 50 --workers 3 --reverse-any --beam 300 --need-fruits 2 --frame-cost 1.0 --booey 12"
job(){ w=$1; gc=10 sl=25 cc=40; n=guide2_w${w}
  cw run --estimate 20m --owner "Claude Code (PacmanPatternFinder)" -- python -u search.py $C --cluster-cost $cc --guide result_floor_L21_2fruit_keep40.json:$w --guide-cost $gc --guide-slack $sl --out result_L21_$n.json > search_L21_$n.log 2>&1
  echo "$n | $(python replay_route.py result_L21_$n.json 21 2>&1 | tail -1) | $(grep -o 'route=.*' search_L21_$n.log | tail -1 | grep -oE '[LRUD][0-9]+' | tr '\n' ' ')" >> sweep_guide2.txt; }
export -f job; export C
seq 0 11 | xargs -P 4 -L 1 bash -c 'job $0'
