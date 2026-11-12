; Ultra-38 B2.2 subset: HIRES, PLOT, LINE (bitmap under the KERNAL through the RAM helpers), TEST
10 poke 53280,11:poke 53281,12:poke 646,0:print chr$(14);chr$(147);
20 hires 1,0
30 for i=0 to 100 step 10:line 0,i,319,199-i,1:next
40 for i=0 to 50:plot i*6,i*3,1:next:plot 10,10,0:line 300,0,300,199,1
50 t1=test(60,30):t2=test(61,30):t3=test(300,77)
60 get k$:if k$="" then 60
70 nrm:print "test";t1;t2;t3
