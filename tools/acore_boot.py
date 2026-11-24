#!/usr/bin/env python3
"""Host-assisted A-core boot run for the D750 prototype.

This is a diagnostic fixture, not a reconstruction of the boot ROM.  It:

  1. starts the real reset path at 0x9027D524 with the Nikon-Patch layout
     (payload base 0x90020000);
  2. supplies the B8000000 IRAM bank and the A2/A120/A161/A300/AE/A340
     register-file stubs;
  3. runs to the wait at 0x1000E24C, clears the shared boot flag at
     0x100A6704, and continues;
  4. records the final PC/registers and the QEMU/UART logs.

The guest firmware file is never modified.
"""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from probe import RSPClient  # noqa: E402

WAIT_PC = 0x1000E24C
FLAG_ADDR = 0x100A6704


def wait_port(port: int, timeout: float) -> None:
    end = time.time() + timeout
    while time.time() < end:
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=0.5)
            s.close()
            return
        except OSError:
            time.sleep(0.1)
    raise TimeoutError(f"gdbstub on port {port} did not come up")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--qemu", required=True)
    ap.add_argument("--payload", required=True)
    ap.add_argument("--out", default="runs/acore-boot")
    ap.add_argument("--seconds", type=float, default=5.0)
    ap.add_argument("--gdb-port", type=int, default=1234)
    ap.add_argument("--plugin", help="optional QEMU TCG plugin (.so)")
    ap.add_argument("--vector-fix", action="store_true",
                    help="install the minimal SVC-return vector table "
                         "(experimental; changes the observed path)")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    qlog = out / "qemu.log"
    ulog = out / "uart.log"
    for p in (qlog, ulog):
        if p.exists():
            p.unlink()

    machine = ("nikon-d750,boot-mode=entry,entry=0x9027d524,"
               "payload-base=0x90020000,aux2-base=0xB8000000,"
               "aux2-size=0x40000,io-stub=on")
    if args.vector_fix:
        machine += ",vector-fix=on"
    cmd = [
        args.qemu,
        "-M", machine,
        "-cpu", "cortex-a9", "-m", "128M",
        "-display", "none", "-monitor", "none",
        "-serial", f"file:{ulog}",
        "-S", "-gdb", f"tcp::{args.gdb_port}",
        "-D", str(qlog), "-d", "guest_errors,plugin" if args.plugin
        else "guest_errors",
        "-no-reboot", "-nic", "none",
        "-kernel", args.payload,
    ]
    if args.plugin:
        cmd += ["-plugin", str(Path(args.plugin).resolve())]
    (out / "command.json").write_text(
        json.dumps({"argv": cmd, "wait_pc": hex(WAIT_PC),
                    "flag_addr": hex(FLAG_ADDR)}, indent=2) + "\n",
        encoding="utf-8")

    p = subprocess.Popen(cmd)
    try:
        wait_port(args.gdb_port, 10)
        c = RSPClient(port=args.gdb_port)
        c.set_breakpoint(WAIT_PC)
        stop = c.continue_(10)
        regs = c.read_registers()
        reached_wait = regs["pc"] == WAIT_PC
        if reached_wait:
            flag_before = c.read_memory(FLAG_ADDR, 4).hex()
            c.write_memory(FLAG_ADDR, b"\x00\x00\x00\x00")
            flag_after = c.read_memory(FLAG_ADDR, 4).hex()
            c.clear_breakpoint(WAIT_PC)
            stop = c.continue_(args.seconds)
        else:
            flag_before = c.read_memory(FLAG_ADDR, 4).hex()
            flag_after = flag_before
            c.clear_breakpoint(WAIT_PC)
            print(f"wait 0x{WAIT_PC:08x} not reached: "
                  f"pc=0x{regs['pc']:08x} stop={stop.kind}/{stop.signal}")
        regs = c.read_registers()
        pc = regs["pc"]
        mem = c.read_memory(pc, 32).hex()

        doc = {
            "kind": "host-assisted-acore-boot",
            "payload": str(Path(args.payload).resolve()),
            "machine": "nikon-d750",
            "entry": "0x9027d524",
            "payload_base": "0x90020000",
            "fixtures": {
                "iram": "0xB8000000/256K",
                "io_stub": ["A2", "A120", "A161", "A300", "AD", "AE", "A340"],
                "vector_fix": ("payload+0 SVC-return table"
                               if args.vector_fix else "off (real handler)"),
                "flag_zero": hex(FLAG_ADDR),
            },
            "wait": {"pc": hex(WAIT_PC), "reached": reached_wait,
                     "flag_before": flag_before, "flag_after": flag_after},
            "final": {
                "pc": hex(pc),
                "lr": hex(regs["lr"]),
                "sp": hex(regs["sp"]),
                "cpsr": hex(regs["cpsr"]),
                "bytes": mem,
            },
            "uart_bytes": ulog.stat().st_size if ulog.exists() else 0,
            "status": "running" if stop.signal == 2 else "stopped",
        }
        (out / "session.json").write_text(
            json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(doc, indent=2))
        return 0
    finally:
        p.terminate()
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()


if __name__ == "__main__":
    raise SystemExit(main())
