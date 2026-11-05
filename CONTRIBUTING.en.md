> [中文](CONTRIBUTING.md) | English

# Contributing

> This document states project rules and legal boundaries; it is **not legal
> advice**. If you plan to redistribute, flash a camera, or use this in a
> commercial setting, consult a lawyer in your jurisdiction.

## 1. What this project is

This repository is **independent firmware interoperability and validation
research**: a Nikon D750 QEMU validation prototype plus an analysis/tool for a
1080p bitrate-table modification. It is not affiliated with or endorsed by
Nikon, WonderLantern, or Magic Lantern. Nikon, D750, and EXPEED are trademarks
of their respective owners and are used only to identify the research target
(nominative fair use).

## 2. Never submit (hard prohibitions)

The following are **not accepted**, whether as attachments, patches, test
fixtures, issue pastes, or Git history:

1. **Nikon firmware** (`.bin`, update packages, decrypted modules, complete
   images of any fragment);
2. **keys/key tables** (`key_all.json`, T1/T2/T3, key material output by a
   decryptor);
3. **boot ROM / flash dumps / camera dumps**, or code, data, or calibration
   tables from them;
4. **Nikon copyrighted assets**: fonts, icons, UI strings/translations, menu
   resources, sample photographs, camera screenshots;
5. **long proprietary code excerpts** obtained by decompilation/disassembly,
   or code clearly copied from leaked sources;
6. **ready-to-flash patched images**, signature/checksum bypass tools, or
   updater bypass methods;
7. **personal data**: serial numbers, internal camera IDs, user photographs,
   location/account information;
8. anything that violates local law, including but not limited to DMCA §1201,
   EU Directive 2009/24/EC, or Japanese copyright law.

> Note: the high-bitrate tool patches only a **decrypted module you supply
> yourself**. It ships no firmware, keys, decryptor, or patched image. Do not
> attach those inputs when contributing related code.

## 3. What is welcome

- your own C/Python/docs/tests;
- **factual** information such as addresses, offsets, hashes, and short numeric
  constants (e.g. `0x2AA9AC`, `0x12CA`);
- analysis derived from public specifications, observable behavior, or
  experiments on your own device;
- bug reports, reproduction steps, and logs that contain no firmware (remove
  personal information first);
- improvements to docs, build, tests, and portability.

## 4. Licensing and DCO

- Unless a file header says otherwise, contributions are licensed under
  **GPL-2.0-or-later**;
- opening a PR means you agree to the
  [Developer Certificate of Origin 1.1](https://developercertificate.org/);
  add `Signed-off-by: Your Name <you@example.com>` to the commit message;
- do not submit code, docs, or assets you are not entitled to license;
- upstream QEMU code keeps its own license; do not change its copyright
  headers.

## 5. Legal and compliance (important)

1. **Interoperability/research purpose**: this project performs static and
   emulation research only on devices you legally own and firmware you obtained
   locally. It does not provide piracy, paid-feature bypass, or
   technical-protection-circumvention instructions.
2. **Firmware copyright belongs to Nikon**: the repository records only
   offsets, hashes, and conclusions, not expressive firmware content.
   Contributors must not submit firmware or derived binaries as "test data".
3. **Flashing is at your own risk**: any camera modification can brick the
   device, lose data, void warranty, or require paid repair. Maintainers
   provide no recovery plan and accept no liability.
4. **Local law comes first**: rules on firmware modification, checksum bypass,
   DMCA §1201, and the EU 2009/24/EC interoperability clause differ by
   jurisdiction; you are responsible for confirming legality.
5. **Trademarks**: Nikon, D750, and EXPEED are used only to identify the
   research target; no official affiliation, sponsorship, or endorsement is
   implied.
6. **No warranty**: the software is provided "as is", without any express or
   implied warranty; maintainers are not liable for damages arising from use or
   inability to use it.
7. **Removal policy**: if a rights holder makes a substantiated request,
   maintainers will remove the relevant content and keep a record; contact us
   through an issue or the repository's public contact.

## 6. Contribution workflow

1. Open an issue describing the problem/goal before sending a large patch;
2. Fork → branch → change → run tests:

   ```sh
   python tests/run_tests.py
   D750_MODULE=/path/to/b1010_115a.bin python bitrate/test_d750_bitrate_patch.py
   ```

3. Open a PR explaining what changed, why, how it was verified, and which
   parts are assumptions;
4. Do not attach firmware, keys, dumps, screenshots, or large binaries;
   discuss large files first;
5. Maintainers may reject a change for legal, evidentiary, or scope reasons
   without a full explanation.

## 7. Security and privacy

- Do not post camera serial numbers, internal IDs, personal photographs, or
  full log paths in public issues;
- If you find an issue that could affect device safety, contact the
  maintainers privately first; do not publish reproducible destructive steps;
- this repository provides no camera USB/flashing/installation tooling and
  does not accept such tools.

## 8. See also

- [NOTICE.md](NOTICE.md) — independent research, no firmware, licensing
- [SUMMARY.md](SUMMARY.md) — both workstreams at a glance
- [README.md](README.md) — the QEMU prototype
- [bitrate/README.md](bitrate/README.md) — high-bitrate modification
