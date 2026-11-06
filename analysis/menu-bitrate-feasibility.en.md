# Adding a Third Bit-rate Item to the D750 Movie Menu: Feasibility

Date: 2026-11-06

Target: Nikon D750, firmware `D750_0115`, main module `b1010_115a.bin`

Scope: **read-only static analysis; no firmware was generated or flashed.**

## Conclusion

**Adding a genuine third "64 Mbps" item under Movie quality is not a safe
static patch with the current evidence.** The blocker is the menu layer, not
the bit-rate table:

1. Menu text is a packed UTF-16 pool per language with no NUL separators.
   Inserting a label shifts every following label in that language.
2. Several u32 offset tables exist, but they resolve to substrings/sorted
   indexes (they point into the middle of strings in tests), not to an
   editable "menu item array". No two-to-three-item menu descriptor was found.
3. `APPMENU` near `0x10CDA0` is an event/command dispatcher, not a pure data
   menu table. A new item also needs a new enum value, settings persistence,
   and UI layout.
4. The QEMU prototype stops at M0 and does not model the UI, so it cannot
   verify that a new item displays, is selectable, or survives a reboot.

This analysis therefore did not modify firmware. The smallest deliverable is
to reuse the existing two Movie quality slots (see §3); it is not a third item,
but it gives a menu-selectable choice.

## 1. Confirmed menu labels

English Movie quality group:

| Offset | Label | Length |
| --- | --- | --- |
| `0x75765A` | `Movie quality` | 13 chars / 26 B |
| `0x757674` | `High quality` | 12 chars / 24 B |
| `0x75768C` | `Normal` | 6 chars / 12 B |

Simplified Chinese group:

| Offset | Label | Length |
| --- | --- | --- |
| `0x8870D8` | `动画品质` | 4 chars / 8 B |
| `0x8870E0` | `高品质` | 3 chars / 6 B |
| `0x8870E6` | `标准` | 2 chars / 4 B |

The labels are adjacent with no NUL. A **same-length** replacement (for
example `Normal` -> `64Mbps`) does not move later labels and is the lowest-risk
text edit. Inserting a new label requires re-laying out that language's offset
table, for all 36 languages.

## 2. Why no directly extendable menu table was found

Attempts:

- searching absolute pointers `0x756CC8` / `0x90756CC8` / `0x75765A`: zero hits;
- searching contiguous 16/32-bit relative-offset arrays: many hits, but most
  candidate tables resolve into the middle of strings when a base is applied;
  they are substring/sorted indexes, not menu item arrays;
- searching for the exact triplet "Movie quality / High quality / Normal":
  no candidate table with a valid base points at all three label starts;
- disassembling around `APPMENU`: it is a `cmp/branch` dispatcher over event
  IDs, not a static "count + item pointers" menu table.

The menu layer therefore has at least one runtime construction/lookup step.
Without a UI-capable emulator or a real camera, editing candidate tables risks
a shifted, blank, or crashing menu.

### 2.1 Further search (2026-11-06)

Several u32 tables have their first two entries exactly at `High quality` /
`Normal` for a trial base:

| Table offset | Trial base | Observation |
| --- | --- | --- |
| `0xB2BA74` | `0x72F400` | first two point at `0x757674/0x75768C`; third falls inside a string |
| `0xC295B0` | `0x72E400` | first two hit; later entries fall inside `NowChoose...` |
| `0xC55F1C` | `0x74C800` | first two hit; later entries fall inside `sensitivity...` |

These look like **sorted/substring indexes**: only the adjacent pair happens to
coincide with label boundaries, and the next entry points into the middle of a
word. They cannot be extended as a menu item array. Larger u32 tables such as
`0x1CEA1C` behave the same way, pointing at `0x75739E`, `0x7571AA`, etc.

The conclusion is unchanged: **no safely extendable Movie quality menu
descriptor was found**. The next step needs dynamic evidence (see §4).

## 3. Smallest feasible menu variant (reuse two slots)

Turn the existing two Movie quality slots into:

| Menu item | Bit-rate rows | Behaviour |
| --- | --- | --- |
| `64 Mbps HQ` (Chinese `64M`) | 1080p HQ rows 1/3/5/7/9 | `64/60` Mbps |
| `Stock` (Chinese `原厂`) | 1080p NQ rows 2/4/6/8 | stock HQ: `42/35`, `42/35`, `24/20`, `24/20` |

Same-length labels:

- English: `High quality` (12) -> `64 Mbps HQ  ` (12, two trailing spaces);
  `Normal` (6) -> `Stock ` (6, one trailing space).
- Chinese: `高品质` (3) -> `64M` (3); `标准` (2) -> `原厂` (2).

This changes only two English labels, two Chinese labels, five HQ rows, four
NQ rows, and the container CRC/encryption (handled by the repack tool). It is
**not** a third item: the old Normal low-bit-rate slot is consumed. Its
advantage is a real menu-selectable "64 Mbps / Stock" choice with no menu
descriptor changes.

> This smallest variant was implemented locally and statically/container
> verified; artifacts are in `D750_0115.menu64.out/` (not published in this
> repository); see its `REPORT.md`.

## 4. A genuine third item would require

1. Locating the Movie quality menu descriptor: item count, text IDs/offsets,
   and the settings enum.
2. Confirming settings persistence (NVRAM/config) and whether the UI indexes
   by enum value.
3. Appending labels to English, Chinese, and the other 34 language pools and
   re-laying out all their offsets.
4. Adding a third branch in the bit-rate selection logic, mapped to a new set
   of 1080p rows.
5. Real-hardware validation: menu display, selection, reboot persistence,
   recorded bit rate, playback, and factory reset.
6. Without hardware, at least a QEMU run that reaches the UI and dumps the
   menu; the current prototype cannot do that.

Step 1 is the current blocker. Do not generate a "third item" image before the
descriptor is found.

### 4.1 Dynamic evidence needed

Static table search has reached its limit. The next step requires one of:

1. **Real camera/debugger**: break on reads near `0x75765A` while the Movie
   quality menu is open; log the caller, access width, and following index to
   recover the real item count/array.
2. **A UI-capable emulator**: the current `nikon-d750` machine stops at M0 and
   has no UI/display/input services; boot-next-stage work would be required.
3. **Same-generation comparison**: D810/D850 have more menu items; locating
   their equivalent descriptor could reveal the format. Not done yet.

Until one of these exists, editing a candidate table is guesswork and must not
produce a flashable image.

## 5. Boundaries

- Static conclusions, not a camera UI test.
- "Menu descriptor not found" is a negative result within the current search
  scope, not a proof that none exists; it is enough to reject a one-byte patch.
- No firmware was generated, repacked, or flashed.
