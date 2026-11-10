import sys
m=open(sys.argv[1],'rb').read()[2:]
d=m[0x400:0x7e8]
lower = '-l' in sys.argv   # lower/upper case charset (TSB demos switch to it)
def ch(c):
    c&=0x7f
    if c==0: return '@'
    if 1<=c<=26: return chr(96+c) if lower else chr(64+c)
    if 32<=c<=63: return chr(c)
    if lower and 65<=c<=90: return chr(c)
    return '.'
for r in range(25):
    line=''.join(ch(b) for b in d[r*40:r*40+40]).rstrip()
    if line: print(f"{r:2}|{line}")
w=lambda a: m[a]|m[a+1]<<8
print("TXTTAB=$%04X VARTAB=$%04X ARYTAB=$%04X STREND=$%04X FRETOP=$%04X MEMSIZ=$%04X  $01=%02X"%(w(0x2b),w(0x2d),w(0x2f),w(0x31),w(0x33),w(0x37),m[1]))
