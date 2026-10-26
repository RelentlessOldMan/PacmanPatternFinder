# sweep_reorder.sh: reorder.py (mirrored, fruit-aware, wide) over more floor walks, 3 at a time; summary -> sweep_reorder.txt
run() {  # name file extra...
  n=$1; f=$2; shift 2
  python -u reorder.py $f result_L21_ro5_$n.json --rounds 300 --beam 32 --before 60 --slack 10 --kmax 20 --budget 90 --jobs 2 --fruit-fail "$@" > ro5_$n.log 2>&1
  echo "$n | $(grep -h '^done' ro5_$n.log)" >> sweep_reorder.txt
}
K=result_floor_L21_2fruit_keep40.json
jobs=()
for i in 1 2 3 4 5 6 7 8 9 10 11; do jobs+=("k40w${i}m $K --walk-index $i --mirror"); done
jobs+=("avoid1w1m result_floor_L21_avoid1.json --walk-index 1 --mirror" "tripsm result_floor_L21_2fruit_trips.json --mirror"
       "keep40 $K" "avoid1 result_floor_L21_avoid1.json" "fv2 result_floor_L21_2fruit_fv2.json")
for j in "${jobs[@]}"; do
  while [ $(jobs -r | wc -l) -ge 3 ]; do sleep 20; done
  run $j &
done
wait
