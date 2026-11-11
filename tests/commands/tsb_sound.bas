; TSB sound: VOL WAVE ENVELOPE SOUND MUSIC PLAY (final SID registers compared)
10 print chr$(147);"tsb sound"
20 vol 15
30 envelope 1,5,1,13,9:envelope 2,6,1,12,8:envelope 3,1,1,1,1
40 wave 1,$40,$0800:wave 2,$20:wave 3,$10
50 sound 1,4000:sound 2,6000
60 music 10,"c4d4e4"
70 play 1
80 print "sound";sound
90 end
