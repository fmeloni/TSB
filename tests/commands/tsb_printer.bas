; TSB printer output (device 4, captured raw): PRINT#, USE#, CMD, COPY (text screen), HRDCPY (hi-res)
10 print chr$(147);"printer test":print "second line"
20 open 4,4:print#4,"print# line";42:use#4,"use ###.#",3.14159:print#4
30 cmd 4:print "via cmd":print#4:close 4
40 copy
50 hires 1,0:circle 160,100,40,40,1:line 0,0,319,199,1:hrdcpy:nrm
60 print "printed"
70 end
