from pathlib import Path
import re
p = Path(r'C:\Users\23795\Downloads\DSLR\D750_0115.dec.modules\b1010_115a.bin')
d = p.read_bytes()
# Extract printable ASCII strings >= 4, store offset
pat = re.compile(rb'[ -~]{4,}')
terms = re.compile(rb'(?i)(movie|video|record|quality|bit|frame|1080|720|h\.?264|avc|encod|codec|stream|hdmi|live)')
hits = []
for m in pat.finditer(d):
    s = m.group()
    if terms.search(s):
        hits.append((m.start(), s.decode('latin1')))
print('total hits', len(hits))
for off, s in hits:
    print(f'{off:08x}  {s[:180]}')
