import json
from pathlib import Path
p = Path(r'C:\Users\23795\AppData\Local\Temp\dsh-spill-ffmoJL\session-113dd6fdf9f0\6a159d554234-web_fetch.txt')
lines = p.read_text(encoding='utf-8').splitlines()
obj = json.loads(lines[4])
print('entries', len(obj['tree']))
for e in obj['tree']:
    path = e['path']
    low = path.lower()
    if any(k in low for k in ('bitrate', 'movie', 'patch', 'video')):
        print(e['type'], e.get('size'), path)
