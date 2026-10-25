#!/bin/bash
# sweep_neigh.sh <neighbors.txt> <tag>: for each neighbor (neigh.py), --prefix it and re-search the rest with the
# guide settings (beam 150) -> neigh/<tag>_<i>_<alt>.{json,log}, summary sweep_neigh_<tag>.txt (i alt frames-line)
cd "$(dirname "$0")"
export C="--levels 21 --minwin 1 --corner-minwin 1 --no-late --late-budget 0 --family-depth 6 --family-cap 30 --backtracks 60 --solutions 50 --workers 3 --reverse-any --need-fruits 2 --frame-cost 1.0 --booey 12 --cluster-cost 40 --guide result_floor_L21_2fruit_trips.json --guide-cost 10 --guide-slack 25 --beam 150"
export TAG=$2
job(){ i=$1 a=$2 p=$3; n=neigh/${TAG}_${i}_${a}
  cw run --estimate 10m --owner "Claude Code (PacmanPatternFinder)" -- python -u search.py $C --prefix $p --out $n.json > $n.log 2>&1
  echo "$i $a | $( [ -f $n.json ] && python replay_route.py $n.json 21 2>&1 | tail -1 || grep -m1 'prefix fails' $n.log)" >> sweep_neigh_$TAG.txt; }
export -f job
xargs -P 4 -L 1 bash -c 'job $0 $1 $2' < $1
