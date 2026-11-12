; Ultra-38 B2.2: interrupt stress (as 2.1 T5). CIA 1 IRQs every 3036 cycles (KERNAL + TSB's IRQ handler) and CIA 2
; NMIs every 1734 cycles while PROC/EXEC, DO/DONE, HIRES+LINE+TEST (pixels through the KERNAL-off helpers),
; PRINT AT and string work run three times. The NMIs go to a counting handler at $033C (TSB Neo's own handler switches
; CIA 2's interrupts off, so it would see only the first); the NMI path into it is the KERNAL's, or Ultra-38's RAM
; vector when a helper has the KERNAL off. Then NMIs off, $0318 back, the KERNAL's IRQ timer back (SYS 64989 = $FDDD,
; PAL or NTSC value). NMIs only on Ultra-38 (MEMSIZ $A000, line 35): TSB Neo's RAM NMI vector (for NMIs while its
; KERNAL is off) does not switch the KERNAL off again, so Neo itself cannot take them during hi-res drawing. The result
; must equal TSB Neo's run (without NMIs) exactly.
10 poke 53280,11:poke 53281,12:poke 646,0:print chr$(14);chr$(147);"u38 stress"
20 for i=0 to 13:read d:poke 828+i,d:next:poke 864,0:poke 865,0:poke 866,peek(792):poke 867,peek(793)
25 data 72,173,13,221,238,96,3,208,3,238,97,3,104,64
30 poke 56324,219:poke 56325,11:poke 792,60:poke 793,3
35 if peek(56)<160 then 40
36 poke 56580,197:poke 56581,6:poke 56589,129:poke 56590,17
40 for r=1 to 3
50 n=0:m=0:exec p1:print at(2,0)"proc";n;m
60 for i=1 to 4:if i>2 then do
70 s=s+i
80 done
90 next
100 hires 1,0:for i=0 to 60 step 6:line 0,i,200,60-i,1:next:t=t+test(100,30)+test(30,30):nrm
110 a$="":for i=1 to 30:a$=a$+chr$(65+i/2):next:print at(3+r,0)a$;s;t
120 next
130 poke 56590,0:poke 56589,127:poke 792,peek(866):poke 793,peek(867):sys 64989
140 print "stress done"
150 end
200 proc p1
210 n=n+1:exec p2
220 end proc
230 proc p2
240 m=m+1
250 end proc
