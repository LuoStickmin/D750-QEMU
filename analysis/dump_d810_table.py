from pathlib import Path
p=Path(r'C:\Users\23795\Downloads\DSLR\D810_0114.bin.modules\b920_114.bin')
d=p.read_bytes()
lo=0x28B900; hi=0x28BB20
for off in range(lo,hi,16):
    b=d[off:off+16]
    hx=' '.join(f'{x:02x}' for x in b)
    asc=''.join(chr(x) if 32<=x<127 else '.' for x in b)
    print(f'{off:08x}  {hx:<47}  {asc}')
