from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_ARM, CS_MODE_LITTLE_ENDIAN
p=Path(r'C:\Users\23795\Downloads\DSLR\D750_0115.dec.modules\b1010_115a.bin')
d=p.read_bytes()
lo=0x2A8000; hi=0x2AA9AC
for mode,name in [(CS_MODE_THUMB,'thumb'),(CS_MODE_ARM,'arm')]:
    md=Cs(CS_ARCH_ARM, mode|CS_MODE_LITTLE_ENDIAN)
    md.skipdata=True
    print('MODE',name)
    count=0
    for ins in md.disasm(d[lo:hi], 0x90000000+lo):
        s=f'{ins.address:08x}: {ins.mnemonic:8} {ins.op_str}'
        if any(k in s for k in ('2aa9','2aaa','2aab','adr','pc,','pc]')) or ins.mnemonic in ('add','ldr'):
            print(s); count+=1
            if count>200: break
