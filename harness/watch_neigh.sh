#!/bin/bash
# watch_neigh.sh <summary.txt> <secs>: wait until a clear under 2458 appears or secs pass; drop finished runs' .ckpt
end=$((SECONDS+$2))
best(){ grep " clear " $1 | awk '{for(i=1;i<=NF;i++) if($i=="frames") print $(i-1), $1, $2}' | sort -n; }
until [ $SECONDS -ge $end ]; do
  for j in neigh/*.json; do [ -f $j.ckpt ] && [ -n "$(grep -l RESULT ${j%.json}.log 2>/dev/null)" ] && rm -f $j.ckpt; done
  [ -n "$(best $1 | awk '$1<2458' | head -1)" ] && break
  sleep 30
done
wc -l < $1; best $1 | head -5
