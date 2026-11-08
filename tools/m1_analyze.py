#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Provenance: imported from the 2026-11-07 D750 investigation update
# (update_1107.zip); comments are in Chinese.  Kept verbatim so the
# measurements in docs/m1-boot-chain.md stay reproducible.
# -*- coding: utf-8 -*-
"""
d750_m1_analyze.py — D750-QEMU M1 阶段静态分析工具（大肥鱼版）

作用：
  1. stub    追踪 b1010 启动桩（0x9025D700）的 LDR 字面量 / 分支，定位 -> a1010 的交接地址与状态。
  2. table   解析 a1010_011100.bin 的 0x40 字节头 + 157 项偏移表，判定表是 BE 还是 LE。
  3. disasm  在指定文件偏移，用 capstone 以 4 种模式(ARM/Thumb × LE/BE)反汇编，判断真实端序/入口。
  4. refs    在文件里按 BE/LE 搜索 32 位值，找引用点。
  5. verdict 综合判定：表端序 + 候选入口的“可解读度”打分。

依赖：disasm/verdict 需要 capstone（pip install capstone）；其余仅标准库。

示例（Windows，路径按你机器改）：
  python d750_m1_analyze.py stub   "D750_0115.dec.modules\\b1010_115a.bin" 0x25D700 --n 16
  python d750_m1_analyze.py table  "D750_0115.dec.modules\\a1010_011100.bin"
  python d750_m1_analyze.py disasm "D750_0115.dec.modules\\a1010_011100.bin" 0x2CB4C --base 0x10000000 --n 24
  python d750_m1_analyze.py refs   "D750_0115.dec.modules\\a1010_011100.bin" 0x2CB8C 0x2CB4C 0xC2D1
  python d750_m1_analyze.py verdict "D750_0115.dec.modules\\a1010_011100.bin" 0x2CB4C 0x2CB8C
"""
import sys
import struct
import argparse


def load(path):
    with open(path, "rb") as f:
        return f.read()


def u32le(d, o):
    return struct.unpack_from("<I", d, o)[0]


def u32be(d, o):
    return struct.unpack_from(">I", d, o)[0]


def sx(v, bits):
    m = 1 << (bits - 1)
    return (v ^ m) - m


# ---------------- ARM 子集解码（只覆盖桩里用到的类型） ----------------
def decode_arm(ins, addr):
    # LDR Rt,[pc,#imm12]（字面量加载）
    if (ins & 0x0F7F0000) == 0x051F0000 and (ins & (1 << 20)):
        rt = (ins >> 12) & 0xF
        imm = ins & 0xFFF
        return ("ldr_lit", rt, (addr + 8 + imm) & 0xFFFFFFFF)
    if (ins & 0x0FFFFFF0) == 0x012FFF30:
        return ("blx_reg", ins & 0xF)
    if (ins & 0x0FFFFFF0) == 0x012FFF10:
        return ("bx", ins & 0xF)
    if (ins & 0x0F000000) == 0x0B000000:
        return ("bl", (addr + 8 + (sx(ins & 0xFFFFFF, 24) << 2)) & 0xFFFFFFFF)
    if (ins & 0x0F000000) == 0x0A000000:
        return ("b", (addr + 8 + (sx(ins & 0xFFFFFF, 24) << 2)) & 0xFFFFFFFF)
    if (ins & 0x0F000010) == 0x0E000010:
        return ("mrc" if (ins & (1 << 20)) else "mcr", ins & 0x0FFFFFFF)
    return ("other", ins)


def cmd_stub(path, off, n):
    d = load(path)
    print("# 启动桩追踪  file=%s  start=0x%X  (%d 条)" % (path, off, n))
    a = off
    last = None
    for _ in range(n):
        if a + 4 > len(d):
            break
        ins = u32le(d, a)
        k = decode_arm(ins, a)
        tag = ""
        if k[0] == "ldr_lit":
            rt, lit = k[1], k[2]
            val = u32le(d, lit) if lit + 4 <= len(d) else None
            tag = "  ; LDR r%d <- *0x%X = %s" % (rt, lit, ("0x%08X" % val) if val is not None else "OOB")
            last = ("ldr_lit", rt, val)
        elif k[0] in ("bl", "b"):
            tag = "  ; %s 0x%08X" % (k[0].upper(), k[1])
        elif k[0] == "blx_reg":
            tag = "  ; BLX r%d" % k[1]
        elif k[0] == "bx":
            tag = "  ; BX r%d" % k[1]
            if k[1] == 12 and last and last[0] == "ldr_lit" and last[1] == 12:
                tgt = last[2]
                print("      -> BX ip = 0x%08X，bit0=%d ⇒ 进入 %s 态" %
                      (tgt, tgt & 1, "Thumb" if (tgt & 1) else "ARM"))
        elif k[0] in ("mrc", "mcr"):
            tag = "  ; cp15 %s" % k[0].upper()
        print("  0x%08X  %08X%s" % (a, ins, tag))
        a += 4


def parse_table(d):
    n = len(d)
    entries = []
    o = 0x40
    while o + 4 <= 0x2B4 and o + 4 <= n:
        entries.append(u32be(d, o))
        o += 4
    return entries


def cmd_table(path):
    d = load(path)
    n = len(d)
    print("# a1010 头部 0x00-0x40  file=%s  size=0x%X (%d)" % (path, n, n))
    for o in range(0, 0x40, 4):
        print("  0x%03X  BE=0x%08X  LE=0x%08X" % (o, u32be(d, o), u32le(d, o)))
    entries = parse_table(d)
    print("\n# 偏移表 0x40..0x2B3（按 4 字节大端解）")
    print("  条目数 = %d" % len(entries))

    def cls(v):
        if v == 0xC2D1:
            return "0xC2D1(default)"
        if 0x10000 <= v < 0x20000:
            return "0x14xxx(code)"
        if v < n:
            return "in-file"
        return "OOB"

    from collections import Counter
    c = Counter(cls(v) for v in entries)
    for k, v in c.most_common():
        print("    %-16s x%d" % (k, v))
    print("  前 12 项: " + ", ".join("0x%X" % v for v in entries[:12]))
    print("  后 8 项:  " + ", ".join("0x%X" % v for v in entries[-8:]))
    be_ok = sum(1 for v in entries if 0 < v < n)
    le_ok = sum(1 for o2 in range(0x40, 0x40 + len(entries) * 4, 4) if 0 < u32le(d, o2) < n)
    verdict = "BIG-ENDIAN" if be_ok >= le_ok else "LITTLE-ENDIAN"
    print("\n# 端序判定：BE 合法率=%d/%d  LE 合法率=%d/%d  => 表应为 %s"
          % (be_ok, len(entries), le_ok, len(entries), verdict))


def _modes():
    from capstone import (CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB, CS_MODE_BIG_ENDIAN)
    return [("ARM-LE", CS_MODE_ARM), ("THUMB-LE", CS_MODE_THUMB),
            ("ARM-BE", CS_MODE_ARM | CS_MODE_BIG_ENDIAN),
            ("THUMB-BE", CS_MODE_THUMB | CS_MODE_BIG_ENDIAN)]


def cmd_disasm(path, off, base, n):
    try:
        from capstone import Cs, CS_ARCH_ARM
    except Exception as e:
        print("需要 capstone: pip install capstone  (%s)" % e)
        return
    d = load(path)
    code = d[off:off + 0x400]
    va = base + off
    for name, m in _modes():
        print("\n--- %s  (file 0x%X -> VA 0x%X) ---" % (name, off, va))
        md = Cs(CS_ARCH_ARM, m)
        cnt = 0
        for ins in md.disasm(code, va):
            print("  0x%08X  %-8s %s" % (ins.address, ins.mnemonic, ins.op_str))
            cnt += 1
            if cnt >= n:
                break
        if cnt == 0:
            print("   <无法解出指令>")


def cmd_refs(path, values):
    d = load(path)
    print("# 引用搜索 file=%s size=0x%X" % (path, len(d)))
    for v in values:
        for endian, pack in (("BE", struct.pack(">I", v)), ("LE", struct.pack("<I", v))):
            hits, i = [], 0
            while True:
                j = d.find(pack, i)
                if j < 0:
                    break
                hits.append(j)
                i = j + 1
            print("  value 0x%X [%s] -> %d 处 %s" % (v, endian, len(hits), [hex(x) for x in hits[:12]]))


def cmd_verdict(path, offs):
    print("=== a1010 入口/端序判定 ===")
    cmd_table(path)
    try:
        from capstone import Cs, CS_ARCH_ARM
    except Exception:
        print("\n(无 capstone，跳过反汇编打分)")
        return
    d = load(path)

    def score(off, m):
        md = Cs(CS_ARCH_ARM, m)
        good = total = rep = 0
        prev = None
        for ins in md.disasm(d[off:off + 0x100], off):
            total += 1
            if ins.mnemonic not in ("udf", "undefined", "svc", "andeq", ".word"):
                good += 1
            if ins.mnemonic == prev:
                rep += 1
            prev = ins.mnemonic
        return good, total, rep

    for off in offs:
        print("\n@ file 0x%X:" % off)
        for name, m in _modes():
            g, t, r = score(off, m)
            print("   %-9s 可解读 %d/%d, 连续同指令 %d" % (name, g, t, r))


def main():
    ap = argparse.ArgumentParser(description="D750-QEMU M1 静态分析")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("stub"); p.add_argument("file"); p.add_argument("off", type=lambda x: int(x, 0)); p.add_argument("--n", type=int, default=16)
    p = sub.add_parser("table"); p.add_argument("file")
    p = sub.add_parser("disasm"); p.add_argument("file"); p.add_argument("off", type=lambda x: int(x, 0)); p.add_argument("--base", type=lambda x: int(x, 0), default=0x10000000); p.add_argument("--n", type=int, default=20)
    p = sub.add_parser("refs"); p.add_argument("file"); p.add_argument("values", nargs="+", type=lambda x: int(x, 0))
    p = sub.add_parser("verdict"); p.add_argument("file"); p.add_argument("offs", nargs="+", type=lambda x: int(x, 0))

    a = ap.parse_args()
    if a.cmd == "stub":
        cmd_stub(a.file, a.off, a.n)
    elif a.cmd == "table":
        cmd_table(a.file)
    elif a.cmd == "disasm":
        cmd_disasm(a.file, a.off, a.base, a.n)
    elif a.cmd == "refs":
        cmd_refs(a.file, a.values)
    elif a.cmd == "verdict":
        cmd_verdict(a.file, a.offs)


if __name__ == "__main__":
    main()
