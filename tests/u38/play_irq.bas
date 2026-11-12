; Ultra-38 B2.2 subset: MUSIC + PLAY, notes played from TSB's IRQ handler (SID trace compared)
10 poke 53280,11:poke 53281,12:poke 646,0:print chr$(14);chr$(147);"u38 play"
20 vol 15
30 envelope 1,5,1,13,9:envelope 2,6,1,12,8:envelope 3,1,1,1,1
40 wave 1,$40,$0800:wave 2,$20:wave 3,$10
50 music 8,"c4d4e4f4g4a4b4"
60 play 1
70 print "played"
