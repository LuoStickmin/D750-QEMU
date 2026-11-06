#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Regenerate or verify ``SHA256SUMS`` and the ``files`` list in ``MANIFEST.json``.

The repository ships a hash list, a machine-readable manifest and a release
binary.  Keeping the three in sync by hand is exactly the kind of step that
rots, so the list is generated from the working tree and checked in CI.

Usage:
    python tools/manifest.py --check    # verify (default; used by CI)
    python tools/manifest.py --write    # regenerate both files
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
EXCLUDE_DIRS = {".git", ".build", ".local", "runs", ".test-tmp", "__pycache__"}
EXCLUDE_FILES = {"SHA256SUMS", "MANIFEST.json", "binary/qemu-system-arm"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tracked_files(root: Path) -> list[Path]:
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in EXCLUDE_DIRS for part in rel.parts[:-1]):
            continue
        if rel.as_posix() in EXCLUDE_FILES or path.suffix == ".pyc":
            continue
        files.append(path)
    return files


def build_entries(root: Path) -> list[dict]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in tracked_files(root)
    ]


def write_text_lf(path: Path, text: str) -> None:
    """Write UTF-8 with LF endings on every platform (hashes must match CI)."""
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def write(root: Path) -> int:
    entries = build_entries(root)
    sums = "".join(f"{e['sha256']}  {e['path']}\n" for e in entries)
    write_text_lf(root / "SHA256SUMS", sums)

    manifest_path = root / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = entries
    manifest["generated"] = _dt.datetime.now().astimezone().isoformat(
        timespec="seconds")
    write_text_lf(manifest_path,
                  json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote SHA256SUMS and MANIFEST.json ({len(entries)} files)")
    return 0


def parse_sums(path: Path) -> dict[str, str]:
    sums = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, name = line.split("  ", 1)
        sums[name] = digest
    return sums


def check(root: Path) -> int:
    errors = []
    entries = {e["path"]: e for e in build_entries(root)}

    sums_path = root / "SHA256SUMS"
    if not sums_path.is_file():
        errors.append("SHA256SUMS is missing")
        sums = {}
    else:
        sums = parse_sums(sums_path)
        for name, digest in sums.items():
            entry = entries.get(name)
            if entry is None:
                errors.append(f"SHA256SUMS lists a missing file: {name}")
            elif entry["sha256"] != digest:
                errors.append(f"SHA256SUMS mismatch: {name}")
        for name in entries:
            if name not in sums:
                errors.append(f"SHA256SUMS is missing: {name}")

    manifest_path = root / "MANIFEST.json"
    if not manifest_path.is_file():
        errors.append("MANIFEST.json is missing")
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        listed = {e["path"]: e for e in manifest.get("files", [])}
        for name, entry in entries.items():
            got = listed.get(name)
            if got is None:
                errors.append(f"MANIFEST.json is missing: {name}")
            elif (got.get("sha256") != entry["sha256"]
                  or got.get("size") != entry["size"]):
                errors.append(f"MANIFEST.json mismatch: {name}")
        for name in listed:
            if name not in entries:
                errors.append(f"MANIFEST.json lists a missing file: {name}")

    if errors:
        print(f"{len(errors)} integrity error(s):", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        return 1
    print(f"integrity OK ({len(entries)} files)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true",
                       help="verify SHA256SUMS/MANIFEST.json against the tree")
    group.add_argument("--write", action="store_true",
                       help="regenerate SHA256SUMS and MANIFEST.json")
    args = parser.parse_args(argv)
    return write(PROJECT) if args.write else check(PROJECT)


if __name__ == "__main__":
    sys.exit(main())
