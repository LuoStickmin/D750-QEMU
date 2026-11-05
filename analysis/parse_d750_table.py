from pathlib import Path
import struct
p=Path(r'C:\Users\23795\Downloads\DSLR\D750_0115.dec.modules\b1010_115a.bin')
d=p.read_bytes()
base=0x2AA990
for i in range(30):
    off=base+i*28
    if off+28>len(d): break
    a,b,flag,maxrate,tb_num,tb_den,fps=struct.unpack('<7I',d[off:off+28])
    print(f'{i:2} {off:08x} a={a/1e6:8.3f}M b={b/1e6:8.3f}M flag={flag:#x} max={maxrate/1e6:8.3f}M tb={tb_num}/{tb_den} fps={fps}')
