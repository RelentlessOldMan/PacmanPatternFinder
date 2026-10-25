#!/bin/bash
# watch_climb.sh <tag> <secs>: wait until sub-40 (<= 2423), the climb ends, or secs pass; then summarize
end=$((SECONDS+$2))
while [ $SECONDS -lt $end ]; do
  grep -q "# done" climb_$1.txt 2>/dev/null && break
  [ -s climb_$1_best.txt ] && awk '$1<=2423{f=1} END{exit !f}' climb_$1_best.txt && break
  sleep 30
done
date +%H:%M; cat climb_$1_best.txt 2>/dev/null; grep "^#" climb_$1.txt | tail -2; grep -vc "^#" climb_$1.txt
grep -v "^#" climb_$1.txt | awk '$4!="no-clear"' | sort -k4 -n | head -3; grep -h kept floor_L21_avoid*.log
