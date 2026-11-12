; B1 benchmark: TSB hi-res graphics: LINE CIRCLE PLOT BLOCK TEST
10 hires 1,0:for i=0 to 199 step 4:line 0,i,319,199-i,1:next
20 for r=5 to 95 step 10:circle 160,100,r,r,1:next
30 for i=0 to 300:plot i,i and 127,1:t=t+test(i,i and 127):next:block 10,10,60,60,1
40 nrm
50 end
