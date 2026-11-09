> [中文](README.md) | English

# binary/qemu-system-arm

Prebuilt QEMU binary for the Nikon `nikon-d750` overlay.

> **This file is ~96 MiB and is not committed to Git history**; it is published
> as a GitHub Release asset:
> <https://github.com/LuoStickmin/D750-QEMU/releases/latest/download/qemu-system-arm>

| Item | Value |
| --- | --- |
| QEMU version | 11.1.0 |
| Release | v0.2.7 (M1 + `flash-size`/`aux-ram-size`/`mmu-table`/`vector-fix`/`veneer-slot`/`loader-copies`) |
| Platform | Linux x86-64 (WSL2 Ubuntu 26.04) |
| Size | 100,651,184 bytes |
| SHA-256 | `c92876f841a3476fed059514aa2198974bba2a590a745ef51bb2f30cfc0a74dd` |
| License | GPLv2; see `COPYING` in the same directory |

## Download and run

```bash
cd /path/to/D750-QEMU
curl -L -o binary/qemu-system-arm \
  https://github.com/LuoStickmin/D750-QEMU/releases/latest/download/qemu-system-arm
chmod +x binary/qemu-system-arm
./binary/qemu-system-arm -M help | grep nikon
```

You should see:

```
nikon-d750           Nikon D750 validation prototype (EXPEED 4, M1 boot chain, experimental)
```

Start an M1 run (default):

```bash
python3 tools/run.py --qemu binary/qemu-system-arm \
  --payload /path/to/b1010_115a.bin \
  --flash   /path/to/a1010_011100.bin \
  --boot stub --a1010-base 0x10018000
```

M0 regression (legacy layout):

```bash
python3 tools/run.py --qemu binary/qemu-system-arm \
  --payload /path/to/b1010_115a.bin \
  --flash   /path/to/a1010_011100.bin \
  --boot entry --a1010-base 0x10000000
```

## Dependencies

Running in the same WSL distribution that built it is the most reliable (glib 2.88, pixman 0.46).
On other Linux systems, if shared libraries are missing, just rebuild following `docs/build.md`; the source is in
`qemu/`, and the build script is `tools/build.py`.

## Rebuilding

```bash
python3 tools/build.py --source <QEMU 11.1.0 source tree> --jobs 4
```

Or build from a tarball following `docs/build.md`. The SHA-256 of the rebuilt binary may differ
(depending on compiler/timestamps), which is normal.
