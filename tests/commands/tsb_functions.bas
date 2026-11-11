; TSB functions and string tools: $ % $$ %% NRM EXOR MOD DIV FRAC DUP PLACE USE AT( CENTER LIN DISPLAY D!PEEK D!POKE MEMPEEK INSERT
10 print chr$(147);"tsb functions"
20 print $ff;%10100000;$c000+1;nrm("$1f");nrm("00000011");nrm("$c000")
30 print exor(255,15);mod(17,5);div(17,5);frac(3.75);frac(-1.25)
40 print $$255;" ";%%10;" ";$$4096;" ";%%(545+1328)
50 a$=dup("ab",4):print a$;len(a$);dup("-",10)
60 print place("lo","hello");place("x","hello")
70 use "####.##",3.14159:use "nr ##: -###,##",7,-12.345:use "+##",5
80 print at(9,10)"at 9,10";:print at(10,0)"";
90 center "centered":print
100 print lin;display;use
110 d!poke 828,$1234:print d!peek(828);peek(828);peek(829);mempeek(828)
120 insert "o-o! !o-o",14,0,12,5,7
130 print at(20,0)"";
140 end
