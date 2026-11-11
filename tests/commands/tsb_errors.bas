; TSB error handling: ON ERROR: GOTO / ERRN / ERRLN / OUT / RESUME / NO ERROR
10 on error:goto 1000
20 print chr$(147);"tsb errors"
30 x=1/0:print "after /0"
40 dim q(2):q(5)=1:print "after subscript"
50 x$="a"+1:print "after mismatch"
60 print sqr(-1):print "after quantity"
70 no error
80 for i=1 to 4:out i:print:next
90 print "done"
100 end
1000 print "err";errn;"line";errln;" ";:out:print
1010 resume next
