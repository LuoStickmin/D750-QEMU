# SPDX-License-Identifier: GPL-2.0-or-later
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

import fwscan  # noqa: E402

BASE = 0x90000000
ENTRY = 0x9027D52C


def make_main(size: int = 0x27D600) -> bytes:
    img = bytearray(size)
    for i in range(8):
        struct.pack_into("<I", img, i * 4, 0xE59FF018)
    literals = [BASE + 0x400, BASE + 0x500, BASE + 0x600, BASE + 0x700,
                BASE + 0x710, 0, 0, BASE + 0x720]
    for i, value in enumerate(literals):
        struct.pack_into("<I", img, 0x20 + i * 4, value)
    struct.pack_into("<I", img, 0x400, 0xE92D4000)   # push {lr}
    struct.pack_into("<I", img, 0x500, 0xE52D0004)   # str lr, [sp, #-4]!
    struct.pack_into("<I", img, 0x27D52C, 0xE3500002)  # cmp r0, #2
    struct.pack_into("<I", img, 0x800, 0x90020000)     # page-table literal
    struct.pack_into("<I", img, 0x804, ENTRY)          # entry literal
    struct.pack_into("<I", img, 0x808, 0x10001000)     # flash reference
    return bytes(img)


class VectorTests(unittest.TestCase):
    def test_vector_table_and_literals(self):
        img = make_main()
        vt = fwscan.vector_table(img, BASE)
        self.assertTrue(vt["present"])
        self.assertEqual(vt["ldr_pc_entries"], 8)
        self.assertEqual(vt["vectors"][0]["literal_addr"], BASE + 0x400)

    def test_target_classification(self):
        img = make_main()
        code = fwscan.check_target(img, BASE + 0x400, BASE)
        self.assertTrue(code["mapped"])
        self.assertTrue(code["looks_like_arm_code"])
        data = fwscan.check_target(img, 0x1041D9A8, BASE)
        self.assertFalse(data["mapped"])

    def test_profile_scan_is_consistent(self):
        with temp_dir() as td:
            main = Path(td) / "b1010.bin"
            flash = Path(td) / "a1010.bin"
            main.write_bytes(make_main())
            flash_img = bytearray(0x2000)
            struct.pack_into("<I", flash_img, 0x100, 0xE92D4000)
            flash.write_bytes(bytes(flash_img))
            report = fwscan.build_report(main, flash, BASE)
        self.assertEqual(report["verdict"], "profile-consistent", report["checks"])
        names = {c["name"] for c in report["checks"]}
        self.assertIn("page_table_literal_present", names)
        self.assertIn("flash_refs_fit_flash_image", names)
        self.assertAlmostEqual(report["main"]["entropy_bits"] >= 0.0, True)

    def test_vector_reset_data_is_reported(self):
        img = bytearray(make_main())
        struct.pack_into("<I", img, 0x20, 0x9027D524)
        struct.pack_into("<I", img, 0x27D524, 0x1041D9A8)
        vt = fwscan.vector_table(bytes(img), BASE)
        check = fwscan.check_target(bytes(img), vt["vectors"][0]["literal_addr"], BASE)
        self.assertFalse(check["looks_like_arm_code"])


class CensusTests(unittest.TestCase):
    def test_pointer_census(self):
        arr = fwscan.words(struct.pack("<4I", 0x10000000, 0x90001000,
                                       0x80000010, 0x12345678))
        census = fwscan.pointer_census(arr)
        self.assertEqual(census["flash_0x10000000"], 1)
        self.assertEqual(census["ram_0x90000000"], 1)
        self.assertEqual(census["periph_0x80000000"], 1)

    def test_mmu_site_detection(self):
        arr = fwscan.words(struct.pack("<2I", 0xEE010F10, 0xE1A00000))
        self.assertEqual(fwscan.mmu_sites(arr), ["0x000000"])


if __name__ == "__main__":
    unittest.main()
