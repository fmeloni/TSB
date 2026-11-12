; B1 benchmark: BASIC V2 control flow: GOSUB/RETURN, GOTO, IF, ON (no TSB keyword)
10 n=0
20 n=n+1:gosub 100:if n<800 then 20
30 end
100 on (n and 3)+1 goto 110,120,130,140
110 x=x+1:return
120 x=x-1:return
130 y=y+1:return
140 y=y-1:return
