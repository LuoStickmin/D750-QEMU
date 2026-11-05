from pathlib import Path
p = Path(r'C:\Users\23795\Downloads\DSLR\D750_0115.dec.modules\b1010_115a.bin')
d = p.read_bytes()
for kw in [b'Mbps', b'mbps', b'bitrate', b'Bit rate', b'BIT RATE', b'MOVIE', b'Movie', b'movie', b'1080', b'60p', b'24p', b'30p', b'42', b'50M', b'High quality', b'HIGH']:
    offs = []
    start = 0
    while True:
        i = d.find(kw, start)
        if i < 0:
            break
        offs.append(i)
        start = i + 1
        if len(offs) >= 20:
            break
    print(kw.decode('latin1'), len(offs), [hex(x) for x in offs])
