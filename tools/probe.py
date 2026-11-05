# SPDX-License-Identifier: GPL-2.0-or-later
"""Minimal GDB remote-serial-protocol client for the D750 lab machine.

Only the subset needed for boot validation is implemented:

  * read registers and memory;
  * set/clear hardware breakpoints (the payload can live in a ROM window);
  * continue, interrupt, single-step;
  * read the stop reason.

It deliberately does *not* implement the full RSP, thread migration or
calling into the guest.  Use gdb-multiarch for interactive debugging.

The client is also exercised against a stock QEMU ``-M virt`` instance in
the test suite, so a protocol regression is visible without the custom
machine.
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from dataclasses import dataclass


class RSPError(RuntimeError):
    pass


def checksum(data: bytes) -> bytes:
    return f"{sum(data) & 0xFF:02x}".encode()


def encode_packet(data: bytes) -> bytes:
    if isinstance(data, str):
        data = data.encode()
    return b"$" + data + b"#" + checksum(data)


def decode_registers(raw: str) -> dict[str, int]:
    """Decode an ARM 'g' payload (little-endian 32-bit register slots)."""
    if len(raw) % 8:
        raise RSPError(f"unexpected register payload length {len(raw)}")
    values = [int.from_bytes(bytes.fromhex(raw[i:i + 8]), "little")
              for i in range(0, len(raw), 8)]
    names = [f"r{i}" for i in range(13)] + ["sp", "lr", "pc", "cpsr"]
    out: dict[str, int] = {}
    for i, name in enumerate(names):
        if i < len(values):
            out[name] = values[i]
    if "cpsr" not in out and values:
        out["cpsr"] = values[-1]
    return out


@dataclass
class StopReply:
    kind: str
    signal: int | None = None
    thread: str | None = None
    raw: str = ""


class RSPClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 1234,
                 timeout: float = 5.0):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(timeout)
        self.timeout = timeout
        self._buf = b""
        self.features: dict[str, str] = {}
        self._handshake()

    # -- low level ---------------------------------------------------
    def _read_byte(self) -> bytes:
        while not self._buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise RSPError("connection closed by QEMU")
            self._buf += chunk
        b, self._buf = self._buf[:1], self._buf[1:]
        return b

    def _read_packet(self) -> bytes:
        while True:
            b = self._read_byte()
            if b == b"$":
                break
            if b in (b"+", b"-"):
                continue
        data = bytearray()
        while True:
            b = self._read_byte()
            if b == b"#":
                break
            data += b
        got = self._read_byte() + self._read_byte()
        if got.lower() != checksum(bytes(data)):
            self.sock.sendall(b"-")
            raise RSPError(f"bad checksum: {got!r} != {checksum(bytes(data))!r}")
        self.sock.sendall(b"+")
        return bytes(data)

    def command(self, data: str | bytes, timeout: float | None = None) -> bytes:
        if isinstance(data, str):
            data = data.encode()
        self.sock.settimeout(timeout or self.timeout)
        self.sock.sendall(encode_packet(data))
        ack = self._read_byte()
        if ack != b"+":
            raise RSPError(f"QEMU rejected packet {data!r} (ack {ack!r})")
        return self._read_packet()

    def _handshake(self) -> None:
        reply = self.command("qSupported:multiprocess+;swbreak+;hwbreak+")
        for item in reply.decode(errors="replace").split(";"):
            if "=" in item:
                k, v = item.split("=", 1)
                self.features[k] = v
        self.handle = self.command("qAttached").decode(errors="replace")

    # -- registers ---------------------------------------------------
    def read_registers(self) -> dict[str, int]:
        return decode_registers(self.command("g").decode())

    def read_memory(self, addr: int, length: int) -> bytes:
        out = bytearray()
        cur = addr
        left = length
        while left > 0:
            n = min(left, 0x400)
            reply = self.command(f"m{cur:x},{n:x}")
            if reply.startswith(b"E"):
                raise RSPError(f"memory read failed at 0x{cur:08x}: {reply!r}")
            out += bytes.fromhex(reply.decode())
            cur += n
            left -= n
        return bytes(out)

    def write_memory(self, addr: int, data: bytes, chunk: int = 0x1000) -> None:
        """Write memory in chunks that fit QEMU's RSP PacketSize."""
        for off in range(0, len(data), chunk):
            part = data[off:off + chunk]
            reply = self.command(f"M{addr + off:x},{len(part):x}:{part.hex()}")
            if reply != b"OK":
                raise RSPError(
                    f"memory write failed at 0x{addr + off:08x}: {reply!r}")

    # -- execution ---------------------------------------------------
    def stop_reply(self, timeout: float | None = None) -> StopReply:
        self.sock.settimeout(timeout or self.timeout)
        raw = self._read_packet().decode(errors="replace")
        if raw.startswith("T"):
            fields = dict(
                part.split(":", 1) for part in raw[1:].split(";") if ":" in part
            )
            return StopReply("T", int(raw[1:3], 16),
                             fields.get("thread"), raw)
        return StopReply(raw[:1] or "?", None, None, raw)

    def continue_(self, seconds: float) -> StopReply:
        self.sock.settimeout(self.timeout)
        self.sock.sendall(encode_packet(b"c"))
        ack = self._read_byte()
        if ack != b"+":
            raise RSPError(f"continue not acknowledged ({ack!r})")
        try:
            return self.stop_reply(timeout=seconds)
        except socket.timeout:
            self.sock.sendall(b"\x03")
            return self.stop_reply(timeout=self.timeout)

    def step(self) -> StopReply:
        self.sock.settimeout(self.timeout)
        self.sock.sendall(encode_packet(b"s"))
        ack = self._read_byte()
        if ack != b"+":
            raise RSPError(f"step not acknowledged ({ack!r})")
        return self.stop_reply(timeout=self.timeout)

    def set_breakpoint(self, addr: int, kind: int = 1) -> None:
        """kind 1 = hardware breakpoint, 0 = software."""
        reply = self.command(f"Z{kind},{addr:x},4")
        if reply != b"OK":
            raise RSPError(f"breakpoint at 0x{addr:08x} rejected: {reply!r}")

    def clear_breakpoint(self, addr: int, kind: int = 1) -> None:
        self.command(f"z{kind},{addr:x},4")

    def detach(self) -> None:
        try:
            self.command("D")
        finally:
            self.close()

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass

    # -- convenience -------------------------------------------------
    def wait_for_pc(self, addr: int, seconds: float) -> StopReply:
        self.set_breakpoint(addr)
        stop = self.continue_(seconds)
        regs = self.read_registers()
        if regs.get("pc") != addr:
            raise RSPError(
                f"expected PC 0x{addr:08x}, stopped at 0x{regs.get('pc', 0):08x} "
                f"({stop.kind}{stop.signal if stop.signal is not None else ''})"
            )
        return stop


def _parse_addr(text: str) -> int:
    return int(text, 0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--regs", action="store_true")
    parser.add_argument("--mem", help="ADDR:LEN")
    parser.add_argument("--break-at", type=_parse_addr, action="append",
                        default=[], help="hardware breakpoint address")
    parser.add_argument("--continue", dest="run_seconds", type=float,
                        default=0.0)
    parser.add_argument("--step", type=int, default=0)
    parser.add_argument("--expect-pc", type=_parse_addr)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    client = RSPClient(args.host, args.port)
    result: dict = {"features": client.features}
    try:
        for addr in args.break_at:
            client.set_breakpoint(addr)
        if args.expect_pc is not None:
            client.wait_for_pc(args.expect_pc, args.run_seconds or 5.0)
        elif args.step:
            for _ in range(args.step):
                client.step()
        elif args.run_seconds:
            client.continue_(args.run_seconds)
        regs = client.read_registers()
        result["registers"] = {k: f"0x{v:08x}" for k, v in regs.items()}
        result["pc"] = f"0x{regs.get('pc', 0):08x}"
        if args.mem:
            addr_s, len_s = args.mem.split(":")
            data = client.read_memory(int(addr_s, 0), int(len_s, 0))
            result["memory"] = {"addr": addr_s, "hex": data.hex()}
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            for k in ("r0", "r1", "sp", "lr", "pc", "cpsr"):
                if k in regs:
                    print(f"{k:6s} 0x{regs[k]:08x}")
            if "memory" in result:
                print(f"mem    {result['memory']['hex']}")
    finally:
        client.detach()
    return 0


if __name__ == "__main__":
    sys.exit(main())
