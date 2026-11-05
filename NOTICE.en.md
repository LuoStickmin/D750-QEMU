> [中文](NOTICE.md) | English

# Notice

## Independent Research Statement

This project is an independent firmware research/learning project; it is not an official release by
Nikon or WonderLantern, nor is it endorsed by them. Nikon, D750, and EXPEED are trademarks of their respective
rights holders and are used only to identify the subject of research.
The project claims no rights over Nikon firmware, the code/resources within the firmware, or any camera private data.

## No Firmware Included

This repository **does not contain** any Nikon firmware, decrypted programs, camera dumps, keys, fonts/icons,
calibration data, or camera UI screenshots. `analysis/d750-0115.json` contains only lengths, SHA-256,
file offsets, and address constants; it contains no image bytes. The tools do not download firmware.

Using this project requires D750 modules that you legally own and that have already been decrypted; the tools open them read-only.
Do not attach firmware or its derived data in issues, PRs, releases, or shared build caches.

## Risks

Flashing, repacking, and bypassing signatures are outside the scope of this project. Any modification to the camera may cause bricking,
data loss, or the need for paid repair; this project provides no recovery procedure and accepts no responsibility for the consequences.

## Legal and compliance

- This is not legal advice; firmware modification, checksum bypass, DMCA §1201,
  and EU 2009/24/EC apply differently by jurisdiction — verify legality
  yourself.
- The project is for **interoperability/research on devices you legally own**
  and firmware obtained locally; it provides no piracy, paid-feature bypass, or
  technical-protection-circumvention instructions.
- The software is provided "as is", without any express or implied warranty;
  maintainers are not liable for the consequences of use.
- If a rights holder makes a substantiated request, maintainers will remove the
  relevant content and keep a record.
- Contribution boundaries and DCO: see [CONTRIBUTING.md](CONTRIBUTING.en.md).

## Third parties and references

- Nikon Hacker's patch database/tools are referenced only and **are not
  redistributed here**: <https://github.com/simeonpilgrim/nikon-firmware-tools>
- WonderLantern's QEMU projects and key tool are architecture/method references:
  <https://github.com/WonderLantern/z7-qemu>,
  <https://github.com/WonderLantern/z9-qemu>,
  <https://github.com/WonderLantern/nikon-fw-key-tool>
- Nikon, D750, and EXPEED are trademarks of their respective owners and are used
  only to identify the research target.

## License

- The overlay under `qemu/`, `tools/`, `tests/`, `docs/`, `bitrate/`:
  **GPL-2.0-or-later**.
- Upstream QEMU retains its per-file licenses; QEMU as a whole is GPLv2.

This project's GPL license grants no rights to any Nikon firmware or third-party proprietary material.
