; BASIC V2 I/O: GET, INPUT (typed by the harness), files on a scratch disk: OPEN/PRINT#/INPUT#/GET#/CLOSE/CMD, SAVE/VERIFY
10 print chr$(147);"v2 i/o"
20 input "name";n$:print "hi ";n$
30 input "two numbers";a,b:print a+b
40 get k$:if k$="" then 40
50 print "key ";k$;asc(k$)
60 open 2,8,2,"data,s,w":print#2,"line one":print#2,12345:print#2,"x";chr$(13);:close 2
70 open 2,8,2,"data,s,r":input#2,l$,v:get#2,g$:close 2:print l$;v;g$
80 open 15,8,15:input#15,e,e$,t,s:close 15:print e;e$;t;s
90 open 4,8,4,"cmdout,s,w":cmd 4:print "via cmd";:print#4:close 4
100 open 2,8,2,"cmdout,s,r":input#2,c$:close 2:print c$;st
110 save "@0:prog",8:verify "prog",8
120 print "saved"
130 end
