; TSB control structures: REPEAT/UNTIL LOOP/EXIT IF/END LOOP DO/DONE PROC/EXEC/END PROC CALL ELSE CGOTO RESET RCOMP PAUSE
10 print chr$(147);"tsb structures"
20 i=0:repeat:i=i+1:until i=4:print "repeat";i
30 i=0:loop:i=i+1:exit if i>6:end loop:print "loop";i
40 i=3:if i=3 then print "then":else print "else wrong"
50 if i=4 then print "then wrong":else print "else"
60 if i>2 then do
70 print "do block"
80 done
90 if i>5 then do
100 print "do wrong"
110 done
120 exec sub1:print "after exec"
130 cgoto 140+10*2
140 print "cgoto wrong":end
160 print "cgoto ok"
170 reset 900:read r:print "reset";r
180 if i=3 then print "rcomp";
190 rcomp:print " again"
200 pause 1
210 x=0:repeat:x=x+1:if x=2 then print "two";
220 until x=3:print
230 call target
240 print "call wrong":end
300 proc target
310 print "call ok"
320 end
500 proc sub1
510 print "in sub1"
520 end proc
800 data 1
900 data 9
