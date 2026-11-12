; B1 benchmark: BASIC V2 strings, arrays and garbage collection (no TSB keyword)
10 dim a$(50):for j=1 to 6:for i=0 to 50:a$(i)=str$(i)+"x"+mid$("abcdefg",j,2):next
20 s$="":for i=0 to 50:s$=left$(s$+a$(i),60):next:next
30 end
