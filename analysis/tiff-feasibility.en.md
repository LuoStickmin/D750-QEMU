> [中文](tiff-feasibility.md) | English

# Adding a TIF Storage Option to the D750 Shooting Menu: Feasibility Analysis

Date: 2026-11-05  
Subject: Nikon D750, firmware `D750_0115`, main module `b1010_115a.bin` (20,324,448 B, SHA-256
`faada7fe…f82937fd`)  
Nature: **read-only static analysis; no firmware was modified, repacked, or flashed.**

## Conclusion

**TIF storage cannot be reproduced in the D750's shooting menu by "flipping a switch."** The D750 firmware does contain TIFF-related bytes, but they are:

1. A generic **filename template** (`DSC_0000.TIF`);
2. Extension names and a TIFF tag table used for **XMP/EXIF metadata parsing**;
3. Coincidental strings inside code bytes or JPEG entropy data.

The D750 has no TIFF image **encoder**, and no `TIFF`/`TIF` menu text in any language. The models that truly support
`TIFF (RGB)` are the D810, D850, and D5 tier; the D750 firmware does not even have the label. Adding TIF shooting
to the D750 amounts to writing a new TIFF encoder and wiring it into the still-image pipeline, menus, settings persistence,
and playback/DPOF; this is a feature port, not a static patch.

Therefore, this time **no firmware was modified**. Below are the evidence, the boundaries, and the engineering steps required
to continue.

---

## 1. TIF Bytes Actually Found in the Firmware

A full ASCII/UTF-16 scan of `b1010_115a.bin` found only the following categories of genuine TIF hits:

| Offset | Content | Nature |
| --- | --- | --- |
| `0x126b4b6` | `DSC_0000.TIF` | Filename template table, alongside `DSC_0000.NDF/NEF/JPG` |
| `0x1bf9ec`/`0x1bf9f0` | `JPG\0TIF\0` | Extension name table of the XMP metadata parser |
| `0x11edf40` onward | TIFF/EXIF tag and file parsing table | Reads metadata/file structure, not a pixel encoder |

All remaining hits are false positives:

- The `TIF` at `0x22c9cf` falls inside Thumb code bytes (not a string);
- The `TifO` at `0x34c536` and `0x3a90d8` falls inside JPEG entropy-coded data;
- `0x23de04`, `0xe83d44`, etc. are the `tif` substring inside the word `notify…`.

### 1.1 `DSC_0000.TIF` Is a Platform-Generic Template

This string likewise exists in the firmware of the D810, D850, and D5 (D810 `0x1148f86`, D850
`0x1782618`, D5 `0x15e7010`), and the D810/D850/D5 support `TIFF (RGB)`. It shows that
the DCF filename table of the EXPEED platform retains the `.TIF` extension; **it does not show that the current model can write TIFF**.
The D750's shooting menu uses only the two extensions NEF/JPG.

### 1.2 `JPG/TIF` Belongs to the XMP Parser

Around `0x1bf9ec` there follow `-ATR DTM`, `../DCIM/`, `A:\MISC` in close succession, and further on are
XMP fields such as `dc.Source`, `photoshop`, `Iptc4xmpExt`, `CaptionWriter`. This is the
extension-name and field table for **reading XMP/metadata**, and has nothing to do with "shooting a TIFF."

### 1.3 The TIFF Tag Table Is the EXIF/NEF Metadata Framework

The table starting at `0x11edf40` contains `II*\0` / `MM\0*` files and a large number of TIFF/EXIF tags
(`0x0100`, `0x0101`, `0x0103`, `0x0106`, `0x0111`, `0x0115`, `0x0116`,
`0x0117`, `0x8769`, `0x8825`, `0x9000`, `0x9003`…). A camera must use this framework to read and write EXIF in JPEG/NEF;
what it handles is the **metadata IFD**, not writing 8-bit RGB pixels out as a TIFF
image. The D810 has the same table, and the `II*\0` literal likewise appears only once there, so it cannot serve as
evidence that "a TIFF encoder exists."

---

## 2. Menu-Level Evidence

### 2.1 The D750 Has No TIFF Menu Text

A UTF-16LE scan over the four modules (`tiff_scan.py`):

```
D750 b1010_115a   UTF16 'TIFF'=0    'TIF'=0    'JPEG/TIFF'=0
D810 b920_114     UTF16 'TIFF'=180  'TIF'=180  'JPEG/TIFF'=35
D850 b1330_131    UTF16 'TIFF'=144  'TIF'=144  'JPEG/TIFF'=36
D5   b870_150     UTF16 'TIFF'=144  'TIF'=144  'JPEG/TIFF'=36
```

The D750 has no `TIFF`/`TIF` in the string pools of all 36 languages, and no
`TIFF (RGB)`, `TIFF(RGB)`, `JPEG/TIFF`, or TIFF help text. The D810, D850, and D5 all have
complete menu and help text (for example D810 English `0x6b48d6`, D850 English `0xcf2ab0`).

### 2.2 The D750 Image Quality Menu Has Only 7 Items

The English menu group is at `0x756cc8` (the Japanese group at `0x73c2f2`), and contains:

```
NEF (RAW) + JPEG fine
NEF (RAW) + JPEG normal
NEF (RAW) + JPEG basic
NEF (RAW)
JPEG fine
JPEG normal
JPEG basic
```

There is no 8th item. The menu text is a **contiguous UTF-16 pool packed by language** (no NUL separators), with an offset table
pointing to each label; inserting a new label changes the offsets of every label after it, and all 36 languages would have to be re-laid-out. This is not
something that can be done by changing one byte.

---

## 3. Why "Flipping a Switch" Does Not Work

| Layer | D750 status | What adding TIF requires |
| --- | --- | --- |
| Menu | 7 items, no TIFF text | Insert labels into the 36 language pools and re-lay-out offsets; extend the menu enumeration |
| Settings | Image quality enum is only NEF/JPEG combinations | New enum values, defaults, NVRAM/config persistence |
| Capture pipeline | JPEG encoding + NEF writing | Obtain an 8-bit RGB buffer; write TIFF header, IFD, Strip/compression, EXIF |
| Filesystem | `.TIF` template exists but there is no write path | DCF filenames, directory entries, playback/DPOF/thumbnails |
| Verification | The QEMU prototype only reaches M0 and does not emulate UI/ISP | Must be verified on real hardware; without real hardware there is no way to prove it will not brick |

The key is the **encoder**: the D750's still-image output is JPEG (JFIF) and NEF (RAW with TIFF structure),
and there is no function that "encodes RGB pixels as TIFF." Even if the menu item were made, there would be nothing to write when the shutter is pressed.

The D810 is the same EXPEED 4 generation and supports `TIFF (RGB)`, so in theory it could serve as a porting reference; but the D810 and
the D750 differ in firmware layout, image pipeline, menu data, and hardware, so D810 code blocks cannot be moved directly to the
D750. Porting would require at least: locating the D810's TIFF encoder and call sites, finding the D750's corresponding RGB buffer and
save path, redoing menu/settings/playback, and finally verifying on real hardware. The effort is "feature development," not a "patch."

---

## 4. Recommendations

1. **Do not flash** any image modified for TIF; there is currently no real-hardware verification capability, and the risk far outweighs the benefit.
2. If you only want TIFF files: shoot NEF/JPEG on the D750, and on a computer use dcraw/ImageMagick/
   Lightroom/Capture NX to convert to TIFF; the quality is better than in-camera 8-bit TIFF.
3. If in-camera TIFF is truly wanted: first do a read-only reverse engineering of the D810's `TIFF (RGB)` path, producing
   a porting plan of "encoder address + calling convention + D750 counterpart function," and only then discuss modifying firmware; do not directly generate
   a flashing image.

---

## 5. How to Reproduce

Script: `analysis/tiff_scan.py` (read-only, does not modify firmware)

```powershell
python analysis\tiff_scan.py --quality-group
```

It outputs the UTF-16 `TIFF`/`TIF`/`JPEG/TIFF` counts for the four modules, the D750's 7-item image quality
menu, and all ASCII TIF strings with their offsets.

---

## 6. Boundaries

- This document is a static-analysis conclusion, not a measurement of camera behavior.
- "No TIFF encoder was found" is evidence based on strings, menus, the tag table, and code layout; it is not
  an instruction-by-instruction formal proof over 20 MB of firmware; however, it is sufficient to refute the claim that "changing one switch would enable it."
- Firmware copyright belongs to Nikon; this document contains no firmware binary, only offsets and conclusions.
