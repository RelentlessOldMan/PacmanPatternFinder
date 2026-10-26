# sweep_noise.sh: reorder.py with a noisy beam ranking (seeds) on the walks that gave 2367/2391/2394; 4 at a time
run() { n=$1; shift; python -u reorder.py "$@" result_L21_ro6_$n.json --rounds 300 --beam 32 --before 60 --slack 10 --kmax 20 --budget 90 --jobs 2 --fruit-fail --mirror > ro6_$n.log 2>&1; echo "$n | $(grep -h '^done' ro6_$n.log)" >> sweep_noise.txt; }
K=result_floor_L21_2fruit_keep40.json
J=()
for s in 1 2 3 4 5 6; do
  J+=("w6s$s $K --walk-index 6 --seed $s --noise 40" "k40s$s $K --seed $s --noise 40")
  J+=("a1s$s result_floor_L21_avoid1.json --seed $s --noise 40")
done
for j in "${J[@]}"; do
  while [ $(jobs -r | wc -l) -ge 4 ]; do sleep 20; done
  set -- $j; n=$1; f=$2; shift 2
  run $n $f "$@" &
done
wait
