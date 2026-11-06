#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""D750 menu-visible 64 Mbps / Stock bit-rate variant.

This does **not** add a third Movie quality item.  It reuses the existing two
items and changes their labels in place (same UTF-16 length, so later labels
keep their offsets):

    High quality -> "64 Mbps HQ  "  (English, 12 chars)
    Normal       -> "Stock "        (English, 6 chars)
    高品质        -> "64M"           (Simplified Chinese, 3 chars)
    标准          -> "原厂"           (Simplified Chinese, 2 chars)

The first item uses the five 1080p HQ rows at 64/60 Mbps.  The second item
uses the four 1080p NQ rows, raised to the stock HQ values:

    NQ row 2 (60p): 24/20 -> 42/35
    NQ row 4 (50p): 24/20 -> 42/35
    NQ row 6 (25p): 12/10 -> 24/20
    NQ row 8 (24p): 12/10 -> 24/20

All other rows, both other modules, and all other label bytes are untouched.
The tool refuses to patch unless the stock table and all four labels match the
expected D750_0115 bytes, so it cannot silently corrupt another revision.

Usage:
    python d750_menu_patch.py --module b1010_115a.bin --out b1010_115a.menu64.bin
    python d750_menu_patch.py --module b1010_115a.bin --check
"""

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

TABLE_ENTRY1 = 0x2AA9AC
ENTRY_STRIDE = 0x1C
HQ_INDICES = (0, 2, 4, 6, 8)
NQ_INDICES = (1, 3, 5, 7)

STOCK_ROWS = (
    (42_000_000, 35_000_000),
    (24_000_000, 20_000_000),
    (42_000_000, 35_000_000),
    (24_000_000, 20_000_000),
    (24_000_000, 20_000_000),
    (12_000_000, 10_000_000),
    (24_000_000, 20_000_000),
    (12_000_000, 10_000_000),
    (24_000_000, 20_000_000),
)
TARGET_ROWS = (
    (64_000_000, 60_000_000),
    (42_000_000, 35_000_000),
    (64_000_000, 60_000_000),
    (42_000_000, 35_000_000),
    (64_000_000, 60_000_000),
    (24_000_000, 20_000_000),
    (64_000_000, 60_000_000),
    (24_000_000, 20_000_000),
    (64_000_000, 60_000_000),
)

# (name, offset, stock text, menu text).  UTF-16 code-unit lengths must match.
LABELS = (
    ("en_high", 0x757674, "High quality", "64 Mbps HQ  "),
    ("en_normal", 0x75768C, "Normal", "Stock "),
    ("zh_high", 0x8870E0, "高品质", "64M"),
    ("zh_normal", 0x8870E6, "标准", "原厂"),
)
NEIGHBOURS = (
    (0x75765A, "Movie quality"),
    (0x757698, "Microphone sensitivity"),
    (0x8870D8, "动画品质"),
    (0x8870EA, "麦克风灵敏度"),
)
MAX_RATE_FIELD = 0x04380780  # 70,780,800 bps ceiling of the 1080p group


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def parse_row(data, index):
    off = TABLE_ENTRY1 + index * ENTRY_STRIDE
    if off + ENTRY_STRIDE > len(data):
        raise ValueError("table row %d at 0x%X is outside the module"
                         % (index + 1, off))
    rate_a, rate_b, flag, ceiling, tb_num, tb_den, fps = struct.unpack(
        "<7I", data[off:off + ENTRY_STRIDE]
    )
    return {
        "row": index + 1,
        "offset": off,
        "rate_a": rate_a,
        "rate_b": rate_b,
        "flag": flag,
        "ceiling": ceiling,
        "tb_num": tb_num,
        "tb_den": tb_den,
        "fps_field": fps,
    }


def read_rows(data):
    return [(parse_row(data, i)["rate_a"], parse_row(data, i)["rate_b"])
            for i in range(9)]


def label_bytes(text):
    return text.encode("utf-16le")


def check_stock(data):
    rows = read_rows(data)
    if rows != list(STOCK_ROWS):
        raise ValueError(
            "the nine 1080p rows do not match D750_0115 stock values\n"
            "  expected %s\n  got      %s" % (STOCK_ROWS, rows)
        )
    for index in range(9):
        row = parse_row(data, index)
        if row["flag"] != 1:
            raise ValueError("row %d has flag %#x, expected 1"
                             % (row["row"], row["flag"]))
        if row["ceiling"] != MAX_RATE_FIELD:
            raise ValueError("row %d has ceiling %#x, expected %#x"
                             % (row["row"], row["ceiling"], MAX_RATE_FIELD))
    for name, off, old, new in LABELS:
        if len(old) != len(new):
            raise ValueError("label %s changes length: %r -> %r"
                             % (name, old, new))
        raw = label_bytes(old)
        if data[off:off + len(raw)] != raw:
            raise ValueError("label %s at 0x%X is not stock %r"
                             % (name, off, old))
    for off, text in NEIGHBOURS:
        raw = label_bytes(text)
        if data[off:off + len(raw)] != raw:
            raise ValueError("neighbouring label at 0x%X is not stock %r"
                             % (off, text))


def patch_module(data):
    check_stock(data)
    out = bytearray(data)
    table_changes = []
    for index, target in enumerate(TARGET_ROWS):
        row = parse_row(data, index)
        off = row["offset"]
        old = data[off:off + 8]
        out[off:off + 8] = struct.pack("<II", *target)
        table_changes.append({
            "row": index + 1,
            "offset": off,
            "old": list(struct.unpack("<II", old)),
            "new": list(target),
        })
    label_changes = []
    for name, off, old, new in LABELS:
        old_raw = label_bytes(old)
        new_raw = label_bytes(new)
        out[off:off + len(new_raw)] = new_raw
        label_changes.append({
            "name": name,
            "offset": off,
            "old": old,
            "new": new,
            "bytes": len(new_raw),
        })
    return bytes(out), table_changes, label_changes


def verify_patch(original, patched, table_changes, label_changes):
    if len(original) != len(patched):
        raise ValueError("module size changed: %d -> %d"
                         % (len(original), len(patched)))
    if read_rows(patched) != list(TARGET_ROWS):
        raise ValueError("patched rows do not read back as TARGET_ROWS")
    for index in NQ_INDICES:
        row = parse_row(patched, index)
        if (row["rate_a"], row["rate_b"]) != TARGET_ROWS[index]:
            raise ValueError("NQ row %d did not read back as %s"
                             % (row["row"], TARGET_ROWS[index]))
    for index in range(9, 22):
        a = original[TABLE_ENTRY1 + index * ENTRY_STRIDE:
                     TABLE_ENTRY1 + (index + 1) * ENTRY_STRIDE]
        b = patched[TABLE_ENTRY1 + index * ENTRY_STRIDE:
                    TABLE_ENTRY1 + (index + 1) * ENTRY_STRIDE]
        if a != b:
            raise ValueError("row %d outside the 1080p group changed"
                             % (index + 1))
    for name, off, old, new in LABELS:
        raw = label_bytes(new)
        if patched[off:off + len(raw)] != raw:
            raise ValueError("label %s did not read back" % name)
        if len(label_bytes(old)) != len(raw):
            raise ValueError("label %s changed length" % name)
    for off, text in NEIGHBOURS:
        raw = label_bytes(text)
        if patched[off:off + len(raw)] != raw:
            raise ValueError("neighbouring label at 0x%X changed" % off)
    allowed = set()
    for change in table_changes:
        allowed.update(range(change["offset"], change["offset"] + 8))
    for change in label_changes:
        allowed.update(range(change["offset"], change["offset"] + change["bytes"]))
    diffs = {i for i, (a, b) in enumerate(zip(original, patched)) if a != b}
    if not diffs.issubset(allowed):
        outside = sorted(diffs - allowed)
        raise ValueError("%d byte(s) changed outside table/labels; first 0x%X"
                         % (len(outside), outside[0]))
    if not diffs:
        raise ValueError("patch produced no changes")


def report(original, patched, table_changes, label_changes):
    return {
        "module": {
            "size": len(original),
            "sha256_stock": sha256(original),
            "sha256_patched": sha256(patched),
            "changed_bytes": sum(1 for a, b in zip(original, patched) if a != b),
        },
        "profile": "menu-visible 64 Mbps HQ / Stock (two existing items, not a third)",
        "table": {
            "entry1_offset": TABLE_ENTRY1,
            "stride": ENTRY_STRIDE,
            "hq_rows": [i + 1 for i in HQ_INDICES],
            "nq_rows": [i + 1 for i in NQ_INDICES],
            "target_rows": [{"row": i + 1, "a": a, "b": b}
                            for i, (a, b) in enumerate(TARGET_ROWS)],
        },
        "labels": label_changes,
        "table_changes": table_changes,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--module", required=True, help="extracted b1010_115a.bin")
    ap.add_argument("--out", help="patched module to write")
    ap.add_argument("--json", help="write a JSON report here")
    ap.add_argument("--check", action="store_true",
                    help="only validate stock table/labels")
    args = ap.parse_args(argv)

    data = Path(args.module).read_bytes()
    try:
        check_stock(data)
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

    if args.check:
        for i, (a, b) in enumerate(read_rows(data)):
            print("row %d  %10d / %10d" % (i + 1, a, b))
        for name, off, old, new in LABELS:
            print("label %-9s 0x%06X  %r -> %r" % (name, off, old, new))
        print("stock table/labels OK")
        return 0

    if not args.out:
        ap.error("--out is required unless --check is used")
    if Path(args.out).resolve() == Path(args.module).resolve():
        print("error: --out must not be the stock module", file=sys.stderr)
        return 2
    patched, table_changes, label_changes = patch_module(data)
    verify_patch(data, patched, table_changes, label_changes)
    Path(args.out).write_bytes(patched)
    doc = report(data, patched, table_changes, label_changes)
    doc["output"] = str(Path(args.out))
    if args.json:
        Path(args.json).write_text(
            json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
    print("stock   %s  %s" % (args.module, doc["module"]["sha256_stock"]))
    print("patched %s  %s" % (args.out, doc["module"]["sha256_patched"]))
    for c in label_changes:
        print("  label %-9s @0x%06X  %r -> %r"
              % (c["name"], c["offset"], c["old"], c["new"]))
    for c in table_changes:
        print("  row %d @0x%06X  %d/%d -> %d/%d"
              % (c["row"], c["offset"], c["old"][0], c["old"][1],
                 c["new"][0], c["new"][1]))
    print("changed bytes: %d" % doc["module"]["changed_bytes"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
