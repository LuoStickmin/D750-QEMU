# SPDX-License-Identifier: GPL-2.0-or-later
import sys
import tempfile
import sys
import unittest
from tmputil import temp_dir
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
TMPBASE = PROJECT / ".test-tmp"
TMPBASE.mkdir(exist_ok=True)
sys.path.insert(0, str(PROJECT / "qemu"))

import prepare_source  # noqa: E402


def make_tree(root: Path, version: str) -> None:
    (root / "hw" / "arm").mkdir(parents=True)
    (root / "configs" / "devices" / "arm-softmmu").mkdir(parents=True)
    (root / "VERSION").write_text(version + "\n", encoding="utf-8")
    (root / "hw" / "arm" / "meson.build").write_text("arm_ss = ss.source_set()\n",
                                                     encoding="utf-8")
    (root / "hw" / "arm" / "Kconfig").write_text("config ARM_VIRT\n    bool\n",
                                                 encoding="utf-8")
    (root / "configs" / "devices" / "arm-softmmu" / "default.mak").write_text(
        "CONFIG_ARM_VIRT=y\n", encoding="utf-8")


class PrepareTests(unittest.TestCase):
    def test_overlay_is_idempotent_for_11_1(self):
        with temp_dir() as td:
            root = Path(td)
            make_tree(root, "11.1.0")
            first = prepare_source.prepare(root)
            second = prepare_source.prepare(root)
            self.assertEqual(first["chardev_type"], "CharFrontend")
            self.assertIn("hw/arm/nikon-d750-lab.c", first["changed"])
            self.assertEqual(second["changed"], {})
            board = (root / "hw" / "arm" / "nikon-d750-lab.c").read_text()
            self.assertIn("CharFrontend chr;", board)
            meson = (root / "hw" / "arm" / "meson.build").read_text()
            self.assertEqual(meson.count("CONFIG_NIKON_D750_LAB"), 1)
            kconfig = (root / "hw" / "arm" / "Kconfig").read_text()
            self.assertEqual(kconfig.count("config NIKON_D750_LAB"), 1)
            mak = (root / "configs" / "devices" / "arm-softmmu" / "default.mak").read_text()
            self.assertIn("CONFIG_NIKON_D750_LAB=y", mak)

    def test_10_x_uses_legacy_chardev_type(self):
        with temp_dir() as td:
            root = Path(td)
            make_tree(root, "10.2.4")
            summary = prepare_source.prepare(root)
            self.assertEqual(summary["chardev_type"], "CharBackend")
            board = (root / "hw" / "arm" / "nikon-d750-lab.c").read_text()
            self.assertIn("CharBackend chr;", board)
            self.assertNotIn("CharFrontend", board)

    def test_unsupported_version_is_rejected(self):
        with temp_dir() as td:
            root = Path(td)
            make_tree(root, "9.2.0")
            with self.assertRaises(SystemExit):
                prepare_source.prepare(root)


if __name__ == "__main__":
    unittest.main()
