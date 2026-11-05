> [中文](README.md) | English

# analysis/

This directory keeps only **publishable factual artifacts**. It contains no
firmware, keys, decrypted images, or patched images.

| File | Content |
| --- | --- |
| `d750-0115.json` | `fwscan` profile of the real image: size, SHA-256, vectors/literals, MMU sites, pointer census. |
| `lcd-testcard.png` | Synthetic test card for the `nikon-d750` LCD dump pipeline (host-written, not firmware UI). |
| `tiff-feasibility.md` / `.en.md` | Feasibility analysis for adding TIF to the D750 menu: read-only static conclusions and evidence. |
| `tiff_scan.py` | Read-only scanner used by that analysis; `--module` accepts a local module. |

## Material not published

The following is **not** part of the public repository and stays in the local
`.local/private-analysis/` for copyright, privacy, or reproducibility reasons:

- Nikon Hacker's patch database (`nikon_patches.c`, `nikon_patches.h`,
  `nikon_patch_main.c`) and its parser scripts — third-party GPL code that also
  contains a large amount of patch bytes;
- firmware ASCII string dumps (`strings_movie.txt`) — contain firmware text and
  may implicate copyright;
- one-off exploration scripts (`scan_bitrate_*.py`, `dump_*.py`,
  `search_bitrate.py`, etc.) — they hard-code local paths and have been
  superseded by conclusions/tools.

To reproduce a step, write a minimal script from the documented offsets/hashes;
do not submit firmware, keys, or third-party patch tables to issues/PRs.

## Boundaries

- no firmware binaries and no flashable images here;
- all offsets/hashes are factual information, not a redistribution of Nikon
  code or assets;
- see [../CONTRIBUTING.md](../CONTRIBUTING.md) and [../NOTICE.md](../NOTICE.md).
