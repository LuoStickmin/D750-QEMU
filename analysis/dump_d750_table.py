from pathlib import Path
p=Path(r'C:\Users\23795\Downloads\DSLR\D750_0115.dec.modules\b1010_115a.bin')
d=p.read_bytes()
lo=0x2AA900; hi=0x2AAC00
for off in range(lo,hi,16):
    b=d[off:off+16]
    hx=' '.join(f'{x:02x}' for x in b)
    asc=''.join(chr(x) if 32<=x<127 else '.' for x in b)
    print(f'{off:08x}  {hx:<47}  {asc}')
