; B1 benchmark: TSB screen block commands: FILL INV MOVE UPB FCOL
10 cls:for i=1 to 40:fill 0,0,40,25,i and 63,i and 15:inv 0,0,40,10:move 0,0,20,5,10,10
20 upb 0,0,40,25:fcol 0,0,40,25,(i+1) and 15:next
30 end
