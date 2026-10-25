#!/bin/bash
# sweep_revany.sh: L21 speed sweep (--reverse-any), 4 jobs at a time; one line per job in sweep_revany.txt
cd "$(dirname "$0")"
C="--levels 21 --minwin 1 --corner-minwin 1 --no-late --late-budget 0 --family-depth 6 --backtracks 60 --solutions 50 --workers 3 --reverse-any"
job(){ fc=$1 b=$2 cap=$3 sd=$4; n=fc${fc}_b${b}_cap${cap}_s${sd}
  cw run --estimate 60m --owner "Claude Code (PacmanPatternFinder)" -- python -u search.py $C --frame-cost $fc --beam $b --family-cap $cap --seed $sd --out result_L21_revany_$n.json > search_L21_revany_$n.log 2>&1
  echo "$n | $(python replay_route.py result_L21_revany_$n.json 21 2>&1 | tail -1)" >> sweep_revany.txt; }
export -f job; export C
for fc in 0.15 0.25 0.4; do for b in 200 400; do for cap in 20 30 50; do for sd in 1 2; do echo $fc $b $cap $sd; done; done; done; done | xargs -P 4 -L 1 bash -c 'job $0 $1 $2 $3'
