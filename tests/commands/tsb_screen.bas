; TSB text screen: CLS COLOR FCHR FCOL FILL INV MOVE UP/DOWN/LEFT/RIGHT B/W FLASH OFF BFLASH CSET
10 cls:color 0,6,1:print "tsb screen"
20 fchr 2,0,10,3,42
30 fcol 2,0,10,3,7
40 fill 2,12,8,3,81,5
50 print at(6,0)"inverse me";:inv 6,0,10,1
60 print at(8,0)"move me";:move 8,0,7,1,8,20
70 print at(10,0)"abcdefgh";:upb 10,0,8,1:print at(12,0)"ijklmnop";:downw 12,0,8,2
80 print at(15,0)"0123456789";:leftb 15,0,10,1:print at(16,0)"0123456789";:rightw 16,0,10,1
90 print at(17,0)"0123456789";:leftw 17,0,10,1:print at(18,0)"0123456789";:rightb 18,0,10,1
100 print at(19,0)"0123456789";:upw 19,0,10,2:print at(20,0)"0123456789";:downb 20,0,10,1
110 flash 7,10:pause 1:off
120 bflash 1,3,2:pause 1:bflash off
130 cset 0:color 0,6,1
140 print at(22,0)"";
150 end
