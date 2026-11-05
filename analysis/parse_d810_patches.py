from pathlib import Path
import re
s=Path(r'analysis/nikon_patches.c').read_text(encoding='utf-8')
# crude parse: each Change line gives offset, b and a arrays
for prefix in ['D810_0114_000','D810_0114_001','D810_0114_002','D810_0114_003','D810_0114_004']:
    print('='*10,prefix)
    for m in re.finditer(r'uint8_t '+prefix+r'_change_(\d+)_b\[\] = \{([^}]*)\};\s*uint8_t '+prefix+r'_change_\1_a\[\] = \{([^}]*)\};\s*struct Change .*?CHANGE\(\d+, (0x[0-9A-Fa-f]+)',s):
        idx,b,a,off=m.groups()
        print(idx,off,b.strip(),'->',a.strip())
