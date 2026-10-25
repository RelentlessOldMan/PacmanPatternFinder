#!/bin/bash
# sweep_noise.sh: L21 speed restarts with --score-noise (need-fruits 2, cc 40); -> sweep_noise.txt
cd "$(dirname "$0")"
C="--levels 21 --minwin 1 --corner-minwin 1 --no-late --late-budget 0 --family-depth 6 --family-cap 30 --backtracks 60 --solutions 50 --workers 3 --reverse-any --beam 300 --need-fruits 2 --cluster-cost 40"
job(){ fc=$1 nz=$2 sd=$3; n=nz_fc${fc}_n${nz}_s${sd}
  cw run --estimate 60m --owner "Claude Code (PacmanPatternFinder)" -- python -u search.py $C --frame-cost $fc --score-noise $nz --seed $sd --out result_L21_$n.json > search_L21_$n.log 2>&1
  echo "$n | $(python replay_route.py result_L21_$n.json 21 2>&1 | tail -1)" >> sweep_noise.txt; }
export -f job; export C
for sd in 1 2 3 4 5 6 7 8; do for fc in 1.0 1.25; do for nz in 15 40; do echo $fc $nz $sd; done; done; done | xargs -P 4 -L 1 bash -c 'job $0 $1 $2'
