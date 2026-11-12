; B1 benchmark: TSB structures and integer functions: REPEAT LOOP EXEC/PROC DIV MOD FRAC
10 i=0:repeat:i=i+1:x=div(i,7)+mod(i,7)+frac(i/3):until i=600
20 j=0:loop:j=j+1:exit if j>400:x=x+1:end loop
30 for k=1 to 200:exec p1:next
40 end
100 proc p1
110 y=y+1
120 end proc
