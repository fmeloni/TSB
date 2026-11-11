; TSB disk commands on a scratch disk: SAVE, DISK (rename, scratch), SCRSV/SCRLD (text screen), LOAD to an address
; (LOAD inside a program restarts it from the first line with variables kept, hence the A=0 guard), DIR
10 if a=1 then 80
20 print chr$(147);"tsb disk":save "@0:blk",8:save "@0:tmp",8
30 disk "r0:blk2=blk":disk "s0:tmp"
40 print "screen to save":scrsv 2,8,2,"scr,p,w"
50 print chr$(147);"cleared":scrld 2,8,2,"scr"
60 memclr $6000,4,0
70 a=1:load "blk2",8,0,$6000
80 print at(4,0)"loaded";peek($6000);peek($6001);peek($6002)
90 dir
100 end
