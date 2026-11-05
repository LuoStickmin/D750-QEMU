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
python tools/run.py --payload ...\b1010_115a.bin --flash ...\a1010_011100.bin --gdb --run-seconds 2
```

Pass criteria (all must be met):

1. `session.json.snapshot.entry_pc == "0x9027d52c"`, `entry_ok == true`;
2. The mode bits of `snapshot.cpsr` are SVC (low 5 bits `0x13`), and A/I/F are masked;
3. QEMU did not exit during the loading phase;
4. The record "instruction fetch near `0x1041D9A8`" does not appear immediately in `qemu.log`
   (if it appears, the entry assumption is wrong; see M0-neg).

Failure handling:

- If `entry_ok=false`: first look at the `pc` printed by `run.py`, and confirm whether `-machine entry=` is
  parsed; then check whether `-kernel` really points to `b1010`.
- If QEMU reports `Bad address`: rerun with `--strict` to get the first unmapped access; this is usually
  the first device address for M1.

**Measured result (2026-11-05, passed)**:

```
session runs/20261105-075610/
exit=0  timed_out=False  wall_seconds=0.18  uart=0B  mmio_events=0
qemu.log: d750-halt: pc=0x00000ff0 r0=0x80002000 r1=0x00000000
          sp=0x97ffff00 lr=0x00000ff0 firmware returned to the assisted trampoline
```

Conclusion: the entry can be loaded and finishes execution, exiting normally through the halt window; but it is a **called function**, not
a reset. Without assistance, the first run will `push` to `0xFFFFFFF0..0xFFFFFFFC` and jump back to 0;
this negative result is saved in `docs/findings.md` §11.

`--gdb` mode has another record (`runs/20261105-075746/`):

```
snapshot.entry_pc = 0x9027d52c
snapshot.entry_ok = true
snapshot.cpsr     = 0x400001d3   (SVC, A/I/F masked, Z set)
stop.kind         = connection-closed   (guest 自行退出，RSP 断开)
```

### M0-neg — Negative control

Run once with `-machine entry=0x90000000` (true reset), and record where it stops/crashes.
This control is used to prove that "`0x9027D52C` is more like an entry point than the vector literal", rather than treating an exception as success.

### M1 — First MMIO sequence

Command:

```powershell
python tools/run.py --payload ... --flash ... --timeout 10
```

Look at `session.json.mmio.by_address`:

- Sort the top 10 addresses by count, and record `addr / rw / count / first_pc`;
- Compare against the UART candidates in `docs/findings.md` §6: check whether `0x80005010..14` appears;
- Compare against `0x1E000000` (MPCore): check whether it appears; if a different address appears, note it,
  and change `D750_MPCORE_BASE` to that address in the next round.

Pass criteria: obtain at least one **reproducible** address sequence, and the sequences from two runs are identical
(with single-threaded TCG and no external input, they should be identical).

**Current result**: `mmio_events=0`. This entry segment only performs initialization within RAM (writing the vector slot at `0x0`
and writing the stack), without reaching any peripherals. So the prerequisite work for M1 is not to add devices, but first to find
the caller/next stage; otherwise the catch-all has nothing to record.

### M2 — UART output

Pass criteria: `session.json.uart.bytes > 0`, and `uart.tail` is readable text or a stable
binary prefix.

**Current result**: `uart.bytes=0`; the UART path has not been reached yet. This is consistent with M1's "the entry does not reach peripherals"
and is not a UART model failure.

If `uart.bytes == 0` but there are many `d750-uart: rd +0x11` entries in `qemu.log`:

- This means the address is right but the status bit is wrong. Record the return values of the read sequence (currently `0x03`),
  change the status values in `d750_uart_read()` in `nikon-d750-lab.c`, or
  add a "set TX-done after writing data" state machine in `d750_uart_write()`;
- Do not change the status to `0xFF` just to "make it output" and declare success—that only fools the polling.

### M3 — Add the first device

Fixed procedure:

1. Run with `--strict` to get the first unmodeled access (address, width, direction, PC);
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

## 2. Evaluation rules

- A run without `session.json` does not count as evidence;
- A run without a recorded command line and SHA-256 of payload/flash does not count as evidence;
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
├── command.json    精确 argv、entry、是否 GDB
├── uart.log         guest 串口原始字节
├── qemu.log         -d guest_errors 的诊断（含 d750-probe/d750-uart）
└── session.json     汇总：exit、timed_out、uart、mmio、snapshot
```

These files may contain firmware behavior/paths; **do not** publish them directly; before publication, review them separately according to z7-qemu's publication process.

## 5. What counts as "done"

The completion definition for this prototype is: **M0 passes, M1 obtains a stable sequence, M2 has at least one explainable output
or a clear "status-bit assumption is wrong" conclusion, and M3 adds at least one device without regression**.
It does not include UI, shooting, or the image pipeline; those are work for subsequent profiles, and should not be claimed in this prototype's
README.
