from pathlib import Path
import struct
p = Path(r'C:\Users\23795\Downloads\DSLR\D750_0115.dec.modules\b1010_115a.bin')
d = p.read_bytes()
for width, fmt in ((2,'>H'),(4,'>I')):
    print('WIDTH', width)
    vals = [42000,35000,36000,24000,20000,12000,10000,8000,6000,64000,60000,48000,50000,54000,29000,18000,16000,14000,9000,24400,20344]
    for v in vals:
        pat=struct.pack(fmt,v)
        offs=[]; s=0
        while True:
            i=d.find(pat,s)
            if i<0: break
            offs.append(i); s=i+1
        print(f'{v:7} 0x{v:08X} n={len(offs):4}', [hex(x) for x in offs[:12]])
