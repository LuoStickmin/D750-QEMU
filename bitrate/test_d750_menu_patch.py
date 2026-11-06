# SPDX-License-Identifier: GPL-2.0-or-later
import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import d750_menu_patch as patch  # noqa: E402

MODULE = Path(os.environ.get(
    "D750_MODULE",
    ROOT.parent / "D750_0115.dec.modules" / "b1010_115a.bin",
))


@unittest.skipUnless(MODULE.is_file(),
                     "provide D750_MODULE or ../D750_0115.dec.modules/b1010_115a.bin")
class D750MenuPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = MODULE.read_bytes()

    def test_stock_table_and_labels(self):
        patch.check_stock(self.module)
        self.assertEqual(patch.read_rows(self.module), list(patch.STOCK_ROWS))

    def test_patch_changes_only_expected_regions(self):
        out, table_changes, label_changes = patch.patch_module(self.module)
        self.assertEqual(len(out), len(self.module))
        self.assertEqual(len(table_changes), 9)
        self.assertEqual(len(label_changes), 4)
        patch.verify_patch(self.module, out, table_changes, label_changes)
        self.assertEqual(patch.read_rows(out), list(patch.TARGET_ROWS))

    def test_neighbour_labels_are_intact(self):
        out, _, _ = patch.patch_module(self.module)
        for off, text in patch.NEIGHBOURS:
            self.assertEqual(out[off:off + len(text) * 2], text.encode("utf-16le"))

    def test_wrong_label_is_rejected(self):
        bad = bytearray(self.module)
        off = patch.LABELS[0][1]
        bad[off:off + 2] = b"X\x00"
        with self.assertRaises(ValueError):
            patch.check_stock(bytes(bad))

    def test_length_change_is_rejected(self):
        for name, off, old, new in patch.LABELS:
            self.assertEqual(len(old), len(new), name)


if __name__ == "__main__":
    unittest.main()
