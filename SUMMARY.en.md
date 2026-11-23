> [中文](SUMMARY.md) | English

# Project overview: D750 QEMU validation

This repository now contains the D750 QEMU validation prototype only.

## QEMU validation prototype (`nikon-d750`)

Following the architecture of WonderLantern's z7-qemu / z9-qemu, this is a QEMU
11.1 source overlay:

- main image `b1010_115a.bin` loaded at `0x90000000`, entry `0x9027D52C`;
- auxiliary boot: low 64 KiB RAM, SP at the top of RAM, LR pointing at the halt
  window `0xFF0`;
- result: entry returns normally, `exit=0`, 0.39 s, `r0=0x80002000`, 0 MMIO, 0 UART;
- cross-check: `entry_pc=0x9027D52C`, `entry_ok=true`, CPSR `0x400001d3`;
- the entry is a **called function**, not reset; without it the code `push`es to
  `0xFFFFFFF0..FC` and jumps to 0;
- all 10 candidate entries inside the image produce 0 MMIO; `0x9025D700` enters a
  no-MMIO wait loop; its caller is outside `b1010`, and later layout enumeration
  points at a missing first-stage boot ROM;
- cross-model (2026-11-10): E5 D850's in-image init is located
  (`0x1035CE30..0x1035D040`) but still lacks the boot-ROM call context; E6 D780
  with the `e6-prep` page-table fix runs with 0 exceptions into the
  `0x0426/0x0428` peripheral block;
- M-core (2026-11-23): added `nikon-d750-mcore`; a1010 is BE8 Firmware A, runs
  from reset `0xC20D` to the `0x440CE000` pin/clock block, writes `STIR=0x8F`,
  then idles; 0 exceptions and 0 UART in 3 s; see
  [docs/mcore.en.md](docs/mcore.en.md);
- the LCD dump pipeline is implemented (configurable framebuffer → PPM) and the
  test card passes; firmware GUI and CMOS still have no model.

Details: [README.en.md](README.en.md), [docs/findings.en.md](docs/findings.en.md),
[docs/validation.en.md](docs/validation.en.md),
[docs/gui-cmos.en.md](docs/gui-cmos.en.md).

## Status and boundaries

- this repository is **local research/static validation**, not a flashable
  product, and does not promise camera compatibility;
- no signing, repacking service, update-container processing or camera installer;
- firmware copyright belongs to Nikon; the repository contains no firmware;
- QEMU overlay / tools / docs: GPL-2.0-or-later; upstream QEMU keeps its own license.

## Recommended reading order

1. [README.en.md](README.en.md) — machine model, M0, LCD pipeline, boot conclusions;
2. [CONTRIBUTING.en.md](CONTRIBUTING.en.md) — legal notice, contribution boundaries, DCO;
3. [docs/findings.en.md](docs/findings.en.md) — static and runtime evidence.
