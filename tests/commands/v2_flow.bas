; BASIC V2: strings, FOR/NEXT, GOSUB, ON, IF, arrays, READ/DATA, PRINT formatting, PEEK/POKE/WAIT
10 print chr$(147);"v2 flow"
20 a$="commodore":b$=a$+" 64":print left$(a$,3);"/";right$(a$,4);"/";mid$(a$,3,4);"/";mid$(a$,5);len(b$)
30 print asc("a");chr$(65);chr$(48+5);left$("",2);len("")
40 for i=1 to 10 step 3:print i;:next:print:for i=3 to 1 step -1:print i;:next i:print
50 for i=1 to 3:for j=1 to 2:print i*10+j;:next j,i:print
60 gosub 500:on 2 gosub 510,520,530:on 3 goto 80,80,70
65 print "on goto failed":end
70 dim m(3,2),n$(4),k%(5):for i=0 to 3:for j=0 to 2:m(i,j)=i*j:next j,i:n$(4)="last":k%(5)=-1
80 print m(3,2);n$(4);k%(5)
90 read x,y$,z:print x;y$;z:restore:read w:print w
100 data 42,"hello, world",-7.5
110 print tab(5);"tab";spc(3);"spc";:print pos(0)
120 print 1,2,3:print "a";"b","c"
130 if a$="commodore" then print "if true"
140 if a$<>"commodore" then print "if wrong":end
150 let q=99:poke 828,123:print peek(828);:wait 828,64:print "wait ok"
160 s$="":for i=1 to 5:s$=s$+chr$(64+i):next:print s$;" ";fre(0)-fre(0)
170 i=0
180 i=i+1:if i<5 then 180
190 print "loop";i:x$="x":gosub 600:poke 828,96:poke 785,60:poke 786,3:clr:print "usr";usr(5)
200 sys 828:go to 205
205 print "sys, go to ok":end
500 print "gosub ok";:return
510 print " on1":return
520 print " on2":return
530 print " on3":return
600 print "nested";:gosub 610:print " back":return
610 print " deeper";:return
700 rem not reached
