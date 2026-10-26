#!/bin/bash
# sweep_race3.sh: as sweep_race.sh, forced prefix x0RDLDL (Race opening); L21 speed guided by David Race's traced level-21 dot order (race21_walk.json); -> sweep_race3.txt
cd "$(dirname "$0")"
C="--levels 21 --minwin 1 --corner-minwin 1 --no-late --late-budget 0 --family-depth 6 --family-cap 30 --backtracks 60 --solutions 50 --workers 2 --reverse-any --beam 300 --frame-cost 1.0 --booey 12 --cluster-cost 40 --guide race21_walk.json --guide-slack 25 --prefix x0RDLDL"
job(){ nf=$1 gc=$2; n=race3_f${nf}_gc${gc}
  cw run --estimate 40m --owner "Claude Code (PacmanPatternFinder)" -- cmd //c "C:\Users\barne\.claude\bin\low.cmd" python -u search.py $C --need-fruits $nf --guide-cost $gc --out result_L21_$n.json > search_L21_$n.log 2>&1
  echo "$n | $(python replay_route.py result_L21_$n.json 21 2>&1 | tail -1) | $(python -c "import json;d=json.load(open('result_L21_$n.json'));print(d.get('frames'),d.get('fruits'),d.get('route'))" 2>&1)" >> sweep_race3.txt; }
export -f job; export C
for nf in 2 0; do for gc in 3; do echo $nf $gc; done; done | xargs -P 2 -L 1 bash -c 'job $0 $1'
