# window.py on the 2438's middle (never rebuilt): same dots, faster at b, then the old suffix; 400k-node cap each
# usage: sweep_mid.sh "a1:b1 a2:b2 ..." outfile
for w in $1; do
  a=${w%:*}; b=${w#*:}
  echo "== $a-$b"
  cmd //c "C:\Users\barne\.claude\bin\low.cmd" python -u window.py ../best/L21_speed_2438.json $a $b win/mid_${a}_${b}.json --max-nodes 400000 </dev/null 2>&1 | grep -v "nodes, [0-9]* found"
done >> $2
