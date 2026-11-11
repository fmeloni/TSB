; TSB misc statements: KEYGET, ERROR, X! without extension, DELAY, GRAPHICS, LOCAL/GLOBAL (disk build), BCKGNDS (ECM)
10 print chr$(147);"tsb misc"
20 print "key?":keyget k$:print "keyget ";k$
30 print at(3,0)"";:error
40 on error:goto 900
50 x!
60 no error
70 delay 5:print "delay ok"
80 g=graphics:print "graphics";g
90 a=1:b=2:local b:b=9:print "local";a;b:global:print "global";a;b
100 bckgnds 6,2,5,7:print at(10,0)"ecm text":print at(11,0)chr$(18)"ecm rvs"chr$(146)
110 print "end ok"
120 end
900 print "x! error";errn;:out:print:resume next
