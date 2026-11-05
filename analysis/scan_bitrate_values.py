from pathlib import Path
import struct
p = Path(r'C:\Users\23795\Downloads\DSLR\D750_0115.dec.modules\b1010_115a.bin')
d = p.read_bytes()
vals = {
 '42M': 42_000_000, '35M': 35_000_000, '36M': 36_000_000, '24M': 24_000_000,
 '20.34432M': 20_344_320, '20M': 20_000_000, '12M': 12_000_000, '10M': 10_000_000,
 '8M': 8_000_000, '6M': 6_000_000, '64M': 64_000_000, '60M': 60_000_000,
 '48M': 48_000_000, '50M': 50_000_000, '54M': 54_000_000, '29M': 29_000_000,
 '18M': 18_000_000, '16M': 16_000_000, '14M': 14_000_000, '9M': 9_000_000,
}
for name, v in vals.items():
    pat = struct.pack('>I', v)
    offs=[]; s=0
    while True:
        i=d.find(pat,s)
        if i<0: break
        offs.append(i); s=i+1
    print(f'{name:10} 0x{v:08X} count={len(offs)}', [hex(x) for x in offs[:20]])
