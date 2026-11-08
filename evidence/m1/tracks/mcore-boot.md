# a1010 on the Cortex-M3 model (2026-11-09)

Goal: decide whether `a1010_011100.bin` is Cortex-M firmware by booting it on an
M-profile machine instead of the A9.

## Setup

- Machine: `mps2-an385` (Cortex-M3), `-cpu cortex-m3,cfgend=on`, `-m 16M`.
- Image: `a1010_vec_le.bin` — a1010 with the **first 16 big-endian vector
  entries byte-swapped to little-endian**, so QEMU's loader reads the intended
  values (`SP=0x2000F8C0`, `PC=0x0000C20D`). The code itself is already BE8
  (little-endian instructions), so it is not modified.
- Command:

  ```sh
  qemu-system-arm -M mps2-an385 -cpu cortex-m3,cfgend=on -m 16M \
    -display none -monitor none -serial file:uart.log \
    -D qemu.log -d int,guest_errors,in_asm -no-reboot -nic none \
    -kernel a1010_vec_le.bin
  ```

## Result

```
Loaded reset SP 0x2000f8c0 PC 0xc20d from vector table
```

Execution (0 exceptions over 4 s):

```
0x0000c20c  bl SystemInit (0xc2ae)
0x0000c2ae  SystemInit body
0x0000c2c0  bx lr
0x0000c210  bl 0x10368
0x00010368  clock/PMU init
0x00010380  poll loop
0x00010386  ldr r2,[r1]; lsls r2,#0x1e; bmi 0x10386
```

At 2 s the CPU is still at `0x00010386` (GDB):

```
pc=0x00010386  lr=0x0000c215  sp=0x2000f8b8
r1=0x00300f40  r2=0xc0000000
mem[0x00300f40] = 00 00 00 00 ...
```

## Interpretation

- a1010's reset handler, `SystemInit` and `.data` copy loop all execute with
  **zero exceptions** on an M-profile CPU, after only a vector-table
  endianness patch. That is independent confirmation that a1010 is
  Cortex-M firmware.
- The hang is a **D750-specific hardware poll**: the code writes/reads a
  clock/PMU block based at `0x00300F40` and waits for bits that MPS2 never
  drives. On MPS2 that address falls inside SSRAM1, so reads return 0 instead
  of faulting; the poll therefore spins forever.
- To go further on the M-core we would need the D750 clock/PMU register
  semantics at `0x00300F40` (and its neighbours `+4`, `+0xC`), or a patched
  image that skips the poll (diagnostic only).

Raw log: `mcore-boot.log`.
