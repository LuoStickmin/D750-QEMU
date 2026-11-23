# D750 M-core (Firmware A / a1010) validation prototype

> [中文](mcore.md) | English

> Date: 2026-11-23 · Machine: `nikon-d750-mcore` · Status: **boots to idle,
> but no console/GUI yet, and the RTOS is not proven fully initialized.**

This document records what `a1010_011100.bin` actually does on a dedicated
Cortex-M model. It answers one question: **as the D750 M-core firmware, how far
does a1010 get after reset, and which peripherals does it need first?** All
conclusions come from the local image and QEMU records; no firmware is included.

## 1. Input and identity

| Item | Value |
| --- | --- |
| Image | `a1010_011100.bin`, 786,432 B |
| SHA-256 | `690b7d1c7683cda36c72b5911cdd474ad5bc78f9467b369f3f86dc7316600213` |
| Identity string | `D750   Firmware A Copyright Nikon Corp.` @ `0x1F08` |
| Vector table | `0x0`, 16 entries, **32-bit big-endian** |
| MSP | `0x2000F8C0` |
| Reset | `0x0000C20D` (Thumb) |
| Code/data | BE8: little-endian Thumb instructions, big-endian data accesses |

The reset value is the same as D850's `a1330` (`0x0000C20D`), a strong clue that
the two M-core boot paths share an origin. Same address does not mean identical
code; this document only concludes from D750's real bytes.

## 2. Machine model

```sh
qemu-system-arm -M nikon-d750-mcore \
  -kernel /path/to/a1010_011100.bin \
  -display none -monitor none -serial file:uart.log \
  -D qemu.log -d int,guest_errors -no-reboot -nic none
```

| Item | Value |
| --- | --- |
| CPU | `cortex-m4` (VFP enabled; `-cpu` can override) |
| Flash | 1 MiB @ `0x00000000`, a1010 loaded directly |
| SRAM | 256 KiB @ `0x20000000` (MSP at `0x2000F8C0`) |
| Vector fixture | first `0x40` bytes (16 entries) word-swapped for QEMU's LE vector fetch |
| BE8 fixup | 0x100-byte big-endian SCB window at `0xE000ED00`, owning `VTOR`/`CPACR` |
| Diagnostics | 4 GiB catch-all: unmodelled access logs PC/address/width/direction |
| First peripherals | diagnostic register files at `0x400F2000` and `0x400F3000`, 0x1000 each |

### 2.1 What is a fixture and what is a conclusion

- **The image is not modified**: the vector word-swap happens only in QEMU's
  flash copy; SP/PC are read from the original big-endian bytes.
- The `0x400F2000` / `0x400F3000` register files are only a "return the last
  written value" diagnostic fixture, used to pass the mailbox echo/busy/ready
  polling. They are **not** a hardware model.
- The big-endian SCB window at `0xE000ED00` is a BE8 fixup, not an SCB model.
- The 4 GiB catch-all records unmodelled accesses as `d750-mcore-probe:`;
  strict mode stops at the first unmodelled access.

## 3. Observed boot trace

Actual probe log (`0x400F2/3` are now register files, so they no longer appear):

```text
Loaded reset SP 0x2000f8c0 PC 0xc20d from vector table
0xFF3A  rd  0x440CE000
0xFF40  wr  0x440CE000 = 0x80000000
0xFFB4  rd  0x440CE004
0xFFC2  wr  0x440CE004 = 0x40000000
0xFFE4  rd  0x440CE008
0xFFEC  wr  0x440CE008 = 0
0xFFCC  rd  0x440CE004
0xFFDA  wr  0x440CE004 = 0x03000000
```

The first probe run (before the `0x400F` register files were added) also logged:

```text
0xC2B0  rd  0x400F2000
0xC2B6  wr  0x400F2000 = 0
0xC2BE  wr  0x400F2004 = 0xB1000000   ; QEMU LE view; the BE write value is 0xB1
0x1036C rd  0x400F3004
0x10376 wr  0x400F3004 = 0x00015DC3   ; QEMU LE view; BE write value is 0xC35D0100
0x10378 rd  0x400F3004  (polling)
```

`0xC03C`'s `STR 0x8F -> 0xE000EF00` (NVIC STIR) comes from disassembly and the
3-second registers (`R1=0xE000EF00`, `PC=0xC04A`), not from the probe log (that
address is modelled by the NVIC).

Registers at 3 s (QMP):

```text
PC=0x0000C04A  LR=0x0000C04B  SP=0x2000F8B8
R1=0xE000EF00  R2=0x00000004  R9=0x2000FC00
XPSR=0x61000000  T priv-thread
```

- `0xC04A` is `bx lr`; with `LR=0xC04B`, BX clears bit0 and returns to `0xC04A`,
  a stable **idle self-loop**.
- After 3 s: **0 exceptions, 0 UART bytes**; all 8 MMIO accesses are at
  `0x440CE000`.
- Strict mode's first unmodelled access: `pc=0xFF3A rd 0x440CE000`.

## 4. Semantics read from the code (strong clues, not hardware-verified)

### 4.1 `0x400F3004` is a command/status mailbox

Disassembling `0x10368..0x103B0`:

1. read `[0x400F3004]`, take the low 20 bits, OR `0xC35D0100`, write back;
2. poll until the high 12 bits read back equal the written value (echo);
3. set bit0, poll until bit1 clears (busy -> done);
4. write `(low 20 bits) | 0x03E20000`, poll until bit17 sets (ready);
5. clear bit16, write `0x400F300C = 0xE09A`, then wait for the high-12-bit echo
   again.

This has the **same address and shape** as the D850 a1330 command/status
handshake at `0x400F3004`. The current register file lets these polls pass, but
does not prove the real hardware's bit semantics.

### 4.2 `0x440CE000` is a pin/clock block

The eight accesses read `+0x00` and set bit7; change bits 30/25/24 of `+0x04`;
change low bits of `+0x08`; then read `+0x04` again. This matches the D850
M-core pin/clock sequence and is **not UART TX**. No data-register write was
observed in this run.

### 4.3 UART candidates

Static scan for big-endian 32-bit words in a1010:

- `0x440C4xxx`: 62 hits;
- `0x440CE000`: 48 hits;
- `0x400F2xxx`: 6 hits; `0x400F3xxx`: 30 hits.

`0x440C4xxx` is the UART candidate range already located on D850, but a1010's
boot path **never accesses it**; UART remains 0 B. The image also has no
`UART`/`console` strings, so the address range alone is not proof that a serial
port exists.

## 5. Relation to D850-QEMU

Directly transferable:

- the `nikon-d850-mcore` machine skeleton (Cortex-M4, 1 MiB flash, 256 KiB
  SRAM, BE8 vector table, SCB window, catch-all, strict);
- the **address isomorphism** at `0x400F2000` / `0x400F3000` / `0x440CE000`;
- the method "fix the vector table/SCB first, then look at unmodelled accesses";
- the evidence/documentation format.

Not directly transferable:

- D850 A-core's LPAE/Cortex-A15 page-table fixture does not apply to D750 E4;
  D750 A-core remains a separate A9/short-descriptor problem;
- D850's `0xC05E` idle and D750's `0xC04A` idle are different addresses; D850's
  function boundaries cannot be copied blindly.

## 6. Boundaries and next steps

1. **This is not "M-core boot complete"**: it only proves that reset/SystemInit/
   clock mailbox/pin block/STIR can reach idle; there is no RTOS task, console,
   or display evidence.
2. `STIR=0x8F` (143) is outside `num-irq=96`; interrupt behavior is unmodelled.
   Next: raise the IRQ count to 240 and see whether a pending IRQ or exception
   appears.
3. Keep looking for a console: disassemble the callers of the `0x440C4xxx`
   initialization functions, or inject an IRQ after idle to wake a task. Do not
   claim serial output before TX is observed.
4. The A-core's next stage remains a separate problem: it needs a real
   flash/boot ROM or a loader hand-off; the M-core result does not replace it.

## 7. Reproduction

```sh
# Build (WSL)
cp qemu/nikon-d750-lab.c qemu/nikon-d750-lab.h \
   ~/d750-build/src/qemu-11.1.0/hw/arm/
ninja -C ~/d750-build/src/qemu-11.1.0/build -j 12 qemu-system-arm

# Run
qemu-system-arm -M nikon-d750-mcore \
  -kernel "$FW/a1010_011100.bin" \
  -display none -monitor none -serial file:uart.log \
  -D qemu.log -d int,guest_errors -no-reboot -nic none
```

Evidence: [`evidence/mcore/session.json`](../evidence/mcore/session.json),
[`boot.qemu.log`](../evidence/mcore/boot.qemu.log),
[`strict.qemu.log`](../evidence/mcore/strict.qemu.log).
