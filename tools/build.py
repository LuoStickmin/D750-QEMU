# SPDX-License-Identifier: GPL-2.0-or-later
"""Fetch (optionally), overlay and build QEMU for the D750 prototype.

No Nikon firmware is downloaded or embedded.  This tool only handles the
upstream QEMU source archive.

Linux:
    python tools/build.py --jobs 4

Windows with MSYS2 UCRT64:
    python tools/build.py --msys-root C:\\msys64 --jobs 4

Offline:
    python tools/build.py --archive C:\\downloads\\qemu-11.1.0.tar.xz
    python tools/build.py --source C:\\src\\qemu-11.1.0

The produced binary is ``<work>/build/qemu-system-arm[.exe]`` and a build
manifest is written to ``.local/build-manifest.json``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
DEFAULT_URL = "https://download.qemu.org/qemu-11.1.0.tar.xz"
CONFIGURE_ARGS = ["--target-list=arm-softmmu", "--disable-werror",
                  "--disable-docs", "--disable-tools"]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, dest: Path, expect: str | None, timeout: int = 600) -> Path:
    if dest.is_file() and (not expect or sha256_file(dest) == expect):
        print(f"using cached archive {dest}")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    print(f"downloading {url}")
    started = time.time()
    with urllib.request.urlopen(url, timeout=timeout) as resp, tmp.open("wb") as out:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
    os.replace(tmp, dest)
    digest = sha256_file(dest)
    print(f"downloaded {dest.stat().st_size} bytes in "
          f"{time.time() - started:.1f}s, sha256={digest}")
    if expect and digest != expect.lower():
        raise SystemExit(f"archive SHA-256 mismatch: {digest} != {expect}")
    return dest


def _safe_extract_filter(member: tarfile.TarInfo, dest: str):
    """Extract upstream QEMU without following links outside the tree.

    The QEMU tarball contains a few EDK2 convenience symlinks to absolute
    host paths; Python's strict ``data`` filter rejects the whole archive
    for one of them.  Skip only those links, keep everything else.
    """
    if member.issym() or member.islnk():
        target = member.linkname
        if os.path.isabs(target):
            print(f"skipping absolute link {member.name} -> {target}")
            return None
        base = os.path.dirname(os.path.abspath(os.path.join(dest, member.name)))
        resolved = os.path.abspath(os.path.join(base, target))
        root = os.path.abspath(dest)
        if not resolved.startswith(root + os.sep):
            print(f"skipping out-of-tree link {member.name} -> {target}")
            return None
    if member.isdev():
        return None
    return member


def extract(archive: Path, work: Path) -> Path:
    work.mkdir(parents=True, exist_ok=True)
    marker = work / ".extract-complete"
    if marker.is_file():
        print(f"reusing extracted tree {work}")
        return work
    print(f"extracting {archive} -> {work}")
    with tarfile.open(archive, "r:*") as tar:
        tar.extractall(work, filter=_safe_extract_filter)
    marker.write_text(archive.name + "\n", encoding="utf-8")
    return work


def pick_source_dir(work: Path) -> Path:
    candidates = [p for p in work.iterdir() if (p / "VERSION").is_file()]
    if not candidates:
        raise SystemExit(f"no QEMU source tree under {work}")
    return candidates[0]


def run(cmd: list[str], cwd: Path, env: dict | None = None) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def build(source: Path, jobs: int, msys_root: Path | None) -> Path:
    if msys_root:
        bash = msys_root / "usr" / "bin" / "bash.exe"
        if not bash.is_file():
            raise SystemExit(f"MSYS2 bash not found: {bash}")
        env = dict(os.environ)
        env["PATH"] = str(msys_root / "ucrt64" / "bin") + os.pathsep + env["PATH"]
        quoted = " && ".join([
            "./configure " + " ".join(CONFIGURE_ARGS),
            f"ninja -C build -j {jobs}",
        ])
        run([str(bash), "-lc", quoted], cwd=source, env=env)
    else:
        if not (source / "configure").is_file():
            raise SystemExit(f"{source} has no configure script")
        run(["./configure", *CONFIGURE_ARGS], cwd=source)
        run(["ninja", "-C", "build", "-j", str(jobs)], cwd=source)
    for name in ("qemu-system-arm.exe", "qemu-system-arm"):
        candidate = source / "build" / name
        if candidate.is_file():
            return candidate
    raise SystemExit("build finished but qemu-system-arm was not produced")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, help="existing QEMU source tree")
    parser.add_argument("--archive", type=Path, help="pre-downloaded QEMU tarball")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--sha256", help="expected archive SHA-256")
    parser.add_argument("--work-dir", type=Path, default=PROJECT / ".build")
    parser.add_argument("--msys-root", type=Path,
                        help=r"MSYS2 root, e.g. C:\msys64")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--overlay-only", action="store_true",
                        help="apply the overlay and stop before configure")
    args = parser.parse_args(argv)

    work = args.work_dir.resolve()
    if args.source:
        source = args.source.resolve()
    elif args.archive:
        archive = args.archive.resolve()
        source = pick_source_dir(extract(archive, work / "src"))
    else:
        archive = download(args.url, work / "download" /
                           Path(args.url).name, args.sha256)
        source = pick_source_dir(extract(archive, work / "src"))

    sys.path.insert(0, str(PROJECT / "qemu"))
    from prepare_source import prepare  # noqa: PLC0415

    summary = prepare(source)
    print(f"QEMU {summary['qemu_version']} prepared at {source}")
    if args.overlay_only:
        return 0

    binary = build(source, args.jobs, args.msys_root.resolve()
                   if args.msys_root else None)
    manifest = {
        "qemu_version": summary["qemu_version"],
        "source": str(source),
        "binary": str(binary),
        "binary_sha256": sha256_file(binary),
        "overlay": summary,
        "configure_args": CONFIGURE_ARGS,
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    local = PROJECT / ".local"
    local.mkdir(exist_ok=True)
    (local / "build-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"built {binary}")
    print(f"manifest {local / 'build-manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
