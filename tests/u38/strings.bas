; Ultra-38 B2.2: string-heavy program: 151 strings built with TSB's DUP and BASIC V2 (+, MID$), garbage collection
; (FRE), checked again; the string area lies in $8000-$9FFF (strings grow down from MEMSIZ $A000). Self-checking.
10 print chr$(147);"u38 strings"
20 dim s$(150):for i=0 to 150:c$=chr$(65+i-26*int(i/26)):s$(i)=dup(c$,i-50*int(i/50))+c$:next
30 for k=1 to 3:for i=0 to 150 step 3:s$(i)=s$(i)+"":next:x=fre(0):next
40 e=0:for i=0 to 150:c$=chr$(65+i-26*int(i/26)):l=i-50*int(i/50)+1
50 if len(s$(i))<>l or mid$(s$(i),l,1)<>c$ or left$(s$(i),1)<>c$ then e=e+1
60 next
70 b=peek(51)+256*peek(52):print at(3,0)"bottom";b;"errors";e
80 print at(4,0)s$(77)
90 if e=0 and b>=32768 then print at(6,0)"strings ok"
