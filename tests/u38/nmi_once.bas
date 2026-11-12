; Ultra-38 B2.2: 20 single CIA 2 NMIs through TSB Neo's own NMI handler (KERNAL $FE43 -> ($0318) -> TSB, which
; switches CIA 2's interrupts off again) while BASIC and TSB code run; the program goes on unchanged.
10 poke 53280,11:poke 53281,12:poke 646,0:print chr$(14);chr$(147);"u38 nmi"
20 for k=1 to 20:poke 56580,100:poke 56581,0:poke 56589,129:poke 56590,25:for w=1 to 5:next:a=a+k:print at(2,k)"*"
30 next:poke 56589,127:print at(4,0)"nmi ok";a
