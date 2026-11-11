; TSB MEM screen: MEMCLR, MEM (screen to $CC00, RAM charset), DISPLAY; CSET 0 afterwards keeps the MEM screen
10 print chr$(147);"tsb mem"
20 memclr 828,16,170:print peek(828);peek(843);peek(844)
30 mem:print "on mem screen";display
40 cset 0:print "back";display
50 end
