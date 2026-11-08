> [中文](validation.md) | English

# Validation Plan: From "It Loads" to "It Explains"

## 0. Evidence layers

Following z7-qemu's discipline: record the following four things separately, and none of them can substitute for another.

| Layer | Evidence for this prototype | Does not mean |
| --- | --- | --- |
| Container/static | `fwscan` checks, sha256, vectors/literals | Code can execute |
| Loading | QEMU did not report `cannot load payload`; bytes are present in RAM | Entry is correct |
| Execution | PC reaches checkpoints, UART has bytes, MMIO sequence | Hardware behavior is correct |
| Physical | None | Flashing/real-device compatibility |

## 1. Milestones

### M0 — Loading and entry

Command:

```powershell
python tools/run.py --payload ...\b1010_115a.bin --flash ...\a1010_011100.bin `
  --boot entry --a1010-base 0x10000000 --gdb --run-seconds 2
```

> M0 is the legacy default; since 2026-11-08 the machine defaults to
> `boot-mode=stub`, so reproducing M0 requires
> `--boot entry --a1010-base 0x10000000`.

Pass criteria (all must be met):

1. `session.json.snapshot.entry_pc == "0x9027d52c"`, `entry_ok == true`;
2. The mode bits of `snapshot.cpsr` are SVC (low 5 bits `0x13`), and A/I/F are masked;
3. QEMU did not exit during the loading phase;
4. The record "instruction fetch near `0x1041D9A8`" does not appear immediately in `qemu.log`
   (if it appears, the entry assumption is wrong; see M0-neg).

Failure handling:

- If `entry_ok=false`: first look at the `pc` printed by `run.py`, and confirm whether `-machine entry=` is
  parsed; then check whether `-kernel` really points to `b1010`.
- If the entry runs away: rerun with `--strict`. The first unmodeled access is logged as `d750-strict:`
  (address, width, direction, PC) and `run.py` exits with code 7; this is usually the first device address for M1.
- If `halt.return_ok=false` (exit code 6): the guest slid into `0xFF0` through an exception path, and the run
  must not be recorded as a passing M0.

**Measured result (2026-11-05, passed)**:

```
session runs/20261105-075610/
exit=0  timed_out=False  wall_seconds=0.393  uart=0B  mmio_events=0
qemu.log: d750-halt: pc=0x00000ff0 r0=0x80002000 r1=0x00000000
          sp=0x97ffff00 lr=0x00000ff0 firmware returned to the assisted trampoline
```

`wall_seconds` includes QEMU process startup and varies between 0.18 and 0.40 s
depending on cold/warm start; the number above is from `evidence/m0/session.json`.

Conclusion: the entry can be loaded and finishes execution, exiting normally through the halt window; but it is a **called function**, not
a reset. Without assistance, the first run will `push` to `0xFFFFFFF0..0xFFFFFFFC` and jump back to 0;
this negative result is saved in `docs/findings.md` §11.

`--gdb` mode has another record (`runs/20261105-075746/`):

```
snapshot.entry_pc = 0x9027d52c
snapshot.entry_ok = true
snapshot.cpsr     = 0x400001d3   (SVC, A/I/F masked, Z set)
stop.kind         = connection-closed   (guest exited by itself; RSP link closed)
```

### M0-neg — Negative control

Run once with `-machine entry=0x90000000` (true reset), and record where it stops/crashes.
This control is used to prove that "`0x9027D52C` is more like an entry point than the vector literal", rather than treating an exception as success.

### M1 — First MMIO sequence

M1 is now the default mode (`boot-mode=stub`). Command:

```powershell
python tools/run.py --payload ... --flash ... `
  --boot stub --a1010-base 0x10018000 --timeout 6 --trace in_asm
```

Look at `session.json.mmio`:

- `first_a1010`: the first unmodelled access **originating in the a1010 address
  range**. With the GIC modelled at `0xE000E000` it should be `null` in a
  default run;
- `by_address`: top 10 addresses by count, with `addr / rw / count / first_pc`;
- Compare against the UART candidates in `docs/findings.md` §6: does
  `0x80005010..14` appear?
- Compare against `0xE000E000` (MPCore): it should normally be absorbed by the
  model and not appear in the unmodelled list.

Pass criteria, in two layers:

1. **Entry layer**: with GDB stopped at `0x1002CB8C`, `CPSR.T=1`,
   `LR=0x9025D754`, `r0..r4=0,0,2,0,1`; `qemu.log` contains a TB for
   `0x1002cb8c`;
2. **Target layer**: that address really belongs to the A-core's next stage and
   not to another core's image. This is currently **not satisfied**: a1010 is
   M-profile firmware, see [m1-boot-chain.en.md](m1-boot-chain.en.md).

**Current result**: the entry layer passes and the first a1010 MMIO is
`wr 0xE000E180 ← 0x00100000` (`evidence/m1/gic-unmapped/`); the target layer
does not, so M1 is recorded as "reached the target, not closed" and must not be
accepted as complete.

### M2 — UART output

Pass criteria: `session.json.uart.bytes > 0`, and `uart.tail` is readable text or a stable
binary prefix.

**Current result**: `uart.bytes=0`; the UART path has not been reached yet. M1
does enter a1010 and issues a GIC write, but never reaches the candidate serial
block, so this is not a UART model failure.

If `uart.bytes == 0` but there are many `d750-uart: rd +0x11` entries in `qemu.log`:

- This means the address is right but the status bit is wrong. Record the return values of the read sequence (currently `0x03`),
  change the status values in `d750_uart_read()` in `nikon-d750-lab.c`, or
  add a "set TX-done after writing data" state machine in `d750_uart_write()`;
- Do not change the status to `0xFF` just to "make it output" and declare success—that only fools the polling.

### M3 — Add the first device

Fixed procedure:

1. Run with `--strict`: `qemu.log` gets a `d750-strict:` line (address, width, direction, PC),
   `session.json.strict` records the same, and `run.py` exits with code 7;
2. Add minimal MemoryRegionOps in `nikon-d750-lab.c`, implementing only the **observed** accesses;
3. Add a rejection test case (wrong width/wrong direction should be logged and return 0, not silently pass);
4. Rerun M0–M2 to confirm there is no regression;
5. Write the new address/semantics into `docs/findings.md`, and update `fwscan.PROFILE` (if applicable).

### L1 — LCD dump pipeline self-check (independent of firmware UI)

```powershell
python tools/run.py --payload ... --flash ... `
  --lcd-base 0x92000000 --lcd-width 320 --lcd-height 240
```

Pass criteria:

- `runs/<ts>/lcd.ppm` exists, with the correct P6 header and dimensions;
- When a test card is written into that window with GDB, the PNG pixels match the written values;
- By default (the firmware does not write the framebuffer), the result is an all-black image;
- When the window is out of bounds, only `d750-lcd:` log entries are written and no file is produced.

**Measured (2026-11-05)**: 320×240 ARGB8888, GDB writes 8 color bars + grayscale,
PPM/PNG pixels are correct, artifact `analysis/lcd-testcard.png`. This only proves the "guest RAM →
scan/dump" pipeline, not the firmware GUI; `docs/gui-cmos.md` §3.2 makes the same statement.

### Run exit codes (`tools/run.py`)

| Code | Meaning |
| --- | --- |
| 0 | Run finished without strict/suspicious state |
| 2 | `qemu-system-arm` not found |
| 3 | That QEMU has no `nikon-d750` machine (stock build) |
| 4 | `--gdb` was requested but the GDB stub did not open |
| 6 | Halt was reached from an exception state (`return_ok=false`) |
| 7 | `--strict` stopped at the first unmodeled access |

## 2. Evaluation rules

- A run without `session.json` does not count as evidence;
- A run without a recorded command line and SHA-256 of payload/flash does not count as evidence
  (`run.py` writes `payload_sha256` / `flash_sha256` since v0.1.1);
- `session.json.halt.return_ok` must be `true`; `false` (exit code 6) means the guest reached the halt window
  through an exception path and the run is not a passing M0;
- `session.json.status` is the machine-readable verdict: `halt` / `strict-stop` / `halt-suspicious` /
  `timeout` / `ran`;
- A string appearing on the UART does not mean "boot completed"; it only means "this output path works";
- The PC reaching an address does not mean "the function executed correctly"; also check whether the expected MMIO was triggered before and after it;
- Results from `-smp 2` cannot be extrapolated to a single core, and vice versa.

## 3. Common failures and diagnosis

| Symptom | Possible cause | Next step |
| --- | --- | --- |
| `machine 'nikon-d750' not found` | Using stock QEMU | Build the overlay first |
| `cannot load payload` | Path/size exceeds RAM | Check the path and `-m` |
| `Bad address` immediately on startup | Entry/RAM window is wrong | `--strict` + `entry=0x90000000` control |
| PC loops at `0x0` or `0xFFFF0000` | PC was overwritten by a reset | Confirm `-S` is used only for GDB; do not `system_reset` |
| UART has 0 bytes, polling address is fixed | Status-bit assumption is wrong | Check the return value of `rd +0x11` and change the state machine |
| MMIO log flooding | Firmware is waiting for some bit | Use `mmio.by_address` to find the most frequent address |
| Cannot connect GDB | Port/firewall/`-S` | `run.py` already uses a random port on 127.0.0.1; check `qemu.log` |

## 4. Evidence storage

```
runs/20261105-123456/
├── command.json    exact argv, entry, GDB flag
├── uart.log         raw guest serial bytes
├── qemu.log         -d guest_errors diagnostics (incl. d750-probe/d750-strict/d750-uart)
└── session.json     summary: status, payload/flash SHA-256, exit, uart, mmio, halt, snapshot
```

These files may contain firmware behavior/paths; **do not** publish them directly; before publication, review them separately according to z7-qemu's publication process.

## 5. What counts as "done"

The completion definition for this prototype is: **M0 passes, M1 obtains a stable sequence, M2 has at least one explainable output
or a clear "status-bit assumption is wrong" conclusion, and M3 adds at least one device without regression**.
It does not include UI, shooting, or the image pipeline; those are work for subsequent profiles, and should not be claimed in this prototype's
README.
