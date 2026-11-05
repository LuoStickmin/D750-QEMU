# SPDX-License-Identifier: GPL-2.0-or-later
"""Static inspection of a decrypted D750 module.

The tool does not disassemble the whole image and does not claim to recover
the firmware's control flow.  It extracts the facts the validation prototype
depends on and *checks the profile constants against the actual bytes*:

  * sizes and SHA-256 of the supplied modules;
  * the exception-vector table at offset 0 and its literals;
  * whether the vector's reset literal points at ARM code or at data;
  * the presence of the MMU page-table literal and the entry literal;
  * a coarse pointer census (flash / peripheral / RAM windows);
  * per-64-KiB ARM/Thumb instruction-shape scores.

Usage:
    python tools/fwscan.py --main b1010_115a.bin --flash a1010_011100.bin \
        --out analysis/d750-0115.json
"""
from __future__ import annotations

import argparse
import array
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

TOOL_VERSION = "1.0"

# Profile constants are hypotheses.  They are checked, not assumed silently.
PROFILE = {
    "name": "nikon-d750-0115",
    "cpu": "cortex-a9",
    "ram_base": 0x90000000,
    "flash_base": 0x10000000,
    "entry": 0x9027D52C,
    "vector_reset": 0x9027D524,
    "page_table": 0x90020000,
    "uart_base": 0x80005010,
}
DEFAULT_ENTRY_OFFSET = PROFILE["entry"] - PROFILE["ram_base"]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def words(data: bytes) -> array.array:
    padded = data[: len(data) // 4 * 4]
    arr = array.array("I")
    arr.frombytes(padded)
    if sys.byteorder != "little":
        arr.byteswap()
    return arr


def entropy_bits(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    total = len(data)
    return -sum((n / total) * math.log2(n / total) for n in counts.values())


def arm_cond(word: int) -> int:
    return (word >> 28) & 0xF


def arm_prologue_score(word: int) -> int:
    if word & 0xFFFF0000 == 0xE92D0000:       # push {.., lr}
        return 4
    if word & 0xFFFFF000 == 0xE52D0000:       # str lr, [sp, #-4]!
        return 4
    if word & 0x0F000000 == 0x0A000000:       # b
        return 2
    if word & 0x0F000000 == 0x0B000000:       # bl
        return 2
    if word & 0xFFFF0000 == 0xE59F0000:       # ldr rd, [pc, #imm]
        return 2
    if word & 0xFFFF0000 == 0xE1A00000:       # mov
        return 2
    if word & 0xFFFFF000 == 0xE28F0000:       # add rd, pc, #imm
        return 2
    if word & 0xFFFF0000 == 0xE3500000:       # cmp r0, #imm
        return 1
    return 0


def thumb_scores(block: bytes) -> tuple[int, int]:
    """Return (push/pop/bx hits, u32-prefix hits) for a 2-byte view."""
    n = len(block) // 2
    arr = array.array("H")
    arr.frombytes(block[: n * 2])
    if sys.byteorder != "little":
        arr.byteswap()
    pops = sum(1 for h in arr if h & 0xFF00 in (0xB500, 0xBD00) or h == 0x4770)
    u32 = sum(1 for h in arr if 0xE800 <= h <= 0xEFFF)
    return pops, u32


def vector_table(data: bytes, base: int) -> dict:
    if len(data) < 0x40:
        return {"present": False, "reason": "image shorter than 0x40"}
    w = [int(x) for x in words(data)[:16]]
    vectors = []
    for i in range(8):
        insn = w[i]
        lit = w[8 + i]
        vectors.append({
            "index": i,
            "insn": f"0x{insn:08X}",
            "is_ldr_pc": (insn & 0xFFFF0000) == 0xE59F0000,
            "literal": f"0x{lit:08X}" if lit else None,
            "literal_addr": lit if lit else None,
            "target_in_image": bool(lit and base <= lit < base + len(data)),
            "target_file_offset": (lit - base) if lit else None,
        })
    shape = sum(1 for v in vectors if v["is_ldr_pc"])
    return {"present": shape >= 5, "ldr_pc_entries": shape, "vectors": vectors}


def check_target(data: bytes, addr: int, base: int) -> dict:
    off = addr - base
    if not (0 <= off <= len(data) - 8):
        return {"addr": f"0x{addr:08X}", "mapped": False}
    w = [int(x) for x in words(data)[off // 4: off // 4 + 2]]
    return {
        "addr": f"0x{addr:08X}",
        "mapped": True,
        "file_offset": f"0x{off:06X}",
        "word0": f"0x{w[0]:08X}",
        "word1": f"0x{w[1]:08X}",
        "arm_cond_word0": arm_cond(w[0]),
        "looks_like_arm_code": arm_cond(w[0]) == 0xE,
        "prologue_score": arm_prologue_score(w[0]),
    }


def code_blocks(data: bytes, limit: int = 8) -> list[dict]:
    rows = []
    for off in range(0, len(data) - 0x10000 + 1, 0x10000):
        block = data[off: off + 0x10000]
        w = words(block)
        arm = sum(1 for x in w if arm_cond(int(x)) == 0xE)
        pops, u32 = thumb_scores(block)
        score = arm + pops + u32
        rows.append({"offset": f"0x{off:06X}", "arm_al": arm,
                     "thumb_push_pop": pops, "thumb32_prefix": u32,
                     "score": score})
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows[:limit]


def pointer_census(w: array.array) -> dict:
    ranges = {
        "flash_0x10000000": (0x10000000, 0x10800000),
        "periph_0x80000000": (0x80000000, 0x90000000),
        "ram_0x90000000": (0x90000000, 0x91000000),
        "ram_high_0x91000000": (0x91000000, 0x92000000),
        "external_0x40000000": (0x40000000, 0x60000000),
        "external_0xA0000000": (0xA0000000, 0xB0000000),
    }
    out = {}
    for name, (lo, hi) in ranges.items():
        out[name] = sum(1 for x in w if lo <= x < hi)
    return out


def count_literal(w: array.array, value: int) -> int:
    return sum(1 for x in w if x == value)


def mmu_sites(w: array.array) -> list[str]:
    """Offsets of 'mcr p15,0,rX,c1,c0,0' (SCTLR writes)."""
    sites = []
    for i, x in enumerate(w):
        if (x & 0xFFFF0FFF) == 0xEE010F10:
            sites.append(f"0x{i * 4:06X}")
    return sites


def scan_main(path: Path, base: int) -> dict:
    data = path.read_bytes()
    w = words(data)
    vt = vector_table(data, base)
    reset = vt["vectors"][0]["literal_addr"] if vt["present"] else None
    reset_check = check_target(data, reset, base) if reset else None
    entry = base + DEFAULT_ENTRY_OFFSET
    entry_check = check_target(data, entry, base)
    flash_refs = [x for x in w if 0x10000000 <= x < 0x10800000]

    checks = []
    checks.append({
        "name": "vector_table_shape",
        "ok": vt["present"],
        "detail": f"{vt.get('ldr_pc_entries', 0)}/8 ldr-pc entries",
    })
    if reset_check and reset_check.get("mapped"):
        checks.append({
            "name": "vector_reset_points_at_code",
            "ok": bool(reset_check["looks_like_arm_code"]),
            "detail": (f"0x{reset:08X} -> {reset_check['word0']} "
                       f"(ARM cond 0x{reset_check['arm_cond_word0']:X}); "
                       "not AL-condition ARM code" if not reset_check["looks_like_arm_code"]
                       else f"0x{reset:08X} looks like ARM code"),
        })
    checks.append({
        "name": "entry_hypothesis_is_arm",
        "ok": bool(entry_check.get("looks_like_arm_code")),
        "detail": f"0x{entry:08X} -> {entry_check.get('word0')}",
    })
    checks.append({
        "name": "page_table_literal_present",
        "ok": count_literal(w, PROFILE["page_table"]) > 0,
        "detail": f"{count_literal(w, PROFILE['page_table'])} occurrence(s) "
                  f"of 0x{PROFILE['page_table']:08X}",
    })
    checks.append({
        "name": "entry_literal_present",
        "ok": count_literal(w, entry) > 0,
        "detail": f"{count_literal(w, entry)} occurrence(s) of 0x{entry:08X}",
    })

    return {
        "path": str(path),
        "size": len(data),
        "sha256": sha256_file(path),
        "entropy_bits": round(entropy_bits(data), 3),
        "zero_pct": round(100.0 * data.count(0) / len(data), 2),
        "ff_pct": round(100.0 * data.count(0xFF) / len(data), 2),
        "vector_table": vt,
        "vector_reset_target": reset_check,
        "entry_hypothesis": entry_check,
        "page_table_literal_count": count_literal(w, PROFILE["page_table"]),
        "entry_literal_count": count_literal(w, entry),
        "pointer_census": pointer_census(w),
        "flash_pointer_count": len(flash_refs),
        "flash_pointer_min": f"0x{min(flash_refs):08X}" if flash_refs else None,
        "flash_pointer_max": f"0x{max(flash_refs):08X}" if flash_refs else None,
        "mmu_sctlr_sites": mmu_sites(w),
        "code_blocks": code_blocks(data),
        "checks": checks,
    }


def scan_flash(path: Path | None, base: int) -> dict | None:
    if path is None:
        return None
    data = path.read_bytes()
    w = words(data)
    return {
        "path": str(path),
        "size": len(data),
        "sha256": sha256_file(path),
        "entropy_bits": round(entropy_bits(data), 3),
        "executable_shapes": code_blocks(data, limit=4),
        "pointer_census": pointer_census(w),
        "vector_table": vector_table(data, base),
    }


def build_report(main: Path, flash: Path | None, base: int) -> dict:
    main_info = scan_main(main, base)
    flash_info = scan_flash(flash, PROFILE["flash_base"])
    checks = list(main_info["checks"])
    if flash_info is not None:
        in_range = sum(
            1 for x in words(main.read_bytes())
            if PROFILE["flash_base"] <= x < PROFILE["flash_base"] + flash_info["size"]
        )
        checks.append({
            "name": "flash_refs_fit_flash_image",
            "ok": in_range > 0,
            "detail": f"{in_range} of {main_info['flash_pointer_count']} "
                      "0x10xxxxxx words fall inside the supplied flash image",
        })
    ok = all(c["ok"] for c in checks)
    return {
        "tool": "d750-fwscan",
        "version": TOOL_VERSION,
        "profile": PROFILE,
        "main": main_info,
        "flash": flash_info,
        "checks": checks,
        "verdict": "profile-consistent" if ok else "profile-has-warnings",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--main", type=Path, required=True,
                        help="decrypted main module (b1010_*.bin)")
    parser.add_argument("--flash", type=Path,
                        help="decrypted first-stage module (a1010_*.bin)")
    parser.add_argument("--out", type=Path,
                        help="write the JSON report here")
    parser.add_argument("--base", type=lambda s: int(s, 0),
                        default=PROFILE["ram_base"])
    args = parser.parse_args(argv)

    report = build_report(args.main, args.flash, args.base)
    print(f"main   {args.main}  {report['main']['size']} bytes")
    print(f"       sha256 {report['main']['sha256']}")
    print(f"       entropy {report['main']['entropy_bits']} bits, "
          f"{report['main']['zero_pct']}% zero, {report['main']['ff_pct']}% 0xFF")
    vt = report["main"]["vector_table"]
    print(f"vectors {vt.get('ldr_pc_entries', 0)}/8 ldr-pc entries")
    for v in vt["vectors"]:
        print(f"       [{v['index']}] {v['insn']} -> {v['literal']} "
              f"in_image={v['target_in_image']}")
    print(f"entry  0x{report['profile']['entry']:08X}: "
          f"{report['main']['entry_hypothesis'].get('word0')}")
    print(f"mmu    SCTLR sites: {', '.join(report['main']['mmu_sctlr_sites'][:8])}")
    print("checks:")
    for c in report["checks"]:
        print(f"  [{'ok ' if c['ok'] else 'WARN'}] {c['name']}: {c['detail']}")
    print(f"verdict: {report['verdict']}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.out}")
    return 0 if report["verdict"] == "profile-consistent" else 1


if __name__ == "__main__":
    sys.exit(main())
