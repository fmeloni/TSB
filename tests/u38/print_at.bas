; Ultra-38 B2.2 subset: command dispatch and PRINT AT (TSB function AT in PRINT), strings built in BASIC memory
10 poke 53280,11:poke 53281,12:poke 646,0:print chr$(14);chr$(147);"u38 print at"
20 for i=2 to 9:print at(i,i*3)"row";i:next
30 print at(12,5)"at end"
40 a$="x":for i=1 to 5:a$=a$+"y":print at(13+i,i)a$:next
50 print at(20,0)"done"
