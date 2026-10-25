#!/bin/bash
# sweep_prefix.sh: L21 speed: keep the first K moves of the 2458 route (--prefix), re-search the rest with --guide
# (G 10, W 25, cc 40, booey 12), beam {300,600}; -> sweep_prefix.txt
cd "$(dirname "$0")"
C="--levels 21 --minwin 1 --corner-minwin 1 --no-late --late-budget 0 --family-depth 6 --family-cap 30 --backtracks 60 --solutions 50 --workers 3 --reverse-any --need-fruits 2 --frame-cost 1.0 --booey 12 --cluster-cost 40 --guide result_floor_L21_2fruit_trips.json --guide-cost 10 --guide-slack 25"
R=$(python -c "import json,search;print(' '.join(search.tokens(json.load(open('result_L21_guide_gc10_sl25_cc40.json'))['route'])))")
job(){ k=$1 b=$2; n=prefix_k${k}_b${b}; p=$(echo $R | cut -d' ' -f1-$k | tr -d ' ')
  cw run --estimate 20m --owner "Claude Code (PacmanPatternFinder)" -- python -u search.py $C --beam $b --prefix $p --out result_L21_$n.json > search_L21_$n.log 2>&1
  echo "$n | $(python replay_route.py result_L21_$n.json 21 2>&1 | tail -1) | $(grep -o 'route=.*' search_L21_$n.log | tail -1 | grep -oE '[LRUD][0-9]+' | tr '\n' ' ')" >> sweep_prefix.txt; }
export -f job; export C R
for k in $(seq 5 5 95); do for b in 300 600; do echo $k $b; done; done | xargs -P 4 -L 1 bash -c 'job $0 $1'
