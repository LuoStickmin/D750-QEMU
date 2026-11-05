from pathlib import Path
p = Path(r'C:\Users\23795\Downloads\DSLR\D750_0115.dec.modules\b1010_115a.bin')
d = p.read_bytes()
for center, before, after in [(0x1b4d80, 0x100, 0x300), (0xe4460, 0x80, 0x180), (0x16e0a0, 0x80, 0x180), (0x2f1760, 0x40, 0x400), (0x1266860, 0x80, 0x100)]:
    print('=' * 20, hex(center))
    lo = max(0, center - before)
    hi = min(len(d), center + after)
    for off in range(lo, hi, 16):
        b = d[off:off+16]
        hx = ' '.join(f'{x:02x}' for x in b)
        asc = ''.join(chr(x) if 32 <= x < 127 else '.' for x in b)
        print(f'{off:08x}  {hx:<47}  {asc}')
