#!/bin/bash
# watch_neigh.sh <summary.txt> <secs> <frames>: wait until a clear under <frames> appears or secs pass; drop finished runs' .ckpt
end=$((SECONDS+$2))
best(){ grep " clear " $1 | awk '{for(i=1;i<=NF;i++) if($i=="frames") print $(i-1), $1, $2}' | sort -n; }
until [ $SECONDS -ge $end ]; do
  for j in neigh/*.json; do [ -f $j.ckpt ] && [ -n "$(grep -l RESULT ${j%.json}.log 2>/dev/null)" ] && rm -f $j.ckpt; done
  [ -n "$(best $1 | awk -v t=$3 '$1<t' | head -1)" ] && break
  sleep 30
done
wc -l < $1; best $1 | head -5
