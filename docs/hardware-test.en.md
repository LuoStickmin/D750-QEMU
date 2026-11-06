# Real-Hardware Testing: Preconditions and Risks (1080p 64/60 Mbps)

> [中文](hardware-test.md) | English

**Conclusion (2026-11-06):** the container chain can now be reproduced byte for
byte, but **no physical D750 has verified updater acceptance or encoder
behaviour**. This is a high-risk experiment on a spare body, not a recommended
flashing procedure.

QEMU M0 covers only the boot entry; it has **no predictive value** for the H.264
encoder, card writes, or playback. Do not treat a passing M0 as evidence that the
camera works.

## 1. What has been verified (container layer)

Inputs: stock `D750_0115.bin` (21,552,187 B) and the patched `b1010_115a.bin`.
Tools: `repack_firmware.py` and `d750_bitrate_verify.py` in the author's other
repository
[Nikon-Expeed-4-and-5-firmware-tool](https://github.com/LuoStickmin/Nikon-Expeed-4-and-5-firmware-tool).

- The D750 uses **packaging A**: 32 spaces at `0x00`, with no 20-byte keyed digest
  in the file. K8/`STALE` only affects packaging B (D850/D5 class).
- Repacking the stock image with no edits: `--selftest` output is **bit-identical**
  to the input (sha256
  `6c1dfadc8feb38bc783522c37f6351e1e8006f4684c8234690afb9aa08444859`).
- Repacking stock + the patched `b1010` module reproduces
  `9c88f3cc80e5e19d780055ced0e4e539739f0e858af1e831228e5f19e904988a`
  from `bitrate/README.en.md` **exactly**.
- Container diff: same size; the 32-byte header is unchanged; only **36 B**
  differ, at `0x3D6575..0x3D665C` (five HQ rows) and `0x148DC29..2A` (b1010 module
  CRC); the package-CRC field `0x148DC2B` stays `f540` (residue); the other two
  modules are byte-identical.

This proves that "patch the table → recompute CRCs → re-encrypt → container" is
reproducible. It says **nothing** about the camera side.

## 2. What has not been verified (decides success on hardware)

| Item | Status | Why it matters |
| --- | --- | --- |
| Updater acceptance | ❓ no hardware report | May reject on model/version/hidden checks, or require a newer version |
| Same-version reflash | ❓ unknown | If 1.15 → 1.15 is rejected, do not force it by bumping the version string |
| Encoder behaviour | ❓ unknown | The table ceiling 70,780,800 allows 64 Mbps, but the D750 encoder may cap or fall back |
| Card/buffer/heat | ❓ unknown | 64 Mbps ≈ 8 MB/s; slow cards, long takes and heat can all fail |
| Playback | ❓ unknown | The camera may play back differently from a computer |
| Failure mode | ❓ unknown | Rejection (safe) / interrupted update / boot failure (service) |

## 3. Hard gates before touching a camera

1. **A spare D750**, or the ability to pay for a mainboard repair.
2. **Re-run the chain yourself** instead of trusting these numbers:

   ```sh
   # 1) no-edit repack must be bit-identical
   python repack_firmware.py --firmware D750_0115.bin --key key_all.json \
     --out stock.repack.bin --selftest
   # 2) stock + patched module must reproduce 9c88f3cc…
   python repack_firmware.py --firmware D750_0115.bin --key key_all.json \
     --out D750_0115.hq64.bin \
     --replace-module b1010_115a.bin=b1010_115a.hq64.bin --encrypt --keep-tags
   ```

3. **Inspect the updater statically**: does it check only CRC/model/version, or is
   there a hidden signature check? This is the zero-risk, highest-information step.
4. **Confirm the same-version policy**: if 1.15 → 1.15 is refused, stop and
   evaluate; do not force a version bump.
5. **Prepare rollback**: stock image, full battery or dummy battery, a known-good
   UHS-I card; rename the patched file back to `D750_0115.bin`.

## 4. Minimum-risk procedure

1. Updater accepts → boot, check version and basic functions (stills, playback, menus);
2. Record a 10-second 1080p HQ clip → check the actual bitrate with `ffprobe`;
3. Play it back in the camera;
4. Check body temperature; look for dropped frames or corruption;
5. Extend gradually: 30 s → 2 min → longer;
6. Stop on any anomaly; **do not flash a second time in a row**.

## 5. Verdict criteria

- **Success**: bitrate close to 64 Mbps, in-camera playback, no dropped takes or
  overheating, stable over longer recordings.
- **Acceptable failure**: the updater rejects the file (usually nothing is written;
  the camera stays on stock).
- **Service required**: black screen, no boot, interrupted update.

## 6. What to record

- Camera model/current firmware, file name, image SHA-256, module SHA-256;
- Updater messages/error codes;
- `ffprobe` output, recording length, temperature, card model;
- Feed the result back as an issue/PR (**do not attach firmware or patched images**).

## 7. What this project will not do

- Provide flashable packages, keys, decryptors, or patched images;
- Bypass signature checks or promise brick-proofing;
- Promise compatibility with any model/firmware revision.
