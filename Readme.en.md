# D750 QEMU Verification Prototype (`nikon-d750`)

> **Disclaimer**: This project **does not contain** and **does not download** any Nikon firmware. Firmware must be provided locally by the user, and the entire toolchain processes it strictly read-only.

Following the architecture of [WonderLantern/z7-qemu](https://github.com/WonderLantern/z7-qemu) and [WonderLantern/z9-qemu](https://github.com/WonderLantern/z9-qemu), this is a minimal verification prototype for the Nikon D750 (EXPEED 4, `D750_0115`): **a QEMU board-level overlay + a suite of host-side evidence tools**.

The goal is not to simulate the entire camera, but to answer four questions sequentially:
- **M0**: Can the main image be loaded at the inferred base address and booted from the inferred entry point?
- **M1**: What MMIO windows does the first execution fragment access?
- **M2**: Does the firmware output bytes from the candidate UART block?
- **M3**: How far can we get after implementing the first missing device?

---

## Table of Contents
- [1. Current Status & Roadmap](#1-current-status--roadmap)
- [2. Quick Start](#2-quick-start)
  - [2.1 Build (Requires C Toolchain)](#21-build-requires-c-toolchain)
  - [2.2 Run](#22-run)
  - [2.3 Static Verification Only](#23-static-verification-only)
  - [2.4 First Actual Run (M0 Passed)](#24-first-actual-run-m0-passed)
- [3. Machine Model](#3-machine-model)
  - [3.1 GUI & CMOS Status](#31-gui--cmos-status)
- [4. Static Evidence Collected](#4-static-evidence-collected)
- [5. Directory Structure & Dependencies](#5-directory-structure--dependencies)
- [6. Relationship with z7-qemu / z9-qemu](#6-relationship-with-z7-qemu--z9-qemu)
- [7. Boundaries & Future Work](#7-boundaries--future-work)

---

## 1. Current Status & Roadmap

Currently **completed and verified**:

| Item | Status |
| --- | --- |
| Static evidence: vector table, entry, page tables, flash/RAM windows, UART candidates | ✅ Ran on real `D750_0115` modules, see [docs/findings.md](docs/findings.md) |
| Board source code `nikon-d750-lab.c/.h` | ✅ Written (QEMU 11.1 API, 10.2.4 adapted via prepare script) |
| Overlay install script `qemu/prepare_source.py` | ✅ Idempotent, unit tests cover 11.1 / 10.2 / unknown version rejection |
| `fwscan` / `run` / `probe` / `build` tools | ✅ Written; `probe` tested with real RSP against stock QEMU `-M virt` |
| Host-side tests | ✅ `python3 tests/run_tests.py` → 20 passed |
| Board C code compilation | ✅ Compiled on WSL Ubuntu 26.04 (gcc 15.2) + QEMU 11.1.0 |
| `nikon-d750` machine actual run | ✅ **M0 passed**: loaded at `0x90000000`, executed from entry `0x9027D52C`, returned normally, exited cleanly in 0.18s |
| LCD scanout/dump pipeline | ✅ Configurable framebuffer → PPM; test card verified; firmware image still absent |
| M1 (MMIO) / M2 (UART) / M3 (Devices) | ⏳ Not started; current execution fragment accesses 0 MMIO |
| Full camera UI / ISP / CMOS / Storage | ❌ Out of scope |

### ⚠️ Warning Regarding Stock QEMU
If you have the official default QEMU installed (e.g., `C:\Program Files\qemu` on Windows), it usually only has `qemu-system-arm` / `qemu-system-aarch64` targets, and **no `nikon-*` machine** in `-M help`. QEMU machines are registered at compile-time and cannot be loaded at runtime like plugins. 
**Therefore, "booting D750 directly with an installed QEMU" is impossible; you must use `tools/build.py` to compile the overlay into `qemu-system-arm`.**
See [docs/build.md](docs/build.md) for stock version/target lists. `tools/run.py` will explicitly reject it before boot (exit code 3). The `binary/` directory in this repo contains a Linux `qemu-system-arm` built in WSL, usable directly in WSL.

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
  --flash   "$FW/a1010_011100.bin"
```

Measured output (evidence in `evidence/m0/`, `evidence/m0-gdb/`):
```text
exit=0  timed_out=False  wall_seconds=0.18  uart=0B  mmio_events=0
d750-halt: pc=0x00000ff0 r0=0x80002000 r1=0x00000000 sp=0x97ffff00 lr=0x00000ff0
```

**Interpretation**:
- Entry `0x9027D52C` is a **called function**, not a reset handler. Without assistance, it pushes `{r4,r5,r6,lr}` to `0xFFFFFFF0..0xFFFFFFFC` (SP=0), executes `pop` returning LR=0, and PC runs away to 0 — the most important finding from the first run.
- The machine thus adds **assisted boot**: low 64 KiB RAM, SP=top of RAM, LR pointing to halt window at `0xFF0`, r0=0. After function returns, halt device records registers and requests QEMU exit cleanly.
- This fragment accesses **0 MMIO** (`mmio_events=0`) and produces **no UART output** (`uart=0B`). So the next step for M1/M2 is **finding the caller of this init function or the next stage entry**; `-machine entry=...` allows trying other hypotheses directly.
- Scanned 10 candidate entries in image: all `0 MMIO`. `0x9025D700` enters a no-MMIO wait loop. Conclusion: **the next stage is not in `b1010`**, likely from boot ROM or flash outside `a1010`. See [findings §11.4](docs/findings.md#114-candidate-entry-scan-negative-results).

---

## 3. Machine Model (One-Liner Version)

| Item | Value | Evidence Strength |
| --- | --- | --- |
| CPU | 1× Cortex-A9 (`-smp 2` can try) | Medium: ARMv7 Thumb-2 + VFP/NEON + T-Kernel strings |
| Main RAM | `0x90000000`, default 128 MiB | High: `0x90020000` page table literal, `0x9027D52C` pointers |
| Main image loaded | `b1010_115a.bin` @ `0x90000000` | High |
| Initial PC | `0x9027D52C` (change via `-machine entry=`) | Medium: see §4 vector table contradiction |
| Low memory | `0x0..0xFFFF` RAM; `0xFF0` halt window | Runtime evidence: entry writes vector words to `0x0` |
| Assisted boot | SP=top of RAM, LR=`0xFF0`, r0=0 | Runtime evidence: entry returns after `push`/`pop` |
| Flash window | `0x10000000`, 8 MiB, loads `a1010_011100.bin` | Med-High: descriptor table references `0x1002CB8C/0x100A1094/0x100F48C0` |
| UART candidate | `0x80005010..0x80005014` byte registers | Medium: driver fragment `0x27CC00..0x27D304` |
| GIC/timer | `a9mpcore_priv` @ `0x1E000000` | Low: placeholder, no access evidence yet |
| Diagnostics | 4 GiB low-priority catch-all, logs unknown MMIO | — |

The machine is **diagnostics-first**: by default, unmodeled accesses are logged in `qemu.log` (PC/address/width/direction) instead of returning plausible values; `-machine strict=on` makes QEMU stop at the first unknown access. This is better for verification than "filling zeros to fake boot past it".

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
├── tools/
│   ├── fwscan.py               Static verification profile, generates manifest
│   ├── run.py                  Launch, timeout, evidence collection
│   ├── probe.py                Minimal GDB RSP client
│   └── build.py                Download/unpack/overlay/build/record
├── tests/                      20 host-side tests (no QEMU build required)
├── analysis/
│   ├── d750-0115.json          Real image scan results
│   ├── lcd-testcard.png        LCD pipeline test card (host-written)
│   └── ...                     Other firmware analysis artifacts already in repo (see below)
├── binary/                     Pre-built Linux qemu-system-arm + COPYING + README
├── evidence/                   M0 / GDB / LCD / boot-scan run evidence
├── docs/                       findings / architecture / validation / build / gui-cmos
├── PRODUCT.md  MANIFEST.json  SHA256SUMS
├── Setup-D750.ps1  Run-D750.ps1
└── .build/ .local/ runs/       Local generated artifacts (Git ignored)
```

`analysis/` only contains `d750-0115.json` and `lcd-testcard.png` generated by this QEMU product; the rest (movie bitrate, TIFF, patch, etc.) are existing firmware analysis artifacts in the same repo, kept for context but out of QEMU product acceptance scope.

> **Repo publishing tip**: `binary/qemu-system-arm` is ~96 MiB (GitHub single file limit 100 MiB). Recommend as Release attachment or manage via Git LFS; add `binary/` to `.gitignore` if not committing. `evidence/*/command.json` records absolute paths at generation; replace with placeholders before making public if needed.

---

## 6. Relationship with z7-qemu / z9-qemu

- **Inherited**: source overlay format, idempotent `prepare_source.py` registration, "user-supplied firmware + local manifest + no firmware distribution" boundary, RSP/GDB and UART evidence habits.
- **Different**: Z7 is dual Cortex-A15, 33 MB payload, with ISP/LCD/browser control; Z9 is quad-core AArch64, 82 MB payload. D750 prototype only has **M0–M3 boot verification**, no UI/sensor/image pipeline, CPU is A9 assumption.
- **Not inherited**: addresses, IRQs, peripheral protocols, boot calls. All constants come from D750's own bytes, each labeled with confidence.

---

## 7. Boundaries & Future Work

- This is an **assisted verification prototype**: entry chosen by host, SP/LR given by host, not equal to natural power-on boot.
- Compiled and ran to M0 on WSL; M1–M3 unfinished, `0x1E000000` MPCore, UART register semantics, CPU model all still assumptions.
- No signing, no repacking, no update container processing; firmware files strictly read-only.

**Roadmap (M1-M3)**:
- **[M1] MMIO Capture**: Need to find real Boot stage (possibly at low address or Flash), or try other entries via `-machine entry=...`. After capturing first MMIO read/write, analyze involved devices.
- **[M2] UART Output**: Confirm `0x80005010` is FIFO data register. Once confirmed, implement device model to see T-Kernel boot strings in `uart.log`.
- **[M3] Missing Device Enumeration**: When M1 hits unknown device access, machine halts. By iteratively running and observing `qemu.log`, add minimal "dummy devices" one by one to push firmware further.

See [NOTICE.md](NOTICE.md) and [docs/validation.md](docs/validation.md).

License: overlay and tools are **GPL-2.0-or-later**; upstream QEMU retains its own license.