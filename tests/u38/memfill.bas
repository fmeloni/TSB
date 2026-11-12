; Ultra-38 B2.2: a float array fills BASIC memory up to $9FFF (MEMSIZ $A000), written and read back; PRINT AT (TSB)
; while the array lies in $8000-$9FFF; FRE(0) at the end. Ultra-38 only (TSB Neo has 30719 bytes): self-checking.
10 print chr$(147);"u38 memory"
20 f=fre(0):if f<0 then f=f+65536
30 n=int(f/5)-60:dim a(n)
40 for i=0 to n step 7:a(i)=i*3:next
50 e=0:for i=0 to n step 7:if a(i)<>i*3 then e=e+1
60 next
70 t=peek(49)+256*peek(50):print at(3,0)"arrays end";t;"errors";e
80 if t>40000 and t<40960 and e=0 then print at(5,0)"memfill ok"
90 g=fre(0):if g<0 then g=g+65536
100 print "free";g
