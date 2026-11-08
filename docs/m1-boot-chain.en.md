# M1: Boot-Stub Run and a1010 Target Verification

> Date: 2026-11-08 · Environment: WSL2 Ubuntu 26.04, gcc 15.2, QEMU 11.1.0 overlay
> Firmware: `b1010_115a.bin` (20,324,448 B, SHA-256 `faada7fe…`),
> `a1010_011100.bin` (786,432 B, SHA-256 `690b7d1c…`)

This continues the 2026-11-07 M1 update (boot stub at `0x9025D700`, a1010 base
`0x10018000`, Thumb-bit correction). Only measurements produced by an **actual
QEMU run** are recorded here, including the parts that contradict that update.
The original material is `update_1107.zip` at the repository root.

## TL;DR

| Item | Result | Status |
|---|---|---|
| Boot stub `0x9025D700` | entered from an MMU trampoline at `0x1000`, stepped through to `bx ip` | ✅ run |
| a1010 at `0x10018000` | `bx ip` target `0x1002CB8C` lands on file `0x14B8C`, entered in **Thumb** | ✅ run |
| Entry state | `PC=0x1002CB8C`, `CPSR.T=1`, `SVC`, `LR=0x9025D754`, `r0..r4=0,0,2,0,1` | ✅ GDB |
| First a1010 MMIO | `wr 0xE000E180 ← 0x00100000` (GIC distributor `ICENABLER0`) | ✅ run |
| QEMU MPCore base | changed from `0x1E000000` to **`0xE000E000`** (same write) | ✅ fixed |
| Stub turns the MMU on | b1010 init writes `SCTLR=0x1C05`; page-table base comes from config slot `0x100F48C0` | ✅ measured |
| Which core owns a1010 | the image carries a **big-endian Cortex-M vector table** and executes `MRS/MSR BASEPRI` at `0x100240AC` → **M-profile firmware** | ⚠️ new question |
| Is M1 "done" | the 1107 address/entry does run, but the target is not A-core code → **not a closed chain** | ⚠️ needs input |

In one sentence: **the 1107 address arithmetic really does execute in QEMU and
yields the first MMIO, but that MMIO comes from a Cortex-M image, not from the
A-core's next boot stage.** A full flash image or module offset table is needed
to decide what the A-core's `0x1002CB8C` actually belongs to.

## 1. New M1 machine options

| Option | Default | Purpose |
|---|---|---|
| `boot-mode=stub\|entry` | `stub` | `stub`: enter the b1010 boot chain; `entry`: assisted M0 entry |
| `a1010-base=<addr>` | `0x10018000` | where the a1010 image is loaded inside the flash window |
| `thumb-fix=on\|off` | `on` | patch the **in-memory copy** of the `0x25D7F8` literal from `0x1002CB8C` to `0x1002CB8D`; the file is never modified |
| `mmu-bringup=on\|off` | `on` | emulate the missing boot ROM: install a 4 GiB identity table, write DACR/TTBR0/TTBCR, and put the table base into the config slot |
| `mmu-table=<addr>` | `0` (auto) | place the identity table at this address and **do not override** the config slot (use the image value); the 2026-11-09 check used it to verify `0x201E2200` is a valid TTBR0 |
| `flash-size=<size>` | 8 MiB | flash window size (max 64 MiB), so the full 20 MiB b1010 can be mapped |
| `aux-ram-size=<size>` | `0` | add a RAM bank at `0x20000000` (e.g. `4M`) |
| `vector-fix=on\|off` | `off` | install a minimal ARM vector table at `0x90020000` (SVC/IRQ/FIQ return, faults spin) |
| `mpcore-base=<addr>` | `0xE000E000` | A9 MPCore (GIC/timers/watchdog) base; set `0x1E000000` to reproduce the "unmapped" observation |

In `boot-mode=stub` the initial PC is the internal trampoline `0x1000` (not
`0x9025D700`); `session.json` still reports the architectural entry
`0x9025D700`, so the implementation detail does not leak into evidence.

## 2. Measured entry state (GDB, `evidence/m1/gdb-entry.json`)

```
power_on   pc=0x00001000  cpsr=0x400001d3  sp=0x97fff000
breakpoint a1010 entry:
           pc=0x1002cb8c  cpsr=0x600001f3  T=1  mode=0x13(SVC)
           sp=0x97fff000  lr=0x9025d754
           r0=0x00000000 r1=0x00000000 r2=0x00000002 r3=0 r4=0x00000001
           bytes: 10 b5 14 20 f9 f7 df ff 04 22 00 21 0f 20 f8 f7
```

`LR=0x9025D754` is exactly the instruction after `bx ip`, and `r0..r4` are
exactly the arguments the stub passes — `func(*(0x100F48C4), *(0x100F48C8),
2, 0, 1) = (0, 0, 2, 0, 1)`. All three agree with the 1107 static analysis.

First six instructions (continuous Thumb):

```
0x1002cb8c  push {r4,lr}
0x1002cb8e  movs r0,#0x14
0x1002cb90  bl   0x10026b52
0x10026b52  ...
```

## 3. The stub's MMU enable is a real trap

The 1107 `stub_trace.py` defaults to `--skip-init 0x9025DA40`, so it never saw
this path. In a real run:

- b1010's init at `0x9025DA40` reads config slot `0x100F48C0`, writes
  `(value & ~0x3FF) | 0x42` into **TTBR0/TTBR1**, then writes
  `SCTLR=0x1C05` (**M=1**) at `0x9025DA80`.
- With only a1010 loaded, the slot reads 0, TTBR0 becomes `0x42`, and the next
  fetch translation-faults:

```
Taking exception 3 [Prefetch Abort] ... IFSR 0x5 IFAR 0x9025da84
```

- `mmu-bringup=on` therefore (1) installs a 4 GiB identity map of 1 MiB
  sections at the top of DRAM (`0x97ff0000`), and (2) writes that address into
  config slot `0x100F48C0`. The init then programs `TTBR0=0x97ff0042` itself and
  execution continues identity-mapped, **with zero changes to the firmware
  file**.

> This also corrects the 1107 claim that the config slot only affects callback
> pointers: **it first of all supplies the page-table base**.

## 4. First MMIO and the GIC base

`evidence/m1/gic-unmapped/qemu.log` (MPCore deliberately left at the old
placeholder `0x1E000000`, so the access falls through to the diagnostic window):

```
0x1002cb8c:  10b51420f9f7dfff          ; push {r4,lr}; movs r0,#0x14; bl ...
0x1002cb90:  ...
0x10026b52:  00f01f020121914040094ff0e02202eb8000c0f880117047
0x10026b64:  c0f88011
d750-a1010-io: pc=0x10026b64 wr addr=0xe000e180 size=4 value=0x00100000
```

- `0xE000E180` with `0x00100000` is GIC distributor `ICENABLER0` (IRQ 20).
- The same run also reported `gic_cpu_write: Bad offset 80`; both point at an
  A9 MPCore at **`0xE000E000`**. The old `0x1E000000` was wrong.
- Re-running with the corrected base (`evidence/m1/default/`): the write is
  accepted by the real GIC model and the **unmodelled MMIO count is 0**. The
  two runs complement each other: the first locates the block, the second shows
  it is now modelled.

## 5. Which core does a1010 belong to?

With a1010 at `0x10018000` and the Thumb bit forced, the entry runs. Execution
then stops at `0x100240AC` on an undefined instruction:

```
0x100240ac:  ef f3 11 80   ; MRS r0, BASEPRI
0x100240b0:  4f f0 20 01   ; mov.w r1,#0x20
0x100240b4:  81 f3 11 88   ; MSR BASEPRI, r1
```

`BASEPRI` is an **ARMv7-M** system register; it is always undefined on a
Cortex-A9 (A-profile), and QEMU behaves accordingly:

```
Taking exception 1 [Undefined Instruction] ... PC=0x100240ac
```

Looking at a1010 as a module:

| Offset | Content | Meaning |
|---|---|---|
| `0x00` | `20 00 f8 c0` (BE `0x2000F8C0`) | initial MSP pointing into `0x20000000` SRAM |
| `0x04` | `00 00 c2 0d` (BE `0x0000C20D`) | reset vector, Thumb → `0xC20C` |
| `0x08..` | `0x000138FB`, `0x00013321`, … | NMI/HardFault/…/IRQ vectors |
| `0xC20C` | `bl SystemInit; bl __libc_init_array; b .` + `.data` copy loop | typical Cortex-M `Reset_Handler` |
| `0xC0AC` | `MRS/MSR BASEPRI` | M-profile critical-section primitive |

In other words **a1010 is big-endian (BE8: big-endian data, little-endian
instructions) Cortex-M firmware**; its strings even say `D750   Firmware A
Copyright Nikon Corp.` It cannot be reached by an A-core `bx`.

Two possibilities remain, and both need external input:

1. **the 1107 base is a coincidence**: the A-core's `0x1002CB8C` belongs to a
   different A-profile module (not among the three extracted modules), and
   a1010 merely happens to contain a decodable Thumb function at that offset;
2. **the core attribution is wrong**: if the D750 really has a second core,
   a1010 belongs to the M-core and the A-core's next stage is simply missing
   (it would only appear in the full flash image / module table).

Until the full flash or module map is available, **M1 must not be recorded as
"complete"**.

## 6. Impact on M2 and next steps

- **GIC is connected**: `mpcore-base=0xE000E000` is now the default; the next
  unmodelled access is the real new-device clue (serial candidate
  `0x80005000` has not been hit yet).
- **No serial output**: `uart=0B`; the M2 acceptance condition is unchanged.
- **Next actions, in order**:
  1. obtain the full flash image (or the container module directory plus each
     module's flash offset/size) and rebuild the `0x10000000` window; identify
     which module owns `0x1002CB8C`;
  2. if a1010 is confirmed to be M-core firmware, bring it up on `cortex-m3`
     separately (reset vector `0xC20D`, SRAM `0x20000000`) and verify its
     behaviour;
  3. keep using `strict=on` + `-d in_asm` to find the A-core's real first new
     MMIO.

## 7. Reproduction

```sh
# M1: boot stub -> a1010 target (GIC modelled, no unmodelled accesses)
FW=/path/to/D750_0115.dec.modules
python3 tools/run.py \
  --payload "$FW/b1010_115a.bin" --flash "$FW/a1010_011100.bin" \
  --boot stub --a1010-base 0x10018000 --timeout 6 --trace in_asm

# Reproduce "first MMIO is 0xE000E180" by putting the MPCore back at the old
# placeholder address:
python3 tools/run.py ... --boot stub --mpcore-base 0x1E000000
# session.json should contain mmio.first_a1010 = {wr 0xe000e180, pc 0x10026b64}

# GDB state: start QEMU with -S and attach with tools/probe.py
```

Evidence: `evidence/m1/{gic-unmapped,default,gdb-entry.json}`.

## 8. Boundaries

- The M-profile conclusion rests on three independent observations
  (instruction encoding, vector table, reset handler); cross-check on real
  hardware or an M-core model is still recommended.
- `mmu-bringup` is a **shim standing in for the boot ROM**, not a
  reconstruction of it; it only guarantees identity mapping, not the real
  cache/permission attributes.
- `thumb-fix` only touches the in-memory copy; container CRC /
  `SHA1(body||K8)` are unaffected.

---

## 9. Follow-up (2026-11-09)

Three no-input checks (static call chain, 12 flash layouts, booting a1010 on
Cortex-M3) moved the conclusion to "**the flash window looks like b1010's
image**, a1010 is confirmed M-core firmware, the first-stage boot ROM is
missing". See [m1-tracks-2026-11-09.en.md](m1-tracks-2026-11-09.en.md). The
"a1010@`0x10018000` executes" result here remains a valid **controlled
experiment**, but is no longer treated as the real module attribution.
