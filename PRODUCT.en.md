> [中文](PRODUCT.md) | English

# D750-QEMU Product Snapshot

The repository root is the **deliverable product directory** of the `nikon-d750`
validation prototype: source code, tools, documentation, the evidence from actual
runs, and a Release link to the prebuilt Linux binary.

It can be copied as a whole; after copying, just re-run `tools/run.py` with the new
absolute paths.

## 1. Snapshot Information

| Item | Value |
| --- | --- |
| Generated | 2026-11-06 (Asia/Shanghai) |
| Host | Windows + WSL2 Ubuntu 26.04.1 LTS |
| Compiler | gcc 15.2.0 |
| QEMU | 11.1.0 (overlay build) |
| Binary | GitHub Release v0.2.5 asset (Linux x86-64, 100,645,120 bytes) |
| Host-side tests | 27 passed (QEMU) + 9 passed (bitrate/menu; needs a local module, 9 skipped without one) |

## 2. Verified Facts

1. **M0 passes**: `b1010_115a.bin` is loaded at `0x90000000`, the entry point `0x9027D52C`
   runs to completion and returns to the halt window, exiting normally in 0.39 s.
   `evidence/m0/`, `evidence/m0-gdb/`.
2. **Entry check**: RSP reads `entry_pc=0x9027d52c`, `entry_ok=true`,
   `cpsr=0x400001d3` (SVC, A/I/F masked).
3. **LCD dump pipeline**: configurable framebuffer → PPM; writing a 320×240
   test card into guest RAM via GDB verifies that the pixels are correct, see `analysis/lcd-testcard.png`.
   **This is a host-written test card, not the firmware UI.**
4. **Boot candidate scan**: all 10 candidate entry points inside the image yield 0 MMIO; the next stage is not inside
   `b1010` (see `evidence/boot-scan.txt` and `docs/findings.md` §11.4).
5. **M1 reached the target but is not closed** (2026-11-08): boot stub `0x9025D700` → `0x1002CB8C` (Thumb, args
   0/0/2/0/1) → first MMIO `0xE000E180←0x00100000` (GIC); execution then hits `MRS/MSR BASEPRI` at `0x100240AC`,
   showing that a1010 is an M-profile image, not the A-core's next stage. Evidence: `evidence/m1/`,
   `docs/m1-boot-chain.en.md`.

## 3. Directory

```text
D750-QEMU/
├── README.md / README.en.md   Main product documentation (status, quick start, machine model)
├── PRODUCT.md / .en.md        This snapshot documentation
├── NOTICE.md / .en.md         Independent research / no-firmware / license notice
├── SUMMARY.md / .en.md        Both workstreams at a glance
├── CONTRIBUTING.md / .en.md   Legal and contribution boundaries
├── MANIFEST.json              File list, SHA-256, evidence summary
├── SHA256SUMS                 sha256sum -c compatible checksum list
├── CHANGELOG.md               Version and fix log
├── .github/workflows/ci.yml   Host-side tests + manifest checks
├── qemu/                      QEMU overlay: nikon-d750-lab.c/.h + prepare_source.py
├── tools/                     fwscan / run / probe / manifest / build
├── tests/                     23 host-side tests (no QEMU build needed)
├── bitrate/                   1080p 64/60 Mbps patcher, menu-visible variant, tests, report
├── docs/                      findings / architecture / validation / build / gui-cmos / hardware-test (+ .en.md)
├── analysis/
│   ├── d750-0115.json         Profile verification results for the real image
│   ├── lcd-testcard.png       LCD pipeline test card (host-written)
│   └── ...                    Existing analysis files in the repo (see §6)
├── binary/
│   ├── COPYING                QEMU's GPLv2 license
│   └── README.md              Binary provenance, Release download, checksums
└── evidence/
    ├── m0/                    Non-GDB M0 evidence (session/command/logs)
    ├── m0-gdb/                GDB entry check + run records
    ├── lcd/                   8×8 LCD dump evidence
    ├── boot-scan.txt          Candidate entry scan results (negative result)
    └── README.md              Evidence documentation
```

`binary/qemu-system-arm` is ~96 MiB and **is not committed to Git**; it is
published as a GitHub Release asset (see §4/§5).

## 4. Quick Run (WSL)

Download the Linux binary from
[Releases](https://github.com/LuoStickmin/D750-QEMU/releases/latest) into
`binary/` (the file is not committed):

```bash
cd /path/to/D750-QEMU
curl -L -o binary/qemu-system-arm \
  https://github.com/LuoStickmin/D750-QEMU/releases/latest/download/qemu-system-arm
chmod +x binary/qemu-system-arm
```

Then run:

```bash
FW=/path/to/D750_0115.dec.modules
python3 tools/run.py \
  --qemu binary/qemu-system-arm \
  --payload "$FW/b1010_115a.bin" \
  --flash   "$FW/a1010_011100.bin" \
  --boot entry --a1010-base 0x10000000
```

Expected output:

```
entry 0x9027d52c  exit=0  timed_out=False  uart=0B  mmio_events=0
halt: pc=0x00000ff0 r0=0x80002000 r1=0x00000000 sp=0x97ffff00 lr=0x00000ff0
```

M1 (default `boot-mode=stub`):

```bash
python3 tools/run.py --qemu binary/qemu-system-arm \
  --payload ... --flash ... --boot stub --a1010-base 0x10018000 \
  --timeout 6 --trace in_asm
```

```
status=timeout  entry 0x9025d700  uart=0B  mmio_events=0
```

Add `--mpcore-base 0x1E000000` to reproduce the first unmodelled MMIO:
`wr 0xe000e180 size=4 at pc 0x10026b64`.

LCD dump:

```bash
python3 tools/run.py --qemu binary/qemu-system-arm \
  --payload ... --flash ... \
  --lcd-base 0x92000000 --lcd-width 320 --lcd-height 240
```

`binary/qemu-system-arm` is **Linux x86-64** and can only run under WSL/Linux;
the stock 11.1.0 under `C:\Program Files\qemu` on the Windows side has no `nikon-d750` machine,
and `tools/run.py` will reject it (exit code 3). For how to rebuild, see `docs/build.md`.

## 5. Binary Provenance

- QEMU 11.1.0 source + the `qemu/` overlay;
- WSL2 Ubuntu 26.04 / gcc 15.2 / glib 2.88 / pixman 0.46.4;
- Build options: `--target-list=arm-softmmu --disable-werror --disable-docs --disable-tools`;
- For checksum values see `binary.sha256` in `MANIFEST.json`, or `sha256sum binary/qemu-system-arm`.

## 6. About `analysis/`

The public `analysis/` directory keeps only publishable factual artifacts:
`d750-0115.json`, `lcd-testcard.png`, `tiff-feasibility.md/.en.md`, and
`tiff_scan.py`.

Nikon Hacker's patch database, firmware ASCII string dumps, and one-off scripts
with local paths **are not published**; they stay in the local
`.local/private-analysis/`. The reasons (third-party GPL, firmware-text
copyright, privacy/reproducibility) are in `analysis/README.md`. The repository
contains no firmware, keys, decrypted images, or patched images.

## 7. Not Done / Next Steps

- Firmware GUI: need to observe the real registers and framebuffer of Display/GPU/GDU; currently there is only the host-side
  dump pipeline.
- CMOS: need the control/data contract for Sensor/I2C/GDMA; currently there is no model.
- Next boot stage: M1 executed the Nov 7 address hypothesis up to `0x1002CB8C`, but that target is M-profile
  firmware; the next step needs a full flash image / module offset table to find the A-core's real next stage, or
  confirmation of the dual-core topology.
- High-bitrate hardware: the container is now byte-reproducible. Next steps are a static review of the D750 updater
  (model/version/hidden checks), confirmation of the same-version reflash policy, then a spare-body test following
  `docs/hardware-test.md` (short clip + playback). Neither updater acceptance nor encoder behaviour has a hardware record yet.
- See `docs/gui-cmos.md`, `docs/findings.md` §11.4/§11.5, `docs/hardware-test.md`.

## 8. Boundaries

Contains no Nikon firmware, keys, dumps, or camera UI screenshots; firmware is provided locally by the user, and the tools
are read-only. License: overlay/tools/docs GPL-2.0-or-later; QEMU retains its own license.
