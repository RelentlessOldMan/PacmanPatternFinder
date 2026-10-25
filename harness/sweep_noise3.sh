#!/bin/bash
# sweep_noise3.sh: L21 speed restarts with --score-noise (need-fruits 2, noise 40; 3rd field = cluster cost); -> sweep_noise3.txt
cd "$(dirname "$0")"
C="--levels 21 --minwin 1 --corner-minwin 1 --no-late --late-budget 0 --family-depth 6 --family-cap 30 --backtracks 60 --solutions 50 --workers 3 --reverse-any --beam 300 --need-fruits 2"
job(){ fc=$1 nz=$2 sd=$3; n=nz3_fc${fc}_cc${nz}_s${sd}
  cw run --estimate 60m --owner "Claude Code (PacmanPatternFinder)" -- python -u search.py $C --frame-cost $fc --score-noise 40 --cluster-cost $nz --seed $sd --out result_L21_$n.json > search_L21_$n.log 2>&1
  echo "$n | $(python replay_route.py result_L21_$n.json 21 2>&1 | tail -1)" >> sweep_noise3.txt; }
export -f job; export C
for sd in 1 2 3 4 5 6 7 8; do for fc in 0.95 1.05; do for nz in 35 45; do echo $fc $nz $sd; done; done; done | xargs -P 4 -L 1 bash -c 'job $0 $1 $2'
