> [中文](README.md) | English

# evidence/

This directory holds the evidence left by **actual runs**, not hand-written documentation.

| Directory/file | Contents | Key conclusions |
| --- | --- | --- |
| `m0/` | `command.json`, `session.json`, `qemu.log`, `uart.log` | Non-GDB M0: exit 0, 0.39 s, halt record `r0=0x80002000` |
| `m0-gdb/` | Same as above, plus RSP snapshots | `entry_pc=0x9027d52c`, `entry_ok=true`, CPSR `0x400001d3`; RSP disconnects after the guest exits by itself |
| `lcd/` | Same as above + `lcd.ppm` | 8×8 ARGB8888 dumped from `0x92000000`; demonstrates the scan/dump chain |
| `m1/` | `command.json`, `session.json`, `qemu.log`, `uart.log` + `gdb-entry.json` | M1: stub → `0x1002CB8C` (Thumb, args 0/0/2/0/1); first MMIO `0xe000e180←0x00100000`; then hits an M-profile instruction at `0x100240AC` |
| `m1/tracks/` | `layout-matrix.md`, `b1010-flash-svc.log`, `ttbr0-run.log`, `veneer-reloc-run.log`, `veneer-scan.txt`, `loader-segments.txt`, `ida-layout.txt`, `ida-layout-run.log`, `cross-model-d3300.txt`, `e6-e5-e4-layout.txt`, `expeed-io-run.log`, `m0-entry-fullflash.log`, `mcore-boot.log`/`.md` | 12-layout comparison; TTBR0 check; after `veneer-slot`: 0 undefined, 1 SVC, 0 aborts; loader segment table; Nikon-Patch IDA layout (base `0x90020000`); D3300 cross-model; E6/E5/E4 map (D780 header+branch, D850 `0x10000000`/`0x4002xxxx`, D750 `0x90020000`); `io-stub` passes the `0xAE00060C` poll |
| `boot-scan.txt` | Scan output for 10 candidate entry points | All 0 MMIO; `0x9025d700` did not return within 2 s; the next stage is not inside `b1010` |

## How to Read

- The `halt` field of `session.json` is the register snapshot when the entry point returns; the `lcd` field is the size/format/path of the last
  dump; `mmio.by_address` is the aggregate of unmodeled accesses.
- `qemu.log` is the raw log of `-d guest_errors`; `d750-halt:` / `d750-lcd:` /
  `d750-probe:` / `d750-a1010-io:` are prefixes written by the machine itself.
  The last one counts only unmodelled accesses originating inside the a1010
  range (`session.json.mmio.first_a1010`).
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
- `m1/gic-unmapped/` deliberately puts the MPCore back at the old placeholder
  to expose the first MMIO address; `m1/default/` is the corrected-base run.
  Together they show "address located" and "device connected".
- `m1/gdb-entry.json` is a host-side RSP snapshot, not a firmware self-report;
  the undefined instruction at `0x100240AC` was reproduced with `-d int`
  (see `docs/m1-boot-chain.en.md`).
- There is still no serial output, and M1 cannot be called a closed boot chain.
