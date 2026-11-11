; BASIC V2: arithmetic, precedence, numeric functions, number printing, integers, logic
10 print chr$(147);"v2 math"
20 a=7:b=-3:c=2.5:print a+b;a-b;a*b;a/b;a^2;-a
30 print 2+3*4-6/2;(2+3)*4;2^3^2;-2^2;10/4
40 print sgn(b);sgn(0);sgn(c);int(-2.5);int(2.5);abs(b);sqr(16)
50 print int(log(100)*1e6);int(exp(1)*1e6)
60 print int(sin(1)*1e6);int(cos(1)*1e6);int(tan(1)*1e6);int(atn(1)*1e6)
70 print 1e10;1.5e-5;123456789;1e9+1;.1+.2;1/3;-0
80 print 3.14159265358979;1e38;-1e-38;2^31
90 a%=-12345:b%=a%/7:print a%;b%;a% and 255;12 or 3;not 0;not -1
100 print 5>3;5<3;5=5;5<>5;5>=5;3<=2;"abc"<"abd";"b">"abc"
110 x=rnd(-1):r1=rnd(1):r2=rnd(1):print int(r1*1e6);int(r2*1e6)
120 def fn sq(x)=x*x+1:print fn sq(3);fn sq(-1.5)
130 print val("3.25e2");val("-12abc");val("x");str$(-12.5);str$(7)
140 print 255 and 15;256 or 1;-1 and 7;int(-0.5);int(1e9/7)
150 end
