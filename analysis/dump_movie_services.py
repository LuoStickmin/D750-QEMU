from pathlib import Path
p = Path(r'C:\Users\23795\Downloads\DSLR\D750_0115.dec.modules\b1010_115a.bin')
d = p.read_bytes()
for center, before, after in [(0x12ad500, 0x300, 0x900)]:
    lo=max(0,center-before); hi=min(len(d),center+after)
    print('='*20, hex(center))
    for off in range(lo,hi,16):
        b=d[off:off+16]
        hx=' '.join(f'{x:02x}' for x in b)
        asc=''.join(chr(x) if 32<=x<127 else '.' for x in b)
        print(f'{off:08x}  {hx:<47}  {asc}')
