# Full two-fruit clears of level 21 that start like the 5-20 route, longest shared start first.
# The 5-20 route dies on time at move 17 on level 21, so at most 16 moves can be shared.
R=LLDLLDRRURULURRURUURRRRDLDLLDLDDRRRURULDLUUULDRUURDLDRDLDDDRDRRRDRRDLLULURRRRULULDLULURULLLURDDDDDD
for n in 16 15 14 13 12 10 8 6; do
  python search.py --levels 21 --no-late --need-fruits 2 --beam 96 --workers 10 --safe-after 3 --gap-cost 5 --family-depth 6 --family-cap 12 --solutions 30 --prefix ${R:0:$n} --out result_L21_p$n.json > search_L21_p$n.log 2>&1
  grep -q 'cleared=True' search_L21_p$n.log && break
done
