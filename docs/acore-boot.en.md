# A-core boot chain: correct reset to a T-Kernel service loop

> [中文](acore-boot.md) | English

> Date: 2026-11-24 · Machine: `nikon-d750` · Status: **the host-assisted
> A-core chain now reaches the next-stage image / T-Kernel service loop;
> there is still no console/GUI and no complete camera boot.**

This records the 2026-11-24 A-core work. All conclusions come from real b1010
bytes and QEMU runs; `tools/acore_boot.py` is a **diagnostic fixture**, not a
boot-ROM reconstruction.

## 1. Fix the layout first

Earlier M0/M1 loaded b1010 at `0x90000000`. Nikon-Patch's D750 IDA scripts give
the real layout:

- ROM base **`0x90020000`**;
- file 0 is the ARM vector table, reset = **`0x9027D524`**;
- the old "`0x9025D700` boot stub" was actually code at `0x9027D700`.

With `tools/run.py --payload-base 0x90020000 --entry 0x9027D524`, the A-core
executes the **real reset path** rather than a shifted fragment.

## 2. Fixtures added

| Fixture | Purpose | Nature |
| --- | --- | --- |
| `aux2-base=0xB8000000` / `aux2-size=0x40000` | A-core IRAM: stack at `0xB801FFxx`, page tables at `0xB801FC00` | required to run; not a guessed RAM base |
| `io-stub=on`: A2/A120/A161/A300/AD/AE/A340 | lets ready-polling in the boot path pass | diagnostic register files, not a hardware model |
| `--vector-fix` (optional; SVC changed to `movs pc,lr`) | preserve SPSR's ARM/Thumb bit on SVC return | diagnostic bypass; off by default, uses the real SVC handler |
| zero `0x100A6704` | pass the next-stage image's shared boot flag (initial value 2) | host GDB write; the firmware file is untouched |

> `0x400F2000/0x400F3000` belong to the M-core. The A-core path uses
> A2/A120/A161/A300/AE/A340 instead; do not mix the two maps.

## 3. Observed chain

```text
0x9027D524  reset
0x9027D944  MMU/cache setup (SCTLR/TTBR/DACR)
0x9027D5A4  blx 0x90020098
0x90020098  build page tables (0xB801FC00.., stack 0xB801FFE0)
0x1000E200  next-stage image (copied into the flash window)
0x1000E24C  wait for [0x100A6704] == 0
0x1002AFE0  svc #5 (T-Kernel service)
0x10025474  A300 status polling / service loop
```

State after 3–4 s:

```text
PC=0x10025474  LR=0x10012938  SP=0x10600BD8
CPSR=0x20000093 (ARM, SVC)
UART=0 B
```

`session.json` also records the flag transition (`0x02` -> `0x00`) and 32 bytes
at the final PC. The run settles in a **stable service/polling loop**, not a
crash.

## 4. What this proves

Proven:

- the real reset path completes and builds MMU page tables in the
  `0xB8000000` IRAM bank;
- execution jumps into the next-stage image copied at `0x1000xxxx`;
- that image calls `svc #5` and loops on A300 status;
- no unhandled exception with `-d int,guest_errors`.

Not proven:

- this is not a complete A-core boot: no T-Kernel services, scheduler,
  console, filesystem, or GUI;
- SVC uses the real handler by default; `--vector-fix` is only a diagnostic
  bypass, and real service semantics are unknown;
- the writer of `0x100A6704` is now known: `0x1000E240` writes 2; no in-image
  clearer exists, so zeroing it is a host fixture (see §5);
- A300/A161/A120 ready bits are diagnostic values, not hardware semantics.

## 5. Plugin capture (2026-11-24 22:00)

`tools/memtrace.c` is a filtered TCG plugin covering flag/page tables/next-stage
image/vectors/stack/UART candidates. Build:

```sh
gcc -shared -fPIC -O2 $(pkg-config --cflags glib-2.0) \
  -I$QEMU/include/plugins -o tools/memtrace.so tools/memtrace.c
python3 tools/acore_boot.py ... --plugin tools/memtrace.so
```

The canonical run (real SVC handler, 6000 events) captured `0x100A6704`:

> The `b1010` used here was reconstructed from local
> `nov7/b1010_mmuoff.bin` and `nov7/b1010_reloc1.bin` (they differ by only
> 2 bytes; the result hashes to `faada7fe…f82937fd`). The original module
> directory is gone; the run itself does not modify firmware.

```text
0x9027D854  w  0x100A6704 = 0   ; BSS/data clear
0x1000E240  w  0x100A6704 = 2   ; A-core doorbell
0x1000E24C  r  0x100A6704 = 0   ; passes after the host clears it
```

There is no third writer in the image, so this is a **cross-core handshake**:
A-core writes 2, then waits for the M-core/boot ROM to clear it. The plugin saw
no `0x80005010`/`0x440C4xxx` accesses; UART is still 0. The `0x1C200` value on
the stack is not by itself proof of a baud rate.

It also exposed a fixture bug: `vector-fix` always wrote `payload+0x20000`, so
with `payload-base=0x90020000` it actually patched `0x90040000`; SVC still used
the original vector (509 reads of `pc=0x90020008` / `0x90020028`). After fixing
it to `payload+0`, `--vector-fix` produced 4549 events with no SVC-vector reads,
but ended at the `b .` self-loop `0x10000874`; the default (no vector-fix) still
reaches the real-handler service loop at `0x10025474`.

## 6. Reproduce

```sh
python3 tools/acore_boot.py \
  --qemu ~/d750-build/src/qemu-11.1.0/build/qemu-system-arm \
  --payload "$FW/b1010_115a.bin" \
  --out runs/acore-boot --seconds 5
```

The script sets a hardware breakpoint at `0x1000E24C`, zeroes `0x100A6704`,
continues, then saves `session.json`/`qemu.log`/`uart.log`. Raw evidence:
[`evidence/acore/`](../evidence/acore/) (`memtrace*.qemu.log`,
`memtrace-summary.json`).

## 7. Next steps

1. reconstruct the real SVC handler (`0x90291D30`) service table/return contract
   instead of relying on `--vector-fix`;
2. use the plugin to trace the **cross-core clearer** of `0x100A6704`
   (M-core/boot ROM side);
3. model A300/A161 status bits and see whether a real task loop starts;
4. a complete A-core boot still needs the boot ROM/flash dump context.

**In one line: the A-core now runs from reset into the next-stage image's
SVC/service loop; a full camera boot still needs T-Kernel services and the
missing boot-ROM context.**
