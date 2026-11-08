/*
 * Nikon D750 validation prototype -- board constants.
 *
 * SPDX-License-Identifier: GPL-2.0-or-later
 *
 * Every address below is a *static-inference hypothesis* derived from
 * D750_0115 firmware modules, not a measured EXPEED 4 specification.
 * See ../docs/findings.md for the evidence and confidence of each line.
 *
 * Nothing in this file may be described as a Nikon board schematic.
 */
#ifndef HW_ARM_NIKON_D750_LAB_H
#define HW_ARM_NIKON_D750_LAB_H

/* Main image (b1010_115a.bin) load window.  Evidence:
 *  - literal 0x90020000 used as an MMU page-table destination;
 *  - literals 0x9027D52C / 0x90284000 / 0x912xxxxx in the payload
 *    resolve to in-image and buffer offsets under this base. */
#define D750_RAM_BASE          0x90000000ULL
#define D750_RAM_MIN           (32ULL * 1024 * 1024)
#define D750_RAM_MAX           (512ULL * 1024 * 1024)

/* Entry hypothesis.  The payload's exception table at file offset 0 points
 * at 0x9027D524, which is two words inside a literal pool; the boot
 * descriptor at file offset 0x25D75C references 0x9027D52C, which is a
 * normal function prologue.  The prototype therefore enters at +0x27D52C
 * and exposes -machine entry=... so a different hypothesis can be tested
 * without rebuilding.
 *
 * 0x9027D52C is a *function*, not a reset handler: its first instruction
 * pushes to the stack and it returns through LR.  The machine therefore
 * supplies an assisted startup state (SP, LR trampoline, r0=0); see
 * docs/architecture.md. */
#define D750_ENTRY_OFFSET      0x27D52CULL

/* Low memory: the entry writes a word to address 0 and reads it back, so
 * the first 64 KiB must be writable RAM, not the diagnostic window. */
#define D750_LOWRAM_BASE       0x00000000ULL
#define D750_LOWRAM_SIZE       (64ULL * 1024)
#define D750_HALT_TRAMPOLINE   0x00000FF0ULL   /* "b ." placed here */

/* Flash / first-stage window. */
#define D750_FLASH_BASE        0x10000000ULL
#define D750_FLASH_SIZE        (8ULL * 1024 * 1024)

/* a1010 load base.  Measured 2026-11-07: the b1010 boot stub's `bx ip`
 * target 0x1002CB8C only lands on a clean Thumb-2 function prologue when
 * a1010 is mapped at 0x10018000 (file offset 0x14B8C).  The earlier
 * 0x10000000 hypothesis mapped the same target onto a data table. */
#define D750_A1010_BASE        0x10018000ULL

/* M1 boot chain.  b1010 is loaded at D750_RAM_BASE; its startup hand-off
 * is at +0x25D700.  The hand-off at 0x9025D750 does `bx ip` with
 * ip = *(0x9025D7F8).  The literal holds 0x1002CB8C (bit0=0, ARM state)
 * although file 0x14B8C is Thumb code, so QEMU patches the in-memory copy
 * to 0x1002CB8D by default instead of repacking the firmware. */
#define D750_BOOT_STUB         0x9025D700ULL
#define D750_BX_SITE           0x9025D750ULL
#define D750_BX_LITERAL_OFF    0x25D7F8ULL
#define D750_BX_TARGET         0x1002CB8CULL

/* Stack given to the boot stub: 4 KiB below the top of the DRAM window. */
#define D750_BOOT_STUB_SP_DELTA 0x1000ULL

/* Emulated boot-ROM MMU bring-up.  b1010's local init at 0x9025DA40 ends by
 * writing SCTLR = 0x1C05, i.e. it turns the MMU on assuming the boot ROM
 * already installed TTBR0/DACR and an identity page table.  This machine
 * starts directly at the stub, so it supplies that missing prologue:
 *   - 16 KiB of short-descriptor section entries at the top of DRAM,
 *   - a tiny ARM prologue in low RAM that writes DACR, TTBR0 and TTBCR,
 *     then jumps to the stub.
 * The page table identity-maps all 4 GiB with 1 MiB sections (AP=rw, C/B on).
 */
#define D750_BOOT_MMU_TRAMPOLINE 0x00001000ULL
#define D750_BOOT_MMU_TABLE_SIZE 0x4000ULL
#define D750_BOOT_MMU_TABLE_DELTA 0x10000ULL

/* The boot stub reads the page-table base from this config slot and passes
 * it to b1010's init, which programs TTBR0/TTBR1 with (value & ~0x3FF) | 0x42.
 * With zero flash the slot reads 0 and the init enables the MMU with
 * TTBR0 = 0x42, which faults at the next fetch. */
#define D750_CONFIG_SLOT0      0x100F48C0ULL

/* Cortex-A9 MPCore private block: GIC + per-CPU timers + watchdog.
 * Measured 2026-11-08: the first a1010 MMIO access is a 32-bit write of
 * 0x00100000 to 0xE000E180, i.e. GIC distributor ICENABLER0 at
 * 0xE000E000 + 0x180.  The earlier 0x1E000000 guess was wrong. */
#define D750_MPCORE_BASE       0xE000E000ULL
#define D750_GIC_NUM_IRQ       96

/* Byte-register serial block.  Code around file offset 0x27CC00 uses
 * 0x80005010/0x80005011/0x80005012/0x80005014 through byte accesses;
 * the device contract (TX at +0x10, status at +0x11/+0x14) is a
 * hypothesis, not a decoded datasheet. */
#define D750_UART_BASE         0x80005000ULL
#define D750_UART_SIZE         0x100

/* Catch-all diagnostic window used when strict=off.  Priority -1000 keeps
 * every real region (RAM, flash, MPCore, UART) in front of it. */
#define D750_PROBE_PRIORITY    (-1000)
#define D750_PROBE_SIZE        0x100000000ULL

#endif /* HW_ARM_NIKON_D750_LAB_H */
