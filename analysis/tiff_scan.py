#!/usr/bin/env python3
"""Read-only TIFF evidence scanner for Nikon EXPEED firmware modules.

This does not modify any firmware.  It answers one question: does a module
contain a TIFF *image writer* (menu label + encoder), or only the generic
filename / EXIF-TIFF metadata strings that the whole EXPEED family shares?

Usage:
    python tiff_scan.py
    python tiff_scan.py --module path\to\b1010_115a.bin
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DEFAULT_FILES = {
    "D750 b1010_115a": r"C:\Users\23795\Downloads\DSLR\D750_0115.dec.modules\b1010_115a.bin",
    "D810 b920_114": r"C:\Users\23795\Downloads\DSLR\D810_0114.bin.modules\b920_114.bin",
    "D850 b1330_131": r"C:\Users\23795\Downloads\DSLR\D850_0131.bin.modules\b1330_131.bin",
    "D5 b870_150": r"C:\Users\23795\Downloads\DSLR\D5__0150.bin.modules\b870_150.bin",
}

# Menu labels that only exist on models with real TIFF (RGB) capture.
TIFF_MENU_LABELS = [
    "TIFF (RGB)",
    "TIFF(RGB)",
    "JPEG/TIFF",
]

D750_QUALITY_GROUP = 0x756CC8  # English packed image-quality labels


def find_all(data: bytes, needle: bytes) -> list[int]:
    out: list[int] = []
    pos = 0
    while True:
        pos = data.find(needle, pos)
        if pos < 0:
            return out
        out.append(pos)
        pos += 1


def utf16_le(s: str) -> bytes:
    return s.encode("utf-16le")


def show(data: bytes, off: int, width: int = 120) -> str:
    chunk = data[max(0, off - 24) : off + width]
    return "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)


def scan(path: Path) -> dict:
    data = path.read_bytes()
    result: dict = {
        "path": str(path),
        "size": len(data),
        "ascii_TIF": find_all(data, b"TIF"),
        "ascii_TIFF": find_all(data, b"TIFF"),
        "u16_TIFF": find_all(data, utf16_le("TIFF")),
        "u16_TIF": find_all(data, utf16_le("TIF")),
        "u16_JPEG_TIFF": find_all(data, utf16_le("JPEG/TIFF")),
        "menu_labels": {
            label: find_all(data, utf16_le(label)) for label in TIFF_MENU_LABELS
        },
        "jfif": find_all(data, b"JFIF"),
        "tiff_header": find_all(data, b"II*\x00"),
    }
    # Real ASCII strings containing TIF, with context.
    hits: list[tuple[int, str]] = []
    for m in re.finditer(rb"[\x20-\x7e]{4,}", data):
        s = m.group()
        if b"tif" in s.lower():
            hits.append((m.start(), s.decode("ascii", "replace")))
    result["ascii_tif_strings"] = hits
    return result


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--module", action="append", default=[])
    parser.add_argument("--quality-group", action="store_true")
    args = parser.parse_args(argv)

    files = dict(DEFAULT_FILES)
    if args.module:
        files = {Path(p).name: p for p in args.module}

    print("TIFF evidence scan (read-only)\n")
    for name, raw in files.items():
        path = Path(raw)
        if not path.exists():
            print(f"== {name}: MISSING {path}")
            continue
        r = scan(path)
        print(f"== {name}  size={r['size']:,}  {path}")
        print(
            "   ASCII 'TIF'={} 'TIFF'={}  UTF16 'TIFF'={} 'TIF'={} 'JPEG/TIFF'={}".format(
                len(r["ascii_TIF"]),
                len(r["ascii_TIFF"]),
                len(r["u16_TIFF"]),
                len(r["u16_TIF"]),
                len(r["u16_JPEG_TIFF"]),
            )
        )
        for label, offs in r["menu_labels"].items():
            print(f"   UTF16 {label!r}: {len(offs)} {[hex(x) for x in offs[:4]]}")
        print(f"   'II*' header bytes: {len(r['tiff_header'])}; JFIF: {len(r['jfif'])}")
        real = [
            (off, s)
            for off, s in r["ascii_tif_strings"]
            if "notify" not in s.lower() and s not in {"TifO"}
        ]
        print(f"   ASCII strings containing TIF: {len(real)}")
        for off, s in real[:12]:
            print(f"     {off:#x}  {s!r}")
        print()

    if args.quality_group:
        path = Path(DEFAULT_FILES["D750 b1010_115a"])
        data = path.read_bytes()
        print(f"D750 English image-quality group at {D750_QUALITY_GROUP:#x}:")
        text = data[D750_QUALITY_GROUP : D750_QUALITY_GROUP + 0x200].decode(
            "utf-16le", "replace"
        )
        print(repr(text))
        print()
        print("D750 menu labels contain 'TIFF':", "TIFF" in text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
