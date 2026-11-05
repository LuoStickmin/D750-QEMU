# SPDX-License-Identifier: GPL-2.0-or-later
import json
import struct
import sys
import tempfile
import sys
import unittest
from tmputil import temp_dir
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
TMPBASE = PROJECT / ".test-tmp"
TMPBASE.mkdir(exist_ok=True)
sys.path.insert(0, str(PROJECT / "tools"))

import probe  # noqa: E402
import run as run_mod  # noqa: E402


class PacketTests(unittest.TestCase):
    def test_checksum_and_encode(self):
        self.assertEqual(probe.checksum(b"g"), b"67")
        self.assertEqual(probe.encode_packet(b"g"), b"$g#67")

    def test_decode_arm_registers_is_little_endian(self):
        values = list(range(17))
        values[15] = 0x9027D52C
        values[16] = 0x400001D3
        values[0] = 0x11223344
        raw = struct.pack("<17I", *values).hex()
        regs = probe.decode_registers(raw)
        self.assertEqual(regs["r0"], 0x11223344)
        self.assertEqual(regs["pc"], 0x9027D52C)
        self.assertEqual(regs["cpsr"], 0x400001D3)
        self.assertEqual(regs["sp"], 13)

    def test_bad_payload_length(self):
        with self.assertRaises(probe.RSPError):
            probe.decode_registers("0011")


class SessionParsingTests(unittest.TestCase):
    def test_probe_log_summary(self):
        with temp_dir() as td:
            log = Path(td) / "qemu.log"
            log.write_text(
                "d750-probe: pc=0x9027d000 rd addr=0x80005011 size=1"
                " (unmodelled read, returning 0)\n"
                "d750-probe: pc=0x9027d010 wr addr=0x80005011 size=1"
                " value=0x000000aa (unmodelled write)\n"
                "unrelated line\n", encoding="utf-8")
            summary = run_mod.summarize_probe_log(log)
        self.assertEqual(summary["events"], 2)
        self.assertEqual(len(summary["by_address"]), 2)
        self.assertEqual({r["rw"] for r in summary["by_address"]}, {"rd", "wr"})

    def test_uart_summary(self):
        with temp_dir() as td:
            uart = Path(td) / "uart.log"
            uart.write_bytes(b"HELLO")
            summary = run_mod.summarize_uart(uart)
        self.assertEqual(summary["bytes"], 5)
        self.assertEqual(summary["tail"], "HELLO")

    def test_halt_summary(self):
        with temp_dir() as td:
            log = Path(td) / "qemu.log"
            log.write_text(
                "d750-halt: pc=0x00000ff0 r0=0x80002000 r1=0x00000000"
                " sp=0x97ffff00 lr=0x00000ff0 firmware returned to the"
                " assisted trampoline\n", encoding="utf-8")
            halt = run_mod.summarize_halt(log)
        self.assertIsNotNone(halt)
        self.assertEqual(halt["r0"], "0x80002000")
        self.assertEqual(halt["sp"], "0x97ffff00")

    def test_lcd_summary(self):
        with temp_dir() as td:
            log = Path(td) / "qemu.log"
            log.write_text(
                "d750-lcd: dumped 320x240 (argb8888, stride 1280)"
                " from 0x92000000 to /tmp/lcd.ppm\n", encoding="utf-8")
            lcd = run_mod.summarize_lcd(log)
            empty = Path(td) / "empty.log"
            empty.write_text("nothing\n", encoding="utf-8")
            self.assertIsNone(run_mod.summarize_lcd(empty))
        self.assertEqual(lcd["width"], 320)
        self.assertEqual(lcd["height"], 240)
        self.assertEqual(lcd["format"], "argb8888")
        self.assertEqual(lcd["base"], "0x92000000")


class CommandTests(unittest.TestCase):
    def test_machine_and_loader_arguments(self):
        args = run_mod.parse_args([
            "--payload", "b1010.bin", "--flash", "a1010.bin",
            "--entry", "0x9027d52c", "--strict", "--gdb",
        ])
        cmd = run_mod.build_command(Path("qemu-system-arm"), args,
                                    Path("run"), 4321)
        text = " ".join(cmd)
        self.assertIn("-M nikon-d750,entry=0x9027d52c,strict=on", text)
        self.assertIn("-kernel", cmd)
        self.assertIn("-bios", cmd)
        self.assertIn("-S", cmd)
        self.assertIn("tcp:127.0.0.1:4321", text)
        self.assertNotIn("\\", cmd[cmd.index("-serial") + 1])

    def test_default_command_has_no_entry_override(self):
        args = run_mod.parse_args(["--payload", "b1010.bin"])
        cmd = run_mod.build_command(Path("qemu-system-arm"), args,
                                    Path("run"), None)
        self.assertIn("nikon-d750", cmd)
        self.assertNotIn("-S", cmd)


STOCK_QEMU = Path(r"C:\Program Files\qemu\qemu-system-arm.exe")


@unittest.skipUnless(STOCK_QEMU.is_file(), "stock QEMU not installed")
class InstalledQemuTests(unittest.TestCase):
    def test_stock_binary_has_no_nikon_machine(self):
        ok, machines = run_mod.machine_supported(STOCK_QEMU)
        self.assertFalse(ok)
        self.assertIn("virt", machines)
        self.assertNotIn("nikon-d750", machines)


class ManifestTests(unittest.TestCase):
    manifest = PROJECT / "analysis" / "d750-0115.json"

    @unittest.skipUnless(manifest.is_file(), "run tools/fwscan.py first")
    def test_d750_manifest(self):
        data = json.loads(self.manifest.read_text(encoding="utf-8"))
        self.assertEqual(data["main"]["size"], 20324448)
        self.assertEqual(data["main"]["vector_table"]["ldr_pc_entries"], 6)
        self.assertEqual(data["profile"]["entry"], 0x9027D52C)
        self.assertTrue(data["main"]["entry_literal_count"] >= 1)
        self.assertTrue(data["main"]["page_table_literal_count"] >= 1)
        names = {c["name"]: c["ok"] for c in data["checks"]}
        self.assertTrue(names["vector_table_shape"])
        self.assertFalse(names["vector_reset_points_at_code"])


if __name__ == "__main__":
    unittest.main()
