#!/bin/bash
# chain_avoid.sh: L21 ghost-free floors with new step sets: floor.py --avoid every earlier step set (milp 10 min),
# both fruits, keep 12 -> result_floor_L21_avoid{1..4}.json
cd "$(dirname "$0")"
av="result_floor_L21_nofruit.json"
for i in 1 2 3 4; do
  PACMAN_NOGHOSTS=1 cw run --estimate 30m --owner "Claude Code (PacmanPatternFinder)" -- python -u floor.py --fruits 2 --keep 12 \
    --time-limit 600 --avoid $av --out result_floor_L21_avoid$i.json > floor_L21_avoid$i.log 2>&1
  av="$av result_floor_L21_avoid$i.json"
done
