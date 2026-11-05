from pathlib import Path
import struct
for mod in ['b1010_115a.bin','a1010_011100.bin']:
    p=Path(r'C:\Users\23795\Downloads\DSLR\D750_0115.dec.modules')/mod
    d=p.read_bytes()
    print('MODULE', mod, len(d))
    for endian,fmt in [('<','<I'),('>','>I')]:
        for name,v in [('42M',42_000_000),('35M',35_000_000),('24M',24_000_000),('20M',20_000_000),('12M',12_000_000),('10M',10_000_000),('20.34432M',20_344_320),('36M',36_000_000),('64M',64_000_000)]:
            pat=struct.pack(fmt,v)
            offs=[];s=0
            while True:
                i=d.find(pat,s)
                if i<0:break
                offs.append(i);s=i+1
            if offs:
                print(endian,name,hex(v),len(offs),[hex(x) for x in offs[:10]])
