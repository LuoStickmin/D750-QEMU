from pathlib import Path
p=Path(r'C:\Users\23795\Downloads\DSLR\D750_0115.dec.modules\b1010_115a.bin')
d=p.read_bytes()

def decode_mov_wt(hw1, hw2):
    if (hw1 & 0xFBFF) == 0xF240:
        op='movw'
    elif (hw1 & 0xFBFF) == 0xF2C0:
        op='movt'
    else:
        return None
    i=(hw1>>10)&1
    imm4=hw1&0xF
    imm3=(hw2>>12)&7
    rd=(hw2>>8)&0xF
    imm8=hw2&0xFF
    imm=(imm4<<12)|(i<<11)|(imm3<<8)|imm8
    return op,rd,imm

hits=[]
for off in range(0, len(d)-4, 2):
    hw1=int.from_bytes(d[off:off+2],'little')
    hw2=int.from_bytes(d[off+2:off+4],'little')
    r=decode_mov_wt(hw1,hw2)
    if not r: continue
    op,rd,imm=r
    if imm in (0xA990,0x2AA9,0x2A,0x902A,0x2AAA,0x2AAB):
        hits.append((off,op,rd,imm))
print('hits',len(hits))
for h in hits[:300]:
    print(f'{h[0]:08x} {h[1]} r{h[2]} #{h[3]:#x}')
