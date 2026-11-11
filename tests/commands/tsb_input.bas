; TSB input: FETCH, DO NULL, INKEY, JOY, POT (keys typed by the harness). PENX/PENY wait for a light pen: not tested.
10 print chr$(147);"tsb input"
20 fetch "abc",3,a$:print:print "fetch ";a$
30 print "press key"
40 do null
50 print "do null ok"
60 i=0:repeat:k=inkey:i=i+1:until k or i>200:print "inkey";k
70 print joy(1);joy(2);pot(1);pot(2)
80 end
