; TSB ON KEY / DISABLE / RESUME
10 print chr$(147);"tsb on key"
20 on key "ab":goto 100
30 i=0:repeat:i=i+1:until i>3000
40 print "no key seen":end
100 print "on key";i>0;:disable
110 print " disabled"
120 end
