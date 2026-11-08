> [中文](architecture.md) | English

# Machine Model and Implementation Boundaries

## 1. Goals and Implementation Form

`nikon-d750` is a **validation prototype** that drives the locally decrypted D750 main image through the earliest
possible boot path and exposes "what is missing" at the lowest cost. It does not aim for a complete EXPEED 4
specification.

Its implementation form is the same as z7-qemu / z9-qemu: a **QEMU source overlay**.

```
hw/arm/nikon-d750-lab.c   board model (~850 lines)
hw/arm/nikon-d750-lab.h   memory-map constants
hw/arm/meson.build        + arm_ss.add(...)
hw/arm/Kconfig            + config NIKON_D750_LAB
configs/devices/arm-softmmu/default.mak  + CONFIG_NIKON_D750_LAB=y
```

`qemu/prepare_source.py` installs the above into the QEMU source tree, idempotently and repeatably. QEMU 11.1's chardev
frontend type is called `CharFrontend`; in 10.x it is called `CharBackend`. The overlay targets 11.1, and the prepare
script performs one textual substitution on 10.x trees, so both generations share the same
source. Only 11.1.0 has actually been built here; 10.x compilation is unverified.

## 2. Memory Map (Prototype Defaults)

| Start | Size | Contents | Attributes |
| --- | --- | --- | --- |
| `0x00000000` | 4 GiB | diagnostic catch-all | `MemoryRegionOps`, priority -1000; strict logs once then stops |
| `0x00000000` | 64 KiB | low-memory RAM (vectors/boot globals) | RAM, priority 0 |
| `0x00000FF0` | 4 B | halt window (auxiliary LR return point) | IO, priority 1 |
| `0x10000000` | 8 MiB | flash window; `-bios` image loaded at `a1010-base` (default `0x10018000`) | RAM-backed, writable in the prototype |
| `0xE000E000` | 0x2000 | `a9mpcore_priv` (GIC/timers/watchdog) | runtime evidence: first a1010 MMIO is `0xE000E180` |
| `0x80005000` | 0x100 | candidate byte serial port | subregion, priority 0 |
| `0x90000000` | `-m` (default 128 MiB) | main image and DRAM | `machine->ram` |

Priority relationship: specific regions > catch-all (-1000). The low 64 KiB must exist because the entry writes a
vector word to `0x0` and reads it back; the 4-byte halt window at `0xFF0` overlays the same RAM range.

## 3. Boot Flow

1. `-kernel` (or `-machine payload=`) supplies `b1010`, loaded at `0x90000000`;
   `-bios` (or `flash=`) supplies `a1010`, loaded at `a1010-base` inside the
   flash window (default `0x10018000`). Images are opened read-only; the
   payload is read into a host buffer and registered as a ROM blob, so
   `thumb-fix` only changes the in-memory copy.
2. Create `-smp` CPUs of type `machine->cpu_type` (default `cortex-a9`).
3. Create `a9mpcore_priv` at `mpcore-base` (default `0xE000E000`) and connect
   each CPU's IRQ/FIQ/VIRQ/VFIQ to the GIC's 4×N sysbus IRQ outputs.
4. The initial PC depends on `boot-mode`:
   - `boot-mode=stub` (default, M1): build a 4 GiB identity page table and a
     small ARM trampoline at `0x1000`; the trampoline writes
     `DACR/TTBR0/TTBCR` and branches to `0x9025D700`. The table base is also
     written into config slot `0x100F48C0`, and the b1010 `bx` literal is
     changed to `0x1002CB8D` in memory (`thumb-fix`).
   - `boot-mode=entry` (M0): PC = `entry` (default `0x9027D52C`),
     overridable with `-machine entry=0x...`.
5. **Auxiliary boot state** (added after the first M0 run; used by entry mode):
   - `SP = D750_RAM_BASE + ram_size - 0x100` (default `0x97FFFF00`);
   - `LR = 0x00000FF0` (halt window);
   - `r0 = 0`;
   - CPSR keeps QEMU's ARM reset value of SVC with A/I/F masked.
   - stub mode instead uses `SP = top of RAM - 0x1000`, `LR = 0`, so a bad
     return is visible.

The entry at `0x9027D52C` starts with `push {r4,r5,r6,lr}`, so without an SP it writes `0xFFFFFFF0..0xFFFFFFFC`; when
done it `pop`s back to LR. In the first actual run LR=0 caused the PC to run away, so the auxiliary state is
**required**, not an optional optimization.

### Why Not Use `arm_load_kernel()`

`arm_load_kernel()` writes a bootloader for the board, handles DTB/PSCI, and runs `-kernel` as a Linux image or a
bare-metal image. The D750 main image is not Linux and does not need QEMU's bootloader; here we directly use
`load_image_targphys` + `cpu_set_pc`, keeping the minimal semantics of "bytes go in, PC points there" and avoiding an
extra layer of inexplicable behavior.

### Reset Behavior

`system_reset` pulls the CPUs back to QEMU's default reset vector (0 or 0xFFFF0000) and does not automatically return to
`entry`. This is a known limitation of the prototype: for validation use a new `run.py` process, and do not rely on the
monitor's `system_reset`.

## 4. Device Contracts

### 4.1 Catch-All Diagnostic Window (`0x00000000`, 4 GiB)

- Read: log `pc/addr/size`, return 0.
- Write: log `pc/addr/size/value`, discard.
- Each record goes through `LOG_GUEST_ERROR` and is collected by `-d guest_errors -D qemu.log`.
- The first 512 records are logged individually; afterwards one in every 4096 is sampled, to keep polling from
  flooding the log.
- `run.py` aggregates the log into `session.json.mmio.by_address` (address × direction × count × first PC).
- `strict=on`: the first access is logged as `d750-strict:` and the run is stopped; `run.py` stores it in
  `session.json.strict` and exits with code 7. The address is not lost, and the guest never falls into an exception vector.
  Note: the shutdown request takes effect at the end of the current TB, so a halt line may follow `d750-strict:` in the
  log; trust `session.json.status=strict-stop`.

This is not a model that "returns plausible values". By default it lets the guest keep running while leaving the real
access sequence for the next round of modeling; strict turns "the first missing device" into an explicit stop.

### 4.2 Serial Port (`0x80005000`)

| Offset | Read | Write |
| --- | --- | --- |
| `+0x10` | 0 | low byte sent to chardev (`-serial file:uart.log`) |
| `+0x11` | `uart_status` (default 0x03) | logged |
| `+0x12` | 0 | logged |
| `+0x14` | `uart_status` | logged |
| Other | 0, logged | logged |

The status bits are an **assumption**. If the firmware polls something like "bit5 = TX empty", the first run will show
dense `rd +0x11` entries in `qemu.log`; adjust the model accordingly, rather than guessing an "all 1s" value.

### 4.3 MPCore

`a9mpcore_priv` provides the GIC, per-CPU private timers, the global timer, and
the watchdog. The base is **`0xE000E000`**, measured on 2026-11-08: the first
a1010 MMIO is `wr 0xE000E180 ← 0x00100000` (GIC distributor `ICENABLER0`), and
the same run also reported `gic_cpu_write: Bad offset 80`. The old
`0x1E000000` was the A9 reference layout with no D750 access evidence; the
`mpcore-base=` property remains so diagnostics can put it back and reproduce
the "unmapped" observation.

### 4.4 SMP

1 core by default. `-smp 2` can be tried, but the prototype's GIC outputs are only connected according to `smp.cpus`,
and the second core's boot convention (spin-table/bootreg) is not modeled; if the firmware waits for CPU1, `entry`
should be the same on both cores, or a `smp_bootreg` property should be added later.

### 4.5 LCD dump (Host-Side Observation, Not a Display Device)

Enabled when `lcd-base` is non-zero:

- on every halt and every 2 seconds, read `[lcd-base, lcd-base + stride*height)` from guest RAM and write a P6 PPM to
  `lcd-out`;
- with `lcd-stride=0`, the stride is computed as `width * bpp`; `argb8888` is interpreted as B,G,R,A in memory,
  `rgb888` as R,G,B, and `rgb565` as little-endian 16-bit;
- an out-of-range window only logs `d750-lcd:` and writes no file;
- with `lcd-base=0` (the default) it is completely disabled: no timer is allocated and no file is produced.

It provides no window, QMP `screendump`, or input events; these await the later G2 stage or a z7-style display surface.
For test card generation/validation, see `docs/gui-cmos.md` §3.2.

## 5. Diagnosis-First Design Trade-offs

| Trade-off | Rationale |
| --- | --- |
| Unknown MMIO returns 0 instead of random values | Lets the guest keep going while leaving the real address behind; random values would create inexplicable state |
| Not strict by default | One run captures the whole access sequence, which is faster than stopping at a new address each time |
| `strict=on` | Logs the first unmodeled access (`d750-strict:`) and stops; `run.py` exits 7 |
| No HLE / no RAM patching | What this stage must prove is "which behaviors are the firmware's own", not to coax out the UI |
| UART does only TX + fixed status | First turn "is there any output" into an observable fact |

## 6. Differences from Z7 / Z9

| | Z7 | Z9 | D750 (This Prototype) |
| --- | --- | --- | --- |
| CPU | 2× Cortex-A15 | 4× AArch64 | 1× Cortex-A9 (assumed) |
| payload | 33 MB @ `0x10020000` | 82 MB | 20 MB @ `0x90000000` |
| Display/ISP | yes | yes | no |
| Boot assistance | yes (explicitly calls the original function) | yes | yes (assisted SP/LR + halt window) |
| Acceptance | UI/shooting/RAW | UI/shooting/RAW/video | M0–M3 boot evidence |

Nothing is inherited in terms of addresses, IRQs, or peripheral protocols; only the engineering form and evidence
discipline are inherited.

## 7. Code Structure

- `nikon_d750_init()`: mapping, loading, CPU, MPCore, serial port, PC, optional LCD timer.
- `d750_probe_read/write()`: catch-all.
- `d750_uart_read/write()`: candidate serial port.
- `d750_halt_read()`: entry return point; the optional LCD dump is also triggered here.
- `d750_halt_state_is_clean()`: checks CPSR mode, LR and SP to tell a real return from a fault.
- `d750_lcd_dump()`: guest RAM → PPM.
- Machine properties: `payload`, `flash`, `entry`, `boot-mode`, `a1010-base`,
  `thumb-fix`, `mmu-bringup`, `mpcore-base`, `strict`, `lcd-*`.
- Log prefixes: `d750-probe:` / `d750-strict:` / `d750-uart:` /
  `d750-a1010-io:`; `run.py` parses by prefix.

## 8. Known Limitations

1. Built and run to M0 under WSL (Ubuntu 26.04 / gcc 15.2); the Windows MSYS2 artifact has not been built.
2. M1 reaches the Nov 7 target and its first MMIO, but the target module is
   M-profile firmware; the A-core chain is not closed.
3. Flash content beyond `a1010` is missing; reads return 0. The config slot
   `0x100F48C0` is therefore supplied by the `mmu-bringup` shim.
4. The serial port semantics and the exact CPU model are still assumptions;
   the GIC base is now measured (`0xE000E000`).
5. No VMState/migration; recovery means starting a new process.
6. Cache/TLB behavioral differences are not implemented, and there is no cycle accuracy; TCG timing does not represent
   the hardware.
7. The halt window sits at the end of the low-memory NOP sled: both a real return and an exception that slides to `0xFF0`
   can reach it. The machine records `return_ok` to tell them apart, and `run.py` exits 6 on `false`.
