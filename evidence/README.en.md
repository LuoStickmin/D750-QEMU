> [中文](README.md) | English

# evidence/

This directory holds the evidence left by **actual runs**, not hand-written documentation.

| Directory/file | Contents | Key conclusions |
| --- | --- | --- |
| `m0/` | `command.json`, `session.json`, `qemu.log`, `uart.log` | Non-GDB M0: exit 0, 0.39 s, halt record `r0=0x80002000` |
| `m0-gdb/` | Same as above, plus RSP snapshots | `entry_pc=0x9027d52c`, `entry_ok=true`, CPSR `0x400001d3`; RSP disconnects after the guest exits by itself |
| `lcd/` | Same as above + `lcd.ppm` | 8×8 ARGB8888 dumped from `0x92000000`; demonstrates the scan/dump chain |
| `boot-scan.txt` | Scan output for 10 candidate entry points | All 0 MMIO; `0x9025d700` did not return within 2 s; the next stage is not inside `b1010` |

## How to Read

- The `halt` field of `session.json` is the register snapshot when the entry point returns; the `lcd` field is the size/format/path of the last
  dump; `mmio.by_address` is the aggregate of unmodeled accesses.
- `qemu.log` is the raw log of `-d guest_errors`; `d750-halt:` / `d750-lcd:` /
  `d750-probe:` are prefixes written by the machine itself.
- Paths in `command.json` / `session.json` are replaced with `<repo>`,
  `<firmware>`, `<build>` placeholders (privacy handling for the public
  repository); re-run with your own paths after moving the checkout.
- The M0/GDB/LCD evidence here was produced by the **v0.1.0** binary. Since
  v0.1.1 `session.json` also records `status`, `payload_sha256`,
  `flash_sha256`, and `halt.return_ok` / `halt.mode`; the old files do not have
  these fields, and `run.py` still parses them.

## Boundaries

- `m0*` only proves that "the entry point executes and returns"; it does not prove that firmware boot completes.
- `lcd/` is a dump of an empty/default framebuffer; the test card (`analysis/lcd-testcard.png`) was written by the host
  via GDB, not rendered by the firmware.
- There is no serial output and no MMIO access; do not describe this evidence as "GUI/CMOS working".
