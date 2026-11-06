> [中文](SUMMARY.md) | English

# Project overview: D750 QEMU validation + 1080p high-bitrate modification

This repository contains two independent workstreams that share the same D750
firmware research:

| Workstream | Content | Status |
| --- | --- | --- |
| **A. QEMU validation prototype** | `nikon-d750` machine, M0 boot, LCD dump, boot scan | M0 passed; M1–M3 incomplete |
| **B. 1080p high-bitrate modification** | raise 5 HQ rows from 42/35 and 24/20 to 64/60 Mbps | container-level verification passed and the image is byte-reproducible; camera capture untested |

Neither workstream **contains firmware, keys, decrypted images or patched
images**; the user supplies firmware locally and the tools only read it. See
[CONTRIBUTING.md](CONTRIBUTING.md) for legal and contribution boundaries.

---

## A. QEMU validation prototype (`nikon-d750`)

Following the structure of WonderLantern's z7-qemu / z9-qemu, this is a QEMU
11.1 source overlay:

- main image `b1010_115a.bin` loaded at `0x90000000`, entry `0x9027D52C`;
- assisted startup: low 64 KiB RAM, SP at the top of RAM, LR pointing at the
  `0xFF0` halt window;
- result: the entry runs and returns cleanly, `exit=0`, 0.39 s,
  `r0=0x80002000`, 0 MMIO, 0 UART;
- cross-check: `entry_pc=0x9027D52C`, `entry_ok=true`, CPSR `0x400001d3`;
- the entry is a **called function**, not reset; without assistance it pushes
  to `0xFFFFFFF0..FC` and returns to 0;
- all 10 in-image candidate entries scanned to 0 MMIO; `0x9025D700` enters a
  wait loop with no MMIO; the next stage is not inside `b1010` and may need a
  flash/ROM dump or the loader hand-off contract;
- LCD dump pipeline implemented (configurable framebuffer → PPM), verified
  with a test card; firmware GUI and CMOS still have no model.

Details: [README.md](README.md), [docs/findings.md](docs/findings.md),
[docs/validation.md](docs/validation.md), [docs/gui-cmos.md](docs/gui-cmos.md).

## B. 1080p high-bitrate modification (64/60 Mbps)

Target firmware `D750_0115`, module `b1010_115a.bin`; the 1080p bitrate table
starts at `0x2AA9AC`, 28 bytes per entry:

| Row | Offset | Stock | Modified |
| --- | --- | --- | --- |
| entry 1 | `0x2AA9AC` | 42/35 Mbps | 64/60 Mbps |
| entry 3 | `0x2AA9E4` | 42/35 Mbps | 64/60 Mbps |
| entry 5 | `0x2AAA1C` | 24/20 Mbps | 64/60 Mbps |
| entry 7 | `0x2AAA54` | 24/20 Mbps | 64/60 Mbps |
| entry 9 | `0x2AAA8C` | 24/20 Mbps | 64/60 Mbps |

- the four NQ rows, the lower-resolution group from entry 10 onward, and the
  other two modules are untouched;
- module CRC `0x12CA → 0x4314`; package CRC remains `0x7EE4` (CRC residue,
  expected);
- the patched decrypted image differs from stock by 36 B (34 B fields + 2 B
  CRC), with 0 B outside the fields;
- an independent verifier (it does not import the patcher) re-decrypts,
  recomputes both CRC levels and checks every row; all checks pass;
- the container is byte-reproducible: a no-edit repack of stock is bit-identical,
  and stock + the patched module rebuilds `9c88f3cc…` exactly; the container
  differs by only 36 B;
- the D750 uses packaging A (no 20-byte header digest), so K8/`STALE` does not
  apply;
- the same QEMU M0 path runs stock and patched modules identically (exit 0,
  same halt, 0 MMIO);
- **not verified**: updater acceptance (including the same-version reflash
  policy), camera encoder, SD recording, playback; 64 Mbps is about 2.7× the
  stock 24 Mbps at 1080p30, and slow cards, heat or encoder limits may cause
  problems;
- the repository ships only the table patcher and tests, not patched images,
  keys or a decryptor;
- menu-visible alternative: reuse the two Movie quality slots as
  `64 Mbps HQ` / `Stock`; a genuine third item is blocked at the menu
  descriptor, see
  [analysis/menu-bitrate-feasibility.en.md](analysis/menu-bitrate-feasibility.en.md);
  tool and verification: [bitrate/MENU64.md](bitrate/MENU64.md).

Details: [bitrate/README.md](bitrate/README.md); hardware preconditions:
[docs/hardware-test.md](docs/hardware-test.md).

## Status and boundaries

- both workstreams are **local research/static validation**, not a flashable
  product, and do not promise camera compatibility;
- no signing, repacking service, update-container processing or
  camera-installable package;
- firmware copyright belongs to Nikon; the repository contains no firmware;
- QEMU overlay / tools / docs: GPL-2.0-or-later; upstream QEMU keeps its own
  license.

## Suggested reading order

1. [README.md](README.md) — machine model, M0, LCD pipeline, boot conclusions;
2. [bitrate/README.md](bitrate/README.md) — 64/60 patch and verification;
3. [CONTRIBUTING.md](CONTRIBUTING.md) — legal notice, contribution boundaries, DCO;
4. [docs/findings.md](docs/findings.md) — static and runtime evidence.
