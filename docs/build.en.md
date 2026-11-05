> [中文](build.md) | English

# Building and Checking Against the Installed QEMU

## 1. Current state of this machine (verified)

| Item | Value |
| --- | --- |
| Installation path | `C:\Program Files\qemu` |
| Version | `11.1.0` (VERSION file; file version 2026-08-11) |
| System emulators | `qemu-system-arm.exe`, `qemu-system-aarch64.exe` (plus `w` variants) |
| `-M help` | Only upstream ARM machines; **no** `nikon-*` |
| Conclusion | This is a **stock build**; new machines cannot be loaded at runtime |

QEMU machine types are registered at compile time through `type_init()`; `-M` only accepts names already compiled into
the binary. Therefore "running D750 directly with the installed QEMU" does not hold; `hw/arm/nikon-d750-lab.c` must be
compiled into a `qemu-system-arm`.

The installed binary is still useful: `tools/probe.py` has already performed real RSP interoperability testing against its `-M virt -S -gdb`
(register reads, memory reads, hardware breakpoints, continue, and CPSR parsing all pass), so the protocol layer is not a paper implementation.

## 2. Dependencies

Common: Python 3.12+, Ninja, pkg-config, GLib, Pixman, zlib, the FDT development package,
and a C compiler.

Linux (Ubuntu 24.04-style):

```sh
sudo apt-get update
sudo apt-get install build-essential ninja-build pkg-config \
    libglib2.0-dev libpixman-1-dev zlib1g-dev libfdt-dev
```

Windows (MSYS2 UCRT64, paths same as z7-qemu):

```sh
pacman -S --needed make diffutils mingw-w64-ucrt-x86_64-gcc \
  mingw-w64-ucrt-x86_64-glib2 mingw-w64-ucrt-x86_64-pixman \
  mingw-w64-ucrt-x86_64-pkgconf mingw-w64-ucrt-x86_64-python \
  mingw-w64-ucrt-x86_64-ninja mingw-w64-ucrt-x86_64-meson \
  mingw-w64-ucrt-x86_64-dtc mingw-w64-ucrt-x86_64-zlib
```

Windows needs permission to create symbolic links (Developer Mode or equivalent permissions); otherwise QEMU's
meson configuration will fail.

## 3. Build

```powershell
python tools/build.py --msys-root C:\msys64 --jobs 4
```

Linux:

```sh
python tools/build.py --jobs 4
```

The script will:

1. Download `https://download.qemu.org/qemu-11.1.0.tar.xz` (or use `--archive` /
   `--source`);
2. Extract to `.build/src/`, with a completion marker to avoid half-extracted trees;
3. Invoke `qemu/prepare_source.py` to install the overlay;
4. `./configure --target-list=arm-softmmu --disable-werror --disable-docs --disable-tools`
   + `ninja -C build` (disabling docs/tools avoids depending on sphinx and qemu.qmp from PyPI);
5. Locate `build/qemu-system-arm[.exe]`, and write the SHA-256, overlay digest, and configure
   parameters to `.local/build-manifest.json`.

Offline:

```powershell
python tools/build.py --archive D:\downloads\qemu-11.1.0.tar.xz
python tools/build.py --source D:\src\qemu-11.1.0
```

Install only the overlay without compiling (used to check whether the patch is idempotent):

```powershell
python tools/build.py --source D:\src\qemu-11.1.0 --overlay-only
```

## 4. Post-build self-check

```powershell
& .build\build\qemu-system-arm.exe -M help | Select-String nikon
```

You should see:

```
nikon-d750           Nikon D750 validation prototype (EXPEED 4, experimental)
```

Then confirm the machine starts (without a payload it reports a clear error; this is expected):

```powershell
& .build\build\qemu-system-arm.exe -M nikon-d750 -display none -monitor none
# nikon-d750: a decrypted main payload is required; pass -kernel FILE ...
```

## 5. Version compatibility

- **11.1.0**: preferred target. The chardev front-end type is `CharFrontend`.
- **10.2.4**: `prepare_source.py` replaces `CharFrontend` with
  `CharBackend` in the source; the other APIs match z7-qemu's target version.
- Other versions: prepare will reject them; after confirming the API, add them to `SUPPORTED`; do not try silently.

## 6. Troubleshooting

| Symptom | Cause | Action |
| --- | --- | --- |
| `no VERSION` / `unexpected tree` | `--source` points to the wrong place | Point to a QEMU root directory containing `VERSION` and `hw/arm/` |
| configure cannot find glib/pixman | Incomplete MSYS2 packages or wrong PATH | Run `pkg-config --modversion glib-2.0` in a UCRT64 shell |
| `ninja: command not found` | ninja not installed or wrong shell | Use `--msys-root`; do not run configure directly from PowerShell |
| Symbolic link permission error | Developer Mode is not enabled on Windows | Enable it and retry, or switch to WSL |
| `machine 'nikon-d750' not found` | The installed QEMU was used | Use `.build/src/qemu-<版本>/build/qemu-system-arm` |
| Download 404 | Version number/mirror unavailable | Download the tarball in advance and use `--archive` |

## 7. Verification record for this environment (2026-11-05)

The build and run actually passed; the environment and details are as follows.

| Item | Value |
| --- | --- |
| Environment | WSL2 Ubuntu 26.04.1 LTS |
| Compiler | gcc 15.2.0 |
| Dependencies | glib 2.88.0, pixman 0.46.4, zlib 1.3.1, ninja 1.13 |
| Python | 3.14.4 |
| QEMU | 11.1.0 (tarball SHA-256 `6ee1d1a6…08fa858`) |
| Build command | `python3 tools/build.py --work-dir ~/d750-build --jobs 12` |
| Artifact | `~/d750-build/src/qemu-11.1.0/build/qemu-system-arm` (96 MB, with debug symbols) |

Notes:

1. Put `--work-dir` under WSL's `$HOME`; the default user has no write permission on `/root`.
2. When PyPI is unreachable, configure attempts to install `qemu.qmp` and prints retry failures, but continues;
   `--disable-docs --disable-tools` already avoids the hard dependencies on sphinx and qemu.qmp.
3. The first compilation exposed and fixed two real API details:
   - `qdev_prop_set_uint32()` needs `hw/core/qdev-properties.h`;
   - The owner of `memory_region_init_ram()` must be a `DeviceState` or `NULL`;
     passing a `MachineState` triggers `DEVICE: Object ... is not an instance of type device`.
4. `-M help` confirms the appearance of:

   ```
   nikon-d750           Nikon D750 validation prototype (EXPEED 4, experimental)
   ```

5. The results of running `tools/run.py` are in M0 of [validation](validation.md):
   0.18 s, exit code 0, and `qemu.log` records `r0/r1/sp/lr` at halt.

The Windows side still has no MSYS2 build artifact; this repository delivers reproducible source + a WSL build path.
The stock binary at `C:\Program Files\qemu` still cannot load this machine.
