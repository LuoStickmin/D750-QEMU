# D750 QEMU Verification Prototype (`nikon-d750`)

> [中文](README.md) | English

> **Recent update log**
>
> | Date | Progress |
> | --- | --- |
> | 2026-11-09 | **Three no-input checks + six follow-ups**: static call chain, 12 flash layouts, M-core boot → TTBR0 check → work-queue slot / veneer relocation (**0 undefined, 1 SVC, 0 aborts**) → loader segment table → the Nikon-Patch IDA base **`0x90020000`** → **D3300/D850/D780 firmware decrypted with the same keys** (E6→E5→E4 map: D780 header+branch, D850 reset `0x1037CBA8`/handlers `0x4002xxxx`, D750 `0x90020000`), with `io-stub` passing the `0xAE00060C` poll. Details: [docs/m1-tracks-2026-11-09.en.md](docs/m1-tracks-2026-11-09.en.md) |
> | 2026-11-08 | **M1 run + v0.2.0**: stub → `0x1002CB8C` (Thumb, `args=0/0/2/0/1`, `LR=0x9025D754`), first MMIO `wr 0xE000E180 ← 0x00100000`; MPCore base corrected to **`0xE000E000`**; a1010 found to be M-profile firmware, so M1 is recorded as "reached target, not closed"; the Linux x86-64 binary is published as [Release v0.2.0](https://github.com/LuoStickmin/D750-QEMU/releases/tag/v0.2.0). Details: [docs/m1-boot-chain.en.md](docs/m1-boot-chain.en.md) |
> | 2026-11-07 | **Static resolution**: a1010 base `0x10018000`, entry file offset `0x14B8C`, Thumb bit, config slots `0x100F48C0/C4/C8`; raw material in `update_1107.zip` |
> | 2026-11-06 | **v0.1.1**: M0 passed, strict/halt evidence fixes, LCD dump pipeline, 64/60 Mbps bitrate patch; see [CHANGELOG.md](CHANGELOG.md) |
> | 2026-11-05 | **v0.1.0**: first public snapshot (M0, LCD dump, bilingual docs) |
>
> Full changes and compatibility notes: [CHANGELOG.md](CHANGELOG.md).

---

> **This repository has two workstreams**: the QEMU validation prototype
> (this file) and a D750 1080p high-bitrate modification (five HQ rows from
> 42/35 and 24/20 to 64/60 Mbps). Combined overview:
> [SUMMARY.md](SUMMARY.en.md); bitrate details:
> [bitrate/README.md](bitrate/README.md); legal/contribution boundaries:
> [CONTRIBUTING.md](CONTRIBUTING.en.md).

---

> **Disclaimer**: This project **does not contain** and **does not download** any Nikon firmware. Firmware must be provided locally by the user, and the entire toolchain processes it strictly read-only.

Following the architecture of [WonderLantern/z7-qemu](https://github.com/WonderLantern/z7-qemu) and [WonderLantern/z9-qemu](https://github.com/WonderLantern/z9-qemu), this is a minimal verification prototype for the Nikon D750 (EXPEED 4, `D750_0115`): **a QEMU board-level overlay + a suite of host-side evidence tools**.

The goal is not to simulate the entire camera, but to answer four questions sequentially:
- **M0**: Can the main image be loaded at the inferred base address and booted from the inferred entry point?
- **M1**: What MMIO windows does the first execution fragment access?
- **M2**: Does the firmware output bytes from the candidate UART block?
- **M3**: How far can we get after implementing the first missing device?

---

## Table of Contents
- [Project overview (both workstreams)](SUMMARY.en.md)
- [High-bitrate modification](bitrate/README.en.md)
- [Contributing & legal boundaries](CONTRIBUTING.en.md)
- [1. Current Status & Roadmap](#1-current-status--roadmap)
- [2. Quick Start](#2-quick-start)
  - [2.1 Build (Requires C Toolchain)](#21-build-requires-c-toolchain)
  - [2.2 Run](#22-run)
  - [2.3 Static Verification Only](#23-static-verification-only)
  - [2.4 First Actual Run (M0 Passed)](#24-first-actual-run-m0-passed)
  - [2.5 M1 Run (Boot Stub → a1010 Target)](#25-m1-run-boot-stub--a1010-target)
- [3. Machine Model (One-Liner Version)](#3-machine-model-one-liner-version)
  - [3.1 GUI & CMOS Status](#31-gui--cmos-status)
- [4. Static Evidence Collected (Real Bytes)](#4-static-evidence-collected-real-bytes)
- [5. Directory Structure & Dependencies](#5-directory-structure--dependencies)
- [6. Relationship with z7-qemu / z9-qemu](#6-relationship-with-z7-qemu--z9-qemu)
- [7. Boundaries & Future Work](#7-boundaries--future-work)

---

## 1. Current Status & Roadmap

Currently **completed and verified**:

| Item | Status |
| --- | --- |
| Static evidence: vector table, entry, page tables, flash/RAM windows, UART candidates | ✅ Ran on real `D750_0115` modules, see [docs/findings.md](docs/findings.md) |
| Board source code `nikon-d750-lab.c/.h` | ✅ Written (QEMU 11.1 API; 10.2.4 is text-adapted by the prepare script but has not been built here) |
| Overlay install script `qemu/prepare_source.py` | ✅ Idempotent, unit tests cover 11.1 / 10.2 / unknown version rejection |
| `fwscan` / `run` / `probe` / `build` tools | ✅ Written; `probe` tested with real RSP against stock QEMU `-M virt` |
| Host-side tests | ✅ `python3 tests/run_tests.py` → 27 passed |
| Board C code compilation | ✅ Compiled on WSL Ubuntu 26.04 (gcc 15.2) + QEMU 11.1.0 |
| `nikon-d750` machine actual run | ✅ **M0 passed**: loaded at `0x90000000`, executed from entry `0x9027D52C`, returned normally, exited cleanly in 0.39s |
| M1 boot-chain run | ⚠️ **Reached the target, not closed**: stub → `0x1002CB8C` (Thumb) → first MMIO `0xE000E180`; then hits an M-profile instruction at `0x100240AC`, so the target module is not A-core code. See [docs/m1-boot-chain.en.md](docs/m1-boot-chain.en.md) |
| M1 machine options | ✅ `boot-mode=stub`, `a1010-base`, `thumb-fix`, `mmu-bringup`, `mpcore-base`; firmware files untouched |
| LCD scanout/dump pipeline | ✅ Configurable framebuffer → PPM; test card verified; firmware image still absent |
| Container repack / patched-image reproduction | ✅ Byte-for-byte reproducible with the author's toolchain (no-edit round trip is bit-identical; the patched image `9c88f3cc…` can be rebuilt exactly), see [docs/hardware-test.md](docs/hardware-test.md) |
| Real hardware | ⚠️ **Unverified**: updater acceptance, encoder behaviour, card/heat/playback have no hardware record yet |
| M2 (UART) / M3 (Devices) | ⏳ Not started: still no serial output (`uart=0B`); the GIC is now connected and the next unmodelled access is the open lead |
| Full camera UI / ISP / CMOS / Storage | ❌ Out of scope |

> **Second workstream (1080p high bitrate)**: the five HQ rows of the D750
> bitrate table were raised from `42/35` and `24/20` to `64/60` Mbps.
> Container-level verification passed, and the patched image is **reproducible
> byte for byte** from stock + the patched module (`repack_firmware.py`'s no-edit
> round trip is bit-identical). The QEMU M0 regression matches stock, but
> **camera capture is unverified**. Overview: [SUMMARY.md](SUMMARY.en.md);
> details: [bitrate/README.md](bitrate/README.md); hardware preconditions:
> [docs/hardware-test.md](docs/hardware-test.md). The repository ships only the
> table patcher, not firmware, keys, or patched images.

### ⚠️ Warning Regarding Stock QEMU
If you have the official default QEMU installed (e.g., `C:\Program Files\qemu` on Windows), it usually only has `qemu-system-arm` / `qemu-system-aarch64` targets, and **no `nikon-*` machine** in `-M help`. QEMU machines are registered at compile-time and cannot be loaded at runtime like plugins. 
**Therefore, "booting D750 directly with an installed QEMU" is impossible; you must use `tools/build.py` to compile the overlay into `qemu-system-arm`.**
See [docs/build.md](docs/build.md) for stock version/target lists. `tools/run.py`
will explicitly reject it before boot (exit code 3). `binary/` holds COPYING and
notes; the Linux `qemu-system-arm` is published as a GitHub Release asset:
<https://github.com/LuoStickmin/D750-QEMU/releases/latest>, runnable in WSL.

---

## 2. Quick Start

### 2.1 Build (Requires C Toolchain)
**Dependencies**: Python 3.8+, standard build tools on Linux/Mac; MSYS2 UCRT64 environment recommended on Windows.

**Linux / WSL**:
```sh
sudo apt-get install build-essential ninja-build pkg-config \
    libglib2.0-dev libpixman-1-dev zlib1g-dev libfdt-dev
python3 tools/build.py --jobs 4
```

**Windows (MSYS2 UCRT64, same path as z7-qemu)**:
*Requires downloading and installing [MSYS2](https://www.msys2.org/) in advance.*
```powershell
python tools/build.py --msys-root C:\msys64 --jobs 4
```

Offline or existing source:
```powershell
python tools/build.py --archive C:\downloads\qemu-11.1.0.tar.xz
python tools/build.py --source C:\src\qemu-11.1.0 --overlay-only
```

Artifacts: `.build/src/qemu-<version>/build/qemu-system-arm[.exe]` (change via `--work-dir`), build records in `.local/build-manifest.json`. See [docs/build.md](docs/build.md).

### 2.2 Run
**Windows PowerShell**:
```powershell
$FW = "D:\path\to\D750_0115.dec.modules"   # Change to your firmware directory
python tools/run.py `
  --payload "$FW\b1010_115a.bin" `
  --flash   "$FW\a1010_011100.bin" `
  --timeout 10
```

**Linux / WSL**:
```sh
FW=/path/to/D750_0115.dec.modules
python3 tools/run.py \
  --payload "$FW/b1010_115a.bin" \
  --flash   "$FW/a1010_011100.bin" \
  --timeout 10
```

With RSP snapshot (halt first, verify entry, then resume guest):
```sh
python3 tools/run.py --payload ... --flash ... --gdb --run-seconds 2
```

Every run generates `runs/<timestamp>/`: `command.json`, `uart.log`, `qemu.log`, `session.json` (contains MMIO stats and UART tail). See [docs/validation.md](docs/validation.md) for acceptance criteria.

> The commands above use the default `boot-mode=stub` (M1, entering through
> the boot stub). To go back to the M0 assisted entry, add
> `--boot entry --a1010-base 0x10000000`, see §2.4.

### 2.3 Static Verification Only
```powershell
$FW = "D:\path\to\D750_0115.dec.modules"
python tools/fwscan.py `
  --main  "$FW\b1010_115a.bin" `
  --flash "$FW\a1010_011100.bin" `
  --out   analysis\d750-0115.json
```

### 2.4 First Actual Run (M0 Passed)
Environment: WSL Ubuntu 26.04, gcc 15.2, QEMU 11.1.0. Build in repo root:
```sh
python3 tools/build.py --work-dir ~/d750-build --jobs 12
```
*(`--work-dir` on WSL native filesystem; `/root` is not writable by default user.)*

Run (or skip build using `binary/qemu-system-arm` directly):
```sh
FW=/path/to/D750_0115.dec.modules
python3 tools/run.py \
  --qemu ~/d750-build/src/qemu-11.1.0/build/qemu-system-arm \
  --payload "$FW/b1010_115a.bin" \
  --flash   "$FW/a1010_011100.bin" \
  --boot entry --a1010-base 0x10000000
```

Measured output (evidence in `evidence/m0/`, `evidence/m0-gdb/`):
```text
exit=0  timed_out=False  wall_seconds=0.393  uart=0B  mmio_events=0
d750-halt: pc=0x00000ff0 r0=0x80002000 r1=0x00000000 sp=0x97ffff00 lr=0x00000ff0
```

**Interpretation**:
- Entry `0x9027D52C` is a **called function**, not a reset handler. Without assistance, it pushes `{r4,r5,r6,lr}` to `0xFFFFFFF0..0xFFFFFFFC` (SP=0), executes `pop` returning LR=0, and PC runs away to 0 — the most important finding from the first run.
- The machine thus adds **assisted boot**: low 64 KiB RAM, SP=top of RAM, LR pointing to halt window at `0xFF0`, r0=0. After function returns, halt device records registers and requests QEMU exit cleanly.
- This fragment accesses **0 MMIO** (`mmio_events=0`) and produces **no UART output** (`uart=0B`). So the next step for M1/M2 is **finding the caller of this init function or the next stage entry**; `-machine entry=...` allows trying other hypotheses directly.
- Scanned 10 candidate entries in image: all `0 MMIO`. `0x9025D700` enters a no-MMIO wait loop. Conclusion: **the next stage is not in `b1010`**, likely from boot ROM or flash outside `a1010`. See [findings §11.4](docs/findings.md#114-candidate-entry-scan-negative-results).

### 2.5 M1 Run (Boot Stub → a1010 Target)

Added 2026-11-08. The default machine mode is now `boot-mode=stub`; the full
record (including the failure point) is in
[docs/m1-boot-chain.en.md](docs/m1-boot-chain.en.md), evidence in `evidence/m1/`.

```sh
FW=/path/to/D750_0115.dec.modules
python3 tools/run.py \
  --qemu ~/d750-build/src/qemu-11.1.0/build/qemu-system-arm \
  --payload "$FW/b1010_115a.bin" --flash "$FW/a1010_011100.bin" \
  --boot stub --a1010-base 0x10018000 --timeout 6 --trace in_asm
```

Expected:

```text
status=timeout  entry 0x9025d700  ...
a1010_io=0                       # GIC modelled at 0xE000E000
```

Putting the MPCore back at the old placeholder reproduces the first-MMIO
discovery:

```sh
python3 tools/run.py ... --boot stub --mpcore-base 0x1E000000
# session.json: mmio.first_a1010 = wr 0xe000e180 size=4 at pc 0x10026b64
```

Under GDB (`-S -gdb tcp::12345` + `tools/probe.py`) the entry state is
`pc=0x1002cb8c cpsr=0x600001f3` (T=1, SVC), `lr=0x9025d754`,
`r0..r4=0,0,2,0,1`.

> **Do not read this as "M1 complete"**: `0x100240AC` is `MRS/MSR BASEPRI`
> (ARMv7-M only), so execution must take an undefined exception; a1010's header
> is also a big-endian Cortex-M vector table. The A-core's next-stage module is
> still missing.

---

## 3. Machine Model (One-Liner Version)

| Item | Value | Evidence Strength |
| --- | --- | --- |
| CPU | 1× Cortex-A9 (`-smp 2` can try) | Medium: ARMv7 Thumb-2 + VFP/NEON + T-Kernel strings |
| Main RAM | `0x90000000`, default 128 MiB | High: `0x90020000` page table literal, `0x9027D52C` pointers |
| Main image loaded | `b1010_115a.bin` @ `0x90000000` | High |
| Initial PC | `0x9025D700` in `boot-mode=stub` (via internal `0x1000` trampoline); `0x9027D52C` in `boot-mode=entry` | Runtime evidence: both modes have run |
| Low memory | `0x0..0xFFFF` RAM; `0xFF0` halt window, `0x1000` M1 MMU trampoline | Runtime evidence: entry writes vector words to `0x0` |
| Assisted boot | SP=top of RAM, LR=`0xFF0`, r0=0 (entry mode) | Runtime evidence: entry returns after `push`/`pop` |
| Flash window | `0x10000000`, 8 MiB; `-bios` image loaded at `a1010-base` (default `0x10018000`) | Medium: the `bx` target lands on a Thumb prologue there, but the image is M-profile (see M1 doc) |
| MMU shim | `mmu-bringup=on`: 16 KiB identity table at top of DRAM + `DACR/TTBR0/TTBCR` prologue; config slot `0x100F48C0` filled with the table base | Runtime evidence: without it, `SCTLR=0x1C05` immediately prefetch-aborts |
| UART candidate | `0x80005010..0x80005014` byte registers | Medium: driver fragment `0x27CC00..0x27D304` |
| GIC/timer | `a9mpcore_priv` @ **`0xE000E000`** (override with `mpcore-base=`) | High: first a1010 MMIO is `0xE000E180 ← 0x00100000` |
| Diagnostics | 4 GiB low-priority catch-all; `strict=on` logs the first access and stops | — |

The machine is **diagnostics-first**: by default, unmodeled accesses are logged in `qemu.log` (PC/address/width/direction) instead of returning plausible values. With `-machine strict=on` the first unmodeled access is still logged (prefix `d750-strict:`) and the run is stopped immediately; `tools/run.py` reports the address and exits with code 7. This is better for verification than "filling zeros to fake boot past it".

### 3.1 GUI & CMOS Status
**GUI: No firmware image yet, but scanout pipeline is ready.** Provides host-side LCD dump:
```powershell
python tools/run.py --payload ... --flash ... `
  --lcd-base 0x92000000 --lcd-width 320 --lcd-height 240
```
- Configurable `lcd-base / lcd-width / lcd-height / lcd-stride / lcd-format / lcd-out`;
- Dumps to PPM on halt and every 2s (`runs/<ts>/lcd.ppm`);
- No guessing: `lcd-base=0` (default) disables completely;
- Verified full chain by writing test card to guest RAM via GDB:

  ![LCD test card](analysis/lcd-testcard.png)

  This is a **host-written test card**, not firmware UI; it proves "guest RAM → scanout → PPM/PNG" works. Real firmware doesn't write framebuffer yet, so default run yields black.

**CMOS: Not yet.** Current fragment `mmio_events=0`, never accessed Sensor/I2C/GDMA; image has Sensor/ImageProcess/GDMA/I2C driver names, but no control/data contract observed. Route and acceptance see [gui-cmos.md](docs/gui-cmos.md). In short: **CMOS blocked on "finding next boot stage + observing DMA descriptors"**; won't guess registers before real access sequence, nor fake sensor with "putting an image in RAM".

---

## 4. Static Evidence Collected (Real Bytes)

`D750_0115` main module `b1010_115a.bin` (20,324,448 B, SHA-256 `faada7fe…f82937fd`) starts with 8 ARM exception vectors:

```text
0x00  E59FF018  ldr pc,[pc,#0x18]  -> 0x9027D524
0x04  E59FF018                     -> 0x90291C80
0x08  E59FF018                     -> 0x90291D30
0x0C  E59FF018                     -> 0x90291DA8
0x10  E59FF018                     -> 0x90291DB8
0x14  E320F000  nop
0x18  EA00000D  b   +0x34
0x1C  E59FF018                     -> 0x90291DEC
```

**Key contradiction**: `0x9027D524` is not code, but two literals `0x1041D9A8 / 0x1041DBA8` (ARM condition code 0x1, not AL). Real function entry is at `0x9027D52C` (`cmp r0,#2; mov r3,#0; push {r4-r6,lr}`), and this address is referenced in boot descriptor table at file `0x25D760`. So prototype defaults to entering `0x9027D52C`, and keeps contradiction as `WARN` in `fwscan` rather than hiding it.

At module file `0x25D7FC`, literal `0x90020000` (MMU page table target), near `0x25D760` RAM pointers like `0x90284000 / 0x90280000 / 0x9128DB64 / 0x9132EC00`, and `0x100xxxxx` flash pointers (max `0x107FFF24`, exactly within 8 MiB window). Full report: `analysis/d750-0115.json`.

---

## 5. Directory Structure & Dependencies

```text
.
├── qemu/
│   ├── nikon-d750-lab.c/.h     Board model (CPU/RAM/flash/MPCore/UART/LCD dump/diagnostics)
│   └── prepare_source.py       Installs overlay into QEMU source tree (idempotent)
├── .github/workflows/ci.yml    Host-side tests + manifest checks
├── tools/
│   ├── fwscan.py               Static verification profile, generates manifest
│   ├── run.py                  Launch, timeout, evidence collection (M0/M1 profiles)
│   ├── probe.py                Minimal GDB RSP client
│   ├── stub_trace.py           Boot-stub single-step simulator (Nov 7 tool, no deps)
│   ├── m1_analyze.py           M1 static-analysis quartet (Nov 7 tool; disasm needs capstone)
│   ├── manifest.py             Regenerate/verify SHA256SUMS and MANIFEST.json
│   └── build.py                Download/unpack/overlay/build/record
├── tests/                      26 host-side tests (no QEMU build required)
├── bitrate/                    D750 1080p 64/60 Mbps patcher, test, report
├── analysis/
│   ├── d750-0115.json          Real image scan results
│   ├── lcd-testcard.png        LCD pipeline test card (host-written)
│   └── ...                     Other firmware analysis artifacts already in repo (see below)
├── binary/                     COPYING + notes (binary published via GitHub Release)
├── evidence/                   M0 / M1 / GDB / LCD / boot-scan run evidence
├── docs/                       findings / m1-boot-chain / architecture / validation / build / gui-cmos / hardware-test (+ .en.md)
├── SUMMARY.md / SUMMARY.en.md  Combined overview of both workstreams
├── CONTRIBUTING.md / .en.md    Legal and contribution boundaries
├── README.md / README.en.md    This document and its Chinese original
├── PRODUCT.md  MANIFEST.json  SHA256SUMS
├── CHANGELOG.md                Version and fix log
├── LICENSE                     GPLv2 text (GPL-2.0-or-later)
├── Setup-D750.ps1  Run-D750.ps1
└── .build/ .local/ runs/       Local generated artifacts (Git ignored)
```

`analysis/` only contains `d750-0115.json` and `lcd-testcard.png` generated by this QEMU product; the rest (movie bitrate, TIFF, patch, etc.) are existing firmware analysis artifacts in the same repo, kept for context but out of QEMU product acceptance scope.

> **Large binary**: `binary/qemu-system-arm` is ~96 MiB, so it is **not**
> committed to Git history. It is attached to GitHub Releases:
> <https://github.com/LuoStickmin/D750-QEMU/releases/latest>. `binary/` keeps
> COPYING and provenance notes.

---

## 6. Relationship with z7-qemu / z9-qemu

- **Inherited**: source overlay format, idempotent `prepare_source.py` registration, "user-supplied firmware + local manifest + no firmware distribution" boundary, RSP/GDB and UART evidence habits.
- **Different**: Z7 is dual Cortex-A15, 33 MB payload, with ISP/LCD/browser control; Z9 is quad-core AArch64, 82 MB payload. D750 prototype only has **M0–M3 boot verification**, no UI/sensor/image pipeline, CPU is A9 assumption.
- **Not inherited**: addresses, IRQs, peripheral protocols, boot calls. All constants come from D750's own bytes, each labeled with confidence.

---

## 7. Boundaries & Future Work

- This is an **assisted verification prototype**: entry chosen by host, SP/LR given by host, not equal to natural power-on boot.
- Compiled and ran on WSL: M0 is clean, M1 reaches the 1107 target and the first
  MMIO but does not close the A-core chain (the target image is M-profile).
  The MPCore base is now measured (`0xE000E000`); UART register semantics and
  the exact CPU model are still assumptions.
- No signing, no repacking, no update container processing; firmware files strictly read-only.

**Roadmap (M1-M3)**:
- **[M1] MMIO Capture**: The 1107 target now runs and the first MMIO is captured
  (`0xE000E180`, GIC). Still open: the target module is M-profile firmware, so
  the A-core's real next stage (and its module) must be identified from a full
  flash / module offset table.
- **[M2] UART Output**: Confirm `0x80005010` is FIFO data register. Once confirmed, implement device model to see T-Kernel boot strings in `uart.log`.
- **[M3] Missing Device Enumeration**: When M1 hits unknown device access, machine halts. By iteratively running and observing `qemu.log`, add minimal "dummy devices" one by one to push firmware further.

See [NOTICE.md](NOTICE.md) and [docs/validation.md](docs/validation.md).

License: overlay and tools are **GPL-2.0-or-later**; upstream QEMU retains its own license.
