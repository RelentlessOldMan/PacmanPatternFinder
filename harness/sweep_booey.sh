#!/bin/bash
# sweep_booey.sh: the 2458/2438 guide settings with stronger booey rescues (K frames late, up to D moves back) over
# several ghost-free guide walks; -> sweep_booey.txt
cd "$(dirname "$0")"
C="--levels 21 --minwin 1 --corner-minwin 1 --no-late --late-budget 0 --family-depth 6 --family-cap 30 --backtracks 60 --solutions 50 --workers 2 --reverse-any --beam 300 --frame-cost 1.0 --cluster-cost 40 --need-fruits 2 --guide-cost 10 --guide-slack 25"
job(){ k=$1 d=$2 g=$3 gt=$4; n=bq_k${k}_d${d}_${gt}
  cw run --estimate 60m --owner "Claude Code (PacmanPatternFinder)" -- cmd //c "C:\Users\barne\.claude\bin\low.cmd" python -u search.py $C --booey $k --booey-depth $d --guide $g --out result_L21_$n.json > search_L21_$n.log 2>&1
  echo "$n | $(python replay_route.py result_L21_$n.json 21 2>&1 | tail -1) | $(python -c "import json;d=json.load(open('result_L21_$n.json'));print(d.get('frames'),d.get('fruits'),d.get('route'))" 2>&1)" >> sweep_booey.txt; }
export -f job; export C
cat <<J | xargs -P 3 -L 1 bash -c 'job $0 $1 $2 $3'
24 2 result_floor_L21_2fruit_keep40.json keep40
24 3 result_floor_L21_2fruit_keep40.json keep40
24 2 result_floor_L21_avoid1.json avoid1
24 3 result_floor_L21_2fruit_fv2.json fv2
40 3 result_floor_L21_2fruit_keep40.json:5 keep40w5
40 3 result_floor_L21_avoid1.json:1 avoid1w1
J
