; Ultra-38 B2.2 subset: IF THEN ELSE, DO/DONE blocks (taken and skipped, nested IF inside)
10 poke 53280,11:poke 53281,12:poke 646,0:print chr$(14);chr$(147);"u38 do"
20 for i=1 to 4
30 if i=1 then print "one":else print "not one";i
40 if i>2 then do
50 print "big";i
60 if i=4 then print "four":else print "three"
70 done
80 if i<0 then do
90 print "never"
100 done
110 next
120 x=5:if x>9 then print "big x":else print "small x"
130 print "end"
