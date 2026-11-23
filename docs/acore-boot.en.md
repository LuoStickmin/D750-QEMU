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
| `vector-fix=on` (SVC changed to `movs pc,lr`) | preserve SPSR's ARM/Thumb bit on SVC return | diagnostic; real SVC is handled by T-Kernel |
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
- SVC is currently returned by vector-fix; real service semantics are unknown;
- the writer/protocol of `0x100A6704` is unknown; zeroing it is a host fixture;
- A300/A161/A120 ready bits are diagnostic values, not hardware semantics.

## 5. Reproduce

```sh
python3 tools/acore_boot.py \
  --qemu ~/d750-build/src/qemu-11.1.0/build/qemu-system-arm \
  --payload "$FW/b1010_115a.bin" \
  --out runs/acore-boot --seconds 5
```

The script sets a hardware breakpoint at `0x1000E24C`, zeroes `0x100A6704`,
continues, then saves `session.json`/`qemu.log`/`uart.log`. Raw evidence:
[`evidence/acore/`](../evidence/acore/).

## 6. Next steps

1. replace the "return immediately" SVC with a minimal T-Kernel service table
   (at least the `svc #5` return contract);
2. find the writer of `0x100A6704` and verify whether it is an M-core/loader
   handshake;
3. model A300/A161 status bits and see whether a real task loop starts;
4. a complete A-core boot still needs the boot ROM/flash dump context.

**In one line: the A-core now runs from reset into the next-stage image's
SVC/service loop; a full camera boot still needs T-Kernel services and the
missing boot-ROM context.**
