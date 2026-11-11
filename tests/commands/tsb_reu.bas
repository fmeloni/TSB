; TSB REU commands (512 KB REU): MEMDEF MEMSAVE MEMLOAD MEMREAD MEMLEN MEMOR MEMPOS MEMCONT MEMRESTORE MEMCLR
10 print chr$(147);"tsb reu"
20 memclr $6000,16,17:memclr $6100,16,0
30 memdef 16,$6000,0,1:memsave
40 memdef 16,$6100,0,1:memload:print peek($6100);peek($610f)
50 memclr $6000,16,34:memlen 16:memor $6000:mempos 0,1:memread
60 print peek($6000);peek($6100)
70 memcont 1:memdef 8,$6200,0,1:memload:memcont 0:print peek($6200);peek($6207)
80 memrestore 0:memdef 4,$6300,100,7:memsave:memdef 4,$6304,100,7:memload:print peek($6304)
90 end
