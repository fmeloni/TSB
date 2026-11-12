; Ultra-38 B2.2 subset: PROC / EXEC / END PROC (nested), CALL
10 poke 53280,11:poke 53281,12:poke 646,0:print chr$(14);chr$(147);"u38 proc"
20 n=0:m=0:exec p1:print "n";n;"m";m
30 for k=1 to 3:exec p2:next:print "k";k;"m";m
40 call p3
50 print "not here":end
100 proc p1
110 n=n+1:exec p2:n=n+10
120 end proc
200 proc p2
210 m=m+1
220 end proc
300 proc p3
310 print "p3";n;m
320 end
