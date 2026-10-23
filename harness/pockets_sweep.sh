R=LLDLLDRRURULURRURUURRRRDLDLLDLDDRRRURULDLUUULDRUURDLDRDLDDDRDRRRDRRDLLULURRRRULULDLULURULLLURDDDDDD
for n in 95 90 85 80 70; do
  python search.py --levels 5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20 --no-late --need-fruits 1 --first-fruit --beam 64 --workers 10 --safe-after 3 --gap-cost 5 --family-depth 6 --family-cap 12 --solutions 50 --prefix ${R:0:$n} --out result_pockets_p$n.json > search_pockets_p$n.log 2>&1
  grep -q 'cleared=True' search_pockets_p$n.log && break
done
