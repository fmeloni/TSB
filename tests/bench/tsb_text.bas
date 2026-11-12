; B1 benchmark: TSB text and string functions: PRINT AT, DUP, PLACE, CENTER, INSERT, USE
10 cls:for i=1 to 150:print at(i and 15,0)dup("*",i and 31);:a$=dup("ab",5):p=place("ba",a$)
20 print at(20,0)"";:center "tsb":use "####.##",i/7:next
30 end
