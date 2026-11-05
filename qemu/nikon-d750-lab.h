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

/* Flash / first-stage window.  The descriptor table refers to
 * 0x1002CB8C, 0x100A1094 and 0x100A1480, all inside a1010_011100.bin
 * when it is mapped at 0x10000000. */
#define D750_FLASH_BASE        0x10000000ULL
#define D750_FLASH_SIZE        (8ULL * 1024 * 1024)

/* Cortex-A9 MPCore private block: GIC + per-CPU timers + watchdog.
 * Placeholder address; the payload has not yet been observed using it. */
#define D750_MPCORE_BASE       0x1E000000ULL
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
