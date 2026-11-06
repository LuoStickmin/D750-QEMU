> [中文](README.md) | English

# D750 1080p high-bitrate modification (64/60 Mbps)

> **Scope**: the document and `bitrate/` tools perform **local static patching
> and container-level verification only**. No firmware, keys, decrypted images,
> or patched images are included. Camera capture is unverified; flashing is at
> your own risk. See [CONTRIBUTING.md](../CONTRIBUTING.md) and
> [NOTICE.md](../NOTICE.md).

## 1. Result

| Item | Result |
| --- | --- |
| Target | Nikon D750, `D750_0115` (1.15), module `b1010_115a.bin` |
| Table | file offset `0x2AA9AC`, 28 bytes/entry, 9 entries in the 1080p group |
| Rows touched | entry 1 / 3 / 5 / 7 / 9 (HQ rows) |
| Before | `42/35`, `42/35`, `24/20`, `24/20`, `24/20` Mbps |
| After | all `64/60` Mbps (`0x03D09000` / `0x03938700`) |
| Untouched | four NQ rows, the lower-resolution group from entry 10, the other two modules |
| Module CRC | `0x12CA` → `0x4314` |
| Package CRC | `0x7EE4` → `0x7EE4` (CRC residue; not "unchanged", see §3) |
| Decrypted-image diff | 36 B: 34 B bitrate fields + 2 B module CRC; 0 B outside fields |
| QEMU M0 regression | identical to stock: exit 0, same halt registers, 0 MMIO, 0 UART |
| Camera capture | **unverified** |

## 2. Table and offsets

The 1080p group in `b1010_115a.bin` starts at `0x2AA9AC`:

```
entry 1  0x2AA9AC
entry 2  0x2AA9C8
entry 3  0x2AA9E4
entry 4  0x2AAA00
entry 5  0x2AAA1C
entry 6  0x2AAA38
entry 7  0x2AAA54
entry 8  0x2AAA70
entry 9  0x2AAA8C
entry 10 0x2AAAA8   <- ceiling drops to ~47.19 Mbps, inferred 720p/480p group, untouched
```

The first two little-endian u32 fields of each entry are the two bitrate
slots, followed by `flag=1`, the entry ceiling (1080p group:
`0x04380780` = 70,780,800 bps), and timebase/frame-rate fields. 64/60 Mbps is
below the 70,780,800 ceiling.

The five-HQ-row mapping is isomorphic to Nikon Hacker's D810 1.14 patch:
D810's `Video 1080 HQ 64mbps` also changes entries 1/3/5/7/9 to
`64,000,000 / 60,000,000`; both tables use 28-byte entries, the same field
order, and the same ceiling.

## 3. Verification

Before writing, `bitrate/d750_bitrate_patch.py` enforces:

1. the five HQ rows must hold exactly `42/35` or `24/20`;
2. every row must have `flag == 1` and ceiling 70,780,800;
3. the 64/60 target must stay below the ceiling;
4. after patching, re-parsing must read 64/60 for all five rows;
5. the four NQ rows must be byte-identical;
6. differences must be confined to the five rows × two u32 fields.

Independent verification (`d750_bitrate_verify.py`, `repack_firmware.py`) lives in
the author's other repository,
[Nikon-Expeed-4-and-5-firmware-tool](https://github.com/LuoStickmin/Nikon-Expeed-4-and-5-firmware-tool);
running it needs the keys/decryptor you legally hold.

```
stock   image sha256 6c1dfadc8feb38bc783522c37f6351e1e8006f4684c8234690afb9aa08444859
patched image sha256 9c88f3cc80e5e19d780055ced0e4e539739f0e858af1e831228e5f19e904988a
module  sha256       ea0c161dd8bfc7fdd7037c13005e8a4f7f3ddf98a79c9565e2c8aa973ba3f579
package CRC 0x7EE4 -> 0x7EE4
b1010 CRC   0x12CA -> 0x4314
changed decrypted bytes: 36 (fields+CRCs), outside: 0
HQ rows at target:
  entry 1 @0x2AA9AC  64000000 / 60000000
  entry 3 @0x2AA9E4  64000000 / 60000000
  entry 5 @0x2AAA1C  64000000 / 60000000
  entry 7 @0x2AAA54  64000000 / 60000000
  entry 9 @0x2AAA8C  64000000 / 60000000
all checks passed
```

**Reproducibility boundary (updated 2026-11-06):** the patched image can now be
reproduced byte for byte —

- repacking the stock image with no edits: `repack_firmware.py --selftest`
  produces a **bit-identical** image (sha256 `6c1dfadc…08444859`);
- repacking stock + the patched `b1010` module reproduces the published
  `9c88f3cc…e904988a` **exactly**;
- container diff: same size (21,552,187 B); the 32-byte header is unchanged;
  only **36 B** differ, at `0x3D6575..0x3D665C` (the five HQ rows) and
  `0x148DC29..2A` (b1010 module CRC); the package-CRC field `0x148DC2B` stays
  `f540` (residue); the other two modules are byte-identical.

**Packaging note:** the D750 uses **packaging A** (32 spaces at `0x00`; there is
no 20-byte keyed digest in the file), so K8/`STALE` only affects packaging B
(D850/D5 class) and is not relevant here.

This proves the container/CRC/re-encryption chain is reproducible. It does **not**
prove the camera updater accepts the image, nor how the encoder behaves; see
[docs/hardware-test.md](../docs/hardware-test.md) for the hardware preconditions.

**Why the package CRC did not change:** CRC-16 residue makes
`CRC16(payload || CRC16(payload)) == 0`; each module carries its own CRC, so the
package CRC is insensitive to "payload change + module CRC recompute". The payload
really did change; the evidence is the module CRC `0x12CA → 0x4314` and the
36-byte diff, not the package CRC.

## 4. Hashes

| File | Size | SHA-256 |
| --- | ---: | --- |
| `D750_0115.bin` (stock encrypted image) | 21,552,187 | `6c1dfadc…08444859` |
| `D750_0115.hq64.bin` (patched image, local) | 21,552,187 | `9c88f3cc…e904988a` |
| `b1010_115a.bin` (stock module) | 20,324,448 | `faada7fe…f82937fd` |
| `b1010_115a.hq64.bin` (patched module, local) | 20,324,448 | `ea0c161d…ba3f579` |
| `D750_0115.dec` (stock decrypted) | 21,552,187 | `1ec77111…7c749bdd` |
| `D750_0115.hq64.dec` (patched decrypted) | 21,552,187 | `79e59294…ca1c300` |

Full hashes are in the local `D750_0115.hq64.out/verify_report.json`; the
repository contains none of these images.

## 5. Tools

```sh
# check the table only
python bitrate/d750_bitrate_patch.py \
  --module D750_0115.dec.modules/b1010_115a.bin --check

# produce the patched module
python bitrate/d750_bitrate_patch.py \
  --module D750_0115.dec.modules/b1010_115a.bin \
  --out b1010_115a.hq64.bin --json patch_report.json

# unit tests (needs a local module)
D750_MODULE=/path/to/b1010_115a.bin python bitrate/test_d750_bitrate_patch.py
```

Repacking / re-encryption / container CRCs are not in this repository, but in the
author's other repository
[Nikon-Expeed-4-and-5-firmware-tool](https://github.com/LuoStickmin/Nikon-Expeed-4-and-5-firmware-tool)
(`repack_firmware.py`). This repository still ships no keys, decryptor, or patched
image.

## 6. Risks and unverified items

1. **Encoder/card/playback unverified.** 64 Mbps is about 2.7× the stock
   24 Mbps at 1080p30; the camera may stop early on a slow card, produce files
   that a computer can play but the camera cannot, or reduce bitrate due to
   heat/encoder limits.
2. **Updater acceptance unverified.** The tool and the sibling repack tool only
   guarantee a self-consistent container CRC. The D750 uses packaging A with no
   signature header, but whether the updater applies model/version/hidden checks
   is unknown, and the same-version (1.15 → 1.15) reflash policy is unknown too.
   A patched image is not guaranteed to be accepted; see
   [docs/hardware-test.md](../docs/hardware-test.md).
3. **Do not test on your only working camera.** Keep the stock image; check
   battery, use a known-good UHS-I card, record 10–30 seconds first, then check
   bitrate and playback.
4. This change touches only the five 1080p HQ rows; NQ rows remain 24/20 and
   12/10, and the 720p/480p group is untouched.

## 7. References

- Nikon Hacker D810 1.14 patch definitions (`Video 1080 HQ 64mbps`):
  <https://github.com/simeonpilgrim/nikon-firmware-tools>
- High-bitrate background:
  <https://simeonpilgrim.com/blog/2014/02/23/high-bit-rate-recording-now-solved/>
- QEMU regression: [../docs/validation.md](../docs/validation.md) and
  [../evidence/](../evidence/).

## 8. Menu-visible variant

A genuine third item is blocked at the menu descriptor; see
[../analysis/menu-bitrate-feasibility.en.md](../analysis/menu-bitrate-feasibility.en.md).
The delivered alternative reuses the two Movie quality slots: `High quality`
→ `64 Mbps HQ`, `Normal` → `Stock`. Tool: `d750_menu_patch.py`; design,
verification, and risks: [MENU64.md](MENU64.md). It is not a third item, and
the camera UI is unverified.
