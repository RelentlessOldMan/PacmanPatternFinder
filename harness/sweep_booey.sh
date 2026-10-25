#!/bin/bash
# sweep_booey.sh: L21 speed restarts with --booey K (late-press retries of deadly moves; noise 40); -> sweep_booey.txt
cd "$(dirname "$0")"
C="--levels 21 --minwin 1 --corner-minwin 1 --no-late --late-budget 0 --family-depth 6 --family-cap 30 --backtracks 60 --solutions 50 --workers 3 --reverse-any --beam 300 --need-fruits 2 --frame-cost 1.0 --cluster-cost 40"
job(){ k=$1 sd=$2; n=booey${k}_n40_s${sd}
  cw run --estimate 20m --owner "Claude Code (PacmanPatternFinder)" -- python -u search.py $C --score-noise 40 --seed $sd --booey $k --out result_L21_$n.json > search_L21_$n.log 2>&1
  echo "$n | $(python replay_route.py result_L21_$n.json 21 2>&1 | tail -1) | $(grep -o 'route=.*' search_L21_$n.log | tail -1 | grep -oE '[LRUD][0-9]+' | tr '\n' ' ')" >> sweep_booey.txt; }
export -f job; export C
for sd in 1 2 3 4 5 6 7 8; do for k in 12 6; do echo $k $sd; done; done | xargs -P 4 -L 1 bash -c 'job $0 $1'
