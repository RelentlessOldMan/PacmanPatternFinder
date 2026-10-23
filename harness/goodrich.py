"""Don Goodrich's level 21+ ("9th key") pattern, transcribed from the StrategyWiki diagram:
waypoints -> tiles -> TOK (node moves, plus one mid-corridor turnaround at (25,5)).
goodrich_late.py plays it on MAME and tests each turn 1-4 frames late."""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import maze
WP = [(13,23),
 (6,23),(6,26),(1,26),(1,29),(26,29),(26,26),(21,26),(21,23),(18,23),(18,26),(15,26),          # red
 (15,29),(1,29),(1,26),(6,26),(6,5),(21,5),(21,14),(18,14),(18,17),(9,17),(9,20),(12,20),(12,23),(15,23),(15,20),(21,20),  # green
 (21,5),(18,5),(18,8),(15,8),(15,11),(12,11),(12,8),(9,8),(9,5),(6,5),(6,1),(12,1),(12,5),     # blue
 (1,5),(1,8),(6,8),(6,20),(12,20),(12,23),(21,23),(21,20),(26,20),(26,23),(24,23),(24,26),(21,26),  # orange
 (21,20),(18,20),(18,17),(9,17),(9,14),('T',),(21,14),(21,8),(26,8),(26,1),(21,1),(21,5),(25,5),(21,5),(21,1),(15,1),(15,5),(6,5),(6,1),(1,1),(1,8),(6,8),  # yellow
 (6,20),(1,20),(1,23),(3,23),(3,26),(6,26),(6,23),(9,23),(9,26),(12,26),(12,28)]  # cyan
seq=[((13,23),None)]; cur=(13,23)
for wp in WP[1:]:
    if wp==('T',):
        while cur!=(-2,14): cur=maze.step(*cur,'L'); seq.append((cur,'L'))
        cur=(29,14); seq.append((cur,'L')); continue
    c,r=cur; tc,tr=wp
    assert c==tc or r==tr, (cur,wp)
    d = 'R' if tc>c else 'L' if tc<c else 'D' if tr>r else 'U'
    while cur!=wp:
        cur=maze.step(*cur,d); assert maze.is_open(*cur),(cur,wp); seq.append((cur,d))
moves=[]; turns=0; held='L'; rev=0
for i in range(len(seq)-1):
    t=seq[i][0]; dout=seq[i+1][1]; din=seq[i][1] or 'L'
    if dout==maze.REV[din]: rev+=1
    if maze.is_node(*t) or dout!=din:
        if i>0 or True:
            moves.append(dout)
            if dout!=held: turns+=1
        held=dout
eaten={t for t,_ in seq}&maze.DOTS
print("moves",len(moves),"turns",turns,"reverses",rev,"dots",len(eaten),"missing",sorted(maze.DOTS-eaten))
print("tiles",len(seq))
print(''.join(moves))
# tokens: node moves as letters; a mid-corridor turnaround as ("rev", d, tile)
TOK=[]; held='L'
for i in range(len(seq)-1):
    t=seq[i][0]; dout=seq[i+1][1]; din=seq[i][1] or 'L'
    if maze.is_node(*t): TOK.append(dout)
    elif dout!=din: TOK.append(("rev",dout,t))
