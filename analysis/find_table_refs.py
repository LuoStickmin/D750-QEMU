from pathlib import Path
import struct
p=Path(r'C:\Users\23795\Downloads\DSLR\D750_0115.dec.modules\b1010_115a.bin')
d=p.read_bytes()
base=0x90000000
for off in [0x2AA990,0x2AA9AC,0x2AA9C8,0x2AAC14]:
    va=base+off
    for delta in [0,-1,1]:
        pat=struct.pack('<I',va+delta)
        hits=[];s=0
        while True:
            i=d.find(pat,s)
            if i<0:break
            hits.append(i);s=i+1
        print(hex(off),'VA',hex(va+delta),'hits',len(hits),[hex(x) for x in hits[:20]])
