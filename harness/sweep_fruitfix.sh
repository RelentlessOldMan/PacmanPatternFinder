#!/bin/bash
# sweep_fruitfix.sh: the 2421 one-fruit L21 route's first K moves as --prefix, then search on needing both fruits
cd "$(dirname "$0")"
R=$(python -c "import json;print(json.load(open('result_L21_revany_fc1.25_cc40.json'))['route'])")
C="--levels 21 --minwin 1 --corner-minwin 1 --no-late --late-budget 0 --family-depth 6 --family-cap 30 --backtracks 60 --solutions 50 --workers 3 --reverse-any --beam 300 --need-fruits 2 --cluster-cost 40"
job(){ k=$1 fc=$2; n=fix_k${k}_fc${fc}; P=$(python -c "from search import tokens;print(''.join(tokens('$R')[:$k]))")
  cw run --estimate 60m --owner "Claude Code (PacmanPatternFinder)" -- python -u search.py $C --frame-cost $fc --prefix "$P" --out result_L21_$n.json > search_L21_$n.log 2>&1
  echo "$n | $(python replay_route.py result_L21_$n.json 21 2>&1 | tail -1)" >> sweep_fruitfix.txt; }
export -f job; export C R
for k in 20 26 32 38 44; do for fc in 1.0 1.25; do echo $k $fc; done; done | xargs -P 4 -L 1 bash -c 'job $0 $1'
