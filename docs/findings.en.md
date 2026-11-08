> [中文](findings.md) | English

# Static Evidence and Confidence (D750_0115)

This document records only **inferences that are read directly from local bytes or can be re-verified from them**. Every
entry is annotated with a confidence level; "assumptions" do not enter acceptance criteria. Reproduction commands are at
the end of the document.

Inputs (read-only):

| File | Size | SHA-256 |
| --- | --- | --- |
| `D750_0115.dec.modules/b1010_115a.bin` | 20,324,448 | `faada7fe2bcc90fef8877fae37965ee836f867b08f5736c67c5266b1f82937fd` |
| `D750_0115.dec.modules/a1010_011100.bin` | 786,432 | `690b7d1c7683cda36c72b5911cdd474ad5bc78f9467b369f3f86dc7316600213` |

---

## 1. Exception Vector Table (High Confidence)

Starting at file offset 0, `b1010` holds 8 ARM vectors, 6 of which are `ldr pc,[pc,#0x18]` (`E59FF018`), one `nop`,
and one `b`:

| Vector | Instruction | Literal | Target |
| --- | --- | --- | --- |
| 0 reset | `E59FF018` | `0x9027D524` | file `0x27D524` |
| 1 undef | `E59FF018` | `0x90291C80` | `0x291C80` |
| 2 swi | `E59FF018` | `0x90291D30` | `0x291D30` |
| 3 prefetch | `E59FF018` | `0x90291DA8` | `0x291DA8` |
| 4 data | `E59FF018` | `0x90291DB8` | `0x291DB8` |
| 5 | `E320F000` | 0 | — |
| 6 | `EA00000D` | 0 | — |
| 7 irq | `E59FF018` | `0x90291DEC` | `0x291DEC` |

The vector table uses 32-byte boundaries with the literals immediately following, which is the standard ARMv7 vector
layout. The fact that entries 5/6 are not `ldr pc` does not affect the determination.

## 2. Entry Point Contradiction (High-Confidence Observation, Medium-Confidence Conclusion)

With a base address of `0x90000000`, the reset literal points at file offset `0x27D524`. The two 32-bit words there are:

```
0x27D524: 0x1041D9A8
0x27D528: 0x1041DBA8
```

Both have ARM condition code `0x1` (NE), not AL; decoding them as instructions yields conditional data-processing
instructions, which do not look like a reset entry. `0x27D52C` is instead the proper start of a function:

```
0x27D52C: E3500002  cmp  r0, #2
0x27D530: E3A03000  mov  r3, #0
0x27D534: E92D4070  push {r4, r5, r6, lr}
```

Moreover, the boot descriptor table at file offset `0x25D760` **references `0x9027D52C` exactly** (see §4). This
prototype therefore sets the initial PC to `0x9027D52C` and keeps "vector table reset points at the literal pool" as a
`fwscan` `WARN` (`vector_reset_points_at_code = false`). The first actual run further confirmed that it is a **called
function** (`push`/`pop`, returns via LR); see §11.

Possible explanations (unverified, in order of likelihood):

1. The vector table is relocated/patched at runtime by a first-stage loader, and the file contains build-time
   placeholder values;
2. The first 8 bytes are an "entry slot" into which the loader writes the real branch at startup;
3. The vector table belongs to a different base address than the main image (but the page table literals in §3 refute
   this).

`-machine entry=0x90000000` can be used to return to the control group that "really resets from the vector table".

## 3. MMU / Page Tables (High Confidence)

`mcr p15,0,rX,c1,c0,0` (writing SCTLR) appears at:

```
0x25D728  0x25D938  0x25D99C  0x25D9AC  0x25DA28  0x25DA80  0x129DA50
```

The literal at `0x25D7FC` is `0x90020000`, and the same code section also contains `mcr p15,0,rX,c2,c0,0` (TTBR0) and
`mcr p15,0,rX,c3,c0,0` (DACR). Conclusion:

- The main image link/load base is **`0x90000000`**;
- The first-level page table target is **`0x90020000`** (base + 0x20000);
- The code enables the MMU itself; QEMU does not need to build page tables for it, but RAM must cover `0x90020000`,
  where the page tables live (the default 128 MiB is sufficient).

## 4. Boot Descriptor Table (Medium Confidence)

`0x25D758..0x25D800` is a compact address/length table; its first few entries are:

```
0x25D760  0x9027D52C  0xAE000200   <- entry or stage descriptor
0x25D768  0x902A2E9C  0x90284000
0x25D770  0x90280000  0x9128DB64
0x25D778  0x10000000  0x00030344
0x25D780  0x912BDEA8  0x10030344
0x25D798  0x9132EC00  0x100A1480  0x0005344C   <- (dest, src, size)?
0x25D7B0  0x9132EBF4  0x100A1094  0x00000004
0x25D7F8  0x1002CB8C  0x90020000               <- (src, dest) page table?
```

Reading it as a load table that **copies several segments from flash to RAM** is an inference: `0x100A1480 + 0x5344C`
still falls within the 786,432 bytes of `a1010`, and so does `0x1002CB8C`, which is self-consistent with "a1010 is
mapped at `0x10000000`". The table also contains buffer addresses such as `0x9132EC00`, which lie outside the main image
range but inside the 128 MiB RAM.

## 5. Flash Window (Medium-High Confidence)

There are **23,660** 32-bit literals in the main image that fall within `0x10000000..0x10800000`; the minimum is
`0x10000000` and the maximum is `0x107FFF24`. The maximum sits exactly inside the 8 MiB boundary, so the prototype sets
the flash window to **`0x10000000` + 8 MiB**. Since 2026-11-08 `a1010` is loaded at `0x10018000` by default
(`-machine a1010-base=` overrides it) so that `bx 0x1002CB8C` lands on a Thumb prologue; this is a prototype mapping,
not the real flash module offset.

The three entries `0x100F48C0/0x100F48C4/0x100F48C8` exceed the size of `a1010`, showing that the real flash contains
content beyond `a1010`; the prototype returns 0 for the parts not provided and states this in the documentation. The
2026-11-08 run further shows that b1010's init treats `0x100F48C0` as the **page-table base**, so `mmu-bringup` fills it
with the identity-table address (§12).

## 6. Serial Port Candidate (Medium Confidence)

The literal pool at `0x27D504..0x27D51C` contains:

```
0x80005011  0x88000104  0x80005010  0x80005012  0x80005014  0x8800010A
```

The instructions that use them are spread over `0x27CC08..0x27D304`; all are byte/halfword accesses, and the same code
section shows the "read status → test bit → write data" shape. The prototype therefore makes
`0x80005000..0x800050FF` into a byte-register serial port: writes to `+0x10` are TX, `+0x11`/`+0x14` return status
(default `0x03`), and all other accesses are logged and return 0.

This is an **assumption**, not a data sheet: if the first actual run produces no output from `d750-uart`, the
addresses/widths in `qemu.log` are the protocol to match next.

## 7. Instruction Set and CPU (Medium Confidence)

- The code contains both ARM and Thumb-2: `0x54` is the start of an ARM exception handler
  (`sub lr,lr,#4; push {r3,lr}`), and `0x14868` is `E92D 4FF7` (`push.w`).
- The full image has 1,623 CP15 accesses and 9,979 VFP-shaped and 17,479 NEON-shaped candidates (the latter two are
  mixed with data and serve only as an order-of-magnitude reference).
- The `T-Kernel` string is at file offset `0x1264FDA`; `Ver.1.15a` is at `0x48`.
- ARM CPU + VFP/NEON + the 2014 EXPEED 4 generation → the prototype defaults to Cortex-A9. **No** MIDR read value
  proves the model—the MIDR reads in the main image are just library functions (`0x129D230` etc.), not board-level
  identification. Changing the core (e.g. to A15) requires also changing the private block model; this prototype
  restricts `-cpu` to `cortex-a9` to avoid creating the illusion that "a different core would just run it".

## 8. Pointer Distribution (Used to Define the Windows; Low Confidence but Re-verifiable)

| Range | b1010 Hits | a1010 Hits |
| --- | --- | --- |
| `0x10000000..0x10800000` (flash) | 23,660 | 2,154 |
| `0x80000000..0x90000000` (peripherals) | 119,084 | 6,538 |
| `0x90000000..0x91000000` (RAM) | 90,016 | 563 |
| `0x91000000..0x92000000` (high RAM) | 13,635 | 115 |
| `0x40000000..0x60000000` | 303,660 | 25,306 |
| `0xA0000000..0xB0000000` | 79,797 | 1,830 |

These counts include large amounts of data/literals and cannot be used directly as a "device address table"; they are
only used to confirm that the three windows `0x80xxxxxx`/`0x90xxxxxx`/`0x10xxxxxx` are not made up.

## 9. Still Unanswered Questions

1. The real entry of the first-stage loader (boot ROM) on the D750 and the register state it delivers to `b1010`.
2. The real register semantics of the `0x80005010` serial port (status bits, FIFO, baud rate).
3. ~~The real base addresses of the GIC/timers~~ — established as **`0xE000E000`** on 2026-11-08 (§12).
4. Dual-core or single-core; how the second core is started (spin-table / bootreg). If a1010 belongs to a second
   (Cortex-M) core, the firmware boundary between the two cores has to be redrawn.
5. The layout of the flash content beyond `a1010`; a1010 itself is now confirmed to be an M-profile image and can no
   longer be treated as the A-core's next stage (§12).
6. Which address space `0x1041D9A8/0x1041DBA8` belongs to (another mapping of the `0x10000000` peripheral window?).

## 10. Re-verification

```powershell
python tools/fwscan.py `
  --main  "...\b1010_115a.bin" `
  --flash "...\a1010_011100.bin" `
  --out   analysis\d750-0115.json
```

The `checks` in the output are the automated verification of "whether the profile constants match the bytes";
`verdict = profile-has-warnings` is the expected result, and the only warning is the vector/entry contradiction in §2.

---

## 11. First Actual Run (2026-11-05)

Build: WSL Ubuntu 26.04 / gcc 15.2 / QEMU 11.1.0. Run: `tools/run.py` + the two modules above.

### 11.1 First Round: No Low Memory, No Assistance

The first few lines of `qemu.log` (in order of occurrence):

```
d750-probe: pc=0x9027d534 wr addr=0xfffffff0 size=4 value=0
d750-probe: pc=0x9027d534 wr addr=0xfffffff4 size=4 value=0
d750-probe: pc=0x9027d534 wr addr=0xfffffff8 size=4 value=0
d750-probe: pc=0x9027d534 wr addr=0xfffffffc size=4 value=0
d750-probe: pc=0x9027d53c wr addr=0x00000000 size=4 value=0
d750-probe: pc=0x9027d560 wr addr=0x00000000 size=4 value=0x1041d688
d750-probe: pc=0x9027d584 rd addr=0xfffffff0 ... (four pops)
d750-probe: pc=0x00000000 rd addr=0x00000000 ... (runaway)
```

Corresponding disassembly:

```
0x27D52C  cmp  r0, #2
0x27D530  mov  r3, #0
0x27D534  push {r4, r5, r6, lr}   ; SP=0 -> 0xFFFFFFF0..0xFFFFFFFC
0x27D538  ldrhs r0, [pc, #...]
0x27D53C  str  r0, [r3]           ; store to address 0
...
0x27D584  pop  {...}              ; LR=0 -> PC=0
```

**Conclusion (high confidence)**:

1. `0x9027D52C` is a **called function**, not the reset entry;
2. Address `0x00000000` must be writable RAM (it writes the vector slot and reads it back);
3. The caller must provide SP and LR; otherwise `pop` returns to 0 and the PC runs away.

### 11.2 Second Round: Low Memory + Assisted SP/LR + halt

Machine changes: map the low 64 KiB as RAM; `SP=0x97FFFF00`, `LR=0x00000FF0`, `r0=0`; put a 4-byte halt window at
`0xFF0`, so that an instruction fetch there requests a clean QEMU exit.

Measured:

```
exit=0  timed_out=False  wall_seconds=0.393  uart=0B  mmio_events=0
d750-halt: pc=0x00000ff0 r0=0x80002000 r1=0x00000000
          sp=0x97ffff00 lr=0x00000ff0
```

**Conclusion**:

- M0 passes: the entry runs to completion and returns cleanly;
- The return value `r0=0x80002000` resembles a peripheral base address, but this section never dereferences it;
- This section performs **no MMIO at all**, so M1/M2 have not begun;
- The value `0x1041D688` that the entry writes to `0x0` falls in `0x1041xxxx` (outside/deep beyond the flash window),
  showing that the real flash layout or address space still has unexplained parts (§9 questions 5/6).

### 11.3 Next Steps

1. Find the caller of `0x9027D52C`: there is no ARM `BL` to that address inside the image, only the literal/descriptor
   table at `0x25D760`; the caller may be in the boot ROM or a loader.
2. Boot under ROM semantics: read the entry and segment table from the descriptor table, and simulate "copy segments →
   call entry → next stage".
3. Try other candidates with `-machine entry=` (`0x9025D720` also returned to the halt window, but with
   `r0=0xEFFD3494` and no evidence of MMU/MMIO).
4. Return to M1/M2 only after finding a path that actually accesses `0x8000xxxx`.

### 11.4 Candidate Entry Scan (Negative Result)

Run each of the following addresses for 2 seconds (no GDB; halt exits immediately; `0x9025D700` used a timeout):

| Entry | Result | probe events | UART |
| --- | --- | --- | --- |
| `0x9025D0D4` / `D1C4` / `D360` / `D400` / `D434` / `D464` / `D474` | returns to halt | 0 | 0 |
| `0x9025D720` | returns to halt | 0 | 0 |
| `0x90000000` (vector table) | returns to halt | 0 | 0 |
| `0x9027D52C` (default) | returns to halt | 0 | 0 |
| `0x9025D700` | did not return within 2 s | 0 | 0 |

These entries cover the function boundaries in `0x25D000..0x25D720` (obtained by a mixed scan for ARM `E92D` and Thumb
`B5xx`). None of them **reaches a peripheral**, showing that the early code in the image is a pure RAM/CP15 path;
`0x9025D700` enters a wait/polling loop but has no MMIO—it is very likely waiting for a RAM flag.

Therefore the "next stage" is more likely to be:

- after the boot ROM copies/jumps according to the `0x25D760` table (the ROM is not in this image);
- or flash content outside `a1010` that is not present in this directory (the copy table's `0x100A1480 + 0x5344C`
  already exceeds `a1010`'s 0xC0000).

This is a negative result, but it largely exhausts the space of "which function to try next": continuing to blindly try
functions inside the image will not produce MMIO, so the next step should turn to the ROM handoff convention/flash
layout.

### 11.5 Conclusion: Inputs Outside the Image Are Needed

The update container has only `a1010` (786,432 B), `_wma`, and `b1010`. The layer needed to reach
drivers/display/sensors is most likely in:

1. **boot ROM** (not in the update container, and usually not readable);
2. or a region on flash beyond `a1010` (the `0x100A1480 + 0x5344C` referenced by the copy table has already passed the
   end of `a1010`).

Therefore the most worthwhile investment right now is not to keep writing device models, but to obtain any one of:

- a complete flash/ROM dump (even read-only);
- or the handoff convention of the loader/boot ROM (entry arguments, segment table semantics, next-stage address);
- or a boot trace captured from the hardware side (PC/MMIO sequence).

Without these inputs, the register contract of the GUI/CMOS can only be guessed, and this project does not guess.

---

## 12. M1 Run: Boot Stub and the a1010 Target (2026-11-08)

Full record: [m1-boot-chain.en.md](m1-boot-chain.en.md); conclusion-level summary below.

### 12.1 Established

- The machine gained `boot-mode=stub`: from the MMU trampoline at `0x1000` into `0x9025D700`, the stub runs to
  `bx ip`, and the target `0x1002CB8C` is entered in **Thumb** with `LR=0x9025D754` and `r0..r4=0,0,2,0,1`
  (measured over GDB).
- First a1010 MMIO: `wr 0xE000E180 ← 0x00100000` (GIC `ICENABLER0`). The MPCore base is therefore corrected from
  `0x1E000000` to **`0xE000E000`**; after the correction the access is absorbed by the GIC model and the unmodelled
  count drops to zero.
- b1010's local init writes `SCTLR=0x1C05` to turn the MMU on, and the page-table base comes from config slot
  `0x100F48C0`. With only a1010 loaded the slot reads 0, the init programs `TTBR0=0x42`, and the next fetch
  prefetch-aborts at `0x9025DA84`. The `mmu-bringup` shim installs a 4 GiB identity table at the top of DRAM and
  fills the slot, with zero changes to the firmware file.

### 12.2 New question: a1010 is not the A-core's next stage

- Execution hits `MRS r0, BASEPRI` / `MSR BASEPRI, r1` at `0x100240AC`; those are **ARMv7-M only**, so a Cortex-A9
  must take an undefined exception (reproduced by QEMU).
- a1010's header is a **big-endian Cortex-M vector table**: initial MSP `0x2000F8C0` at `0x00`, reset `0x0000C20D`
  at `0x04`, and a typical `Reset_Handler` at `0xC20C` (`SystemInit` + `.data` copy loop). Its string is
  `D750   Firmware A Copyright Nikon Corp.`.
- So the Nov 7 `a1010-base=0x10018000` is self-consistent for Thumb decoding, but it points the A-core's `bx` at
  M-core firmware. Two explanations remain:
  1. the base is a coincidence and the A-core's `0x1002CB8C` belongs to an A-profile module not yet extracted;
  2. the D750 has two cores, a1010 belongs to the M-core, and the A-core's next stage has not been obtained.

### 12.3 Conclusion

- **M1 is recorded as "reached the target, not closed"** and must not be accepted as complete;
- new input is needed: a full flash image / module offset table (to identify the real owner of `0x1002CB8C`), or
  hardware documentation confirming the core topology;
- the only new hard device fact is the GIC base; the UART still produces 0 bytes.
