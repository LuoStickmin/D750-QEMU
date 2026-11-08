#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Provenance: imported from the 2026-11-07 D750 investigation update
# (update_1107.zip); comments are in Chinese.  Kept verbatim so the
# measurements in docs/m1-boot-chain.md stay reproducible.
# -*- coding: utf-8 -*-
"""
stub_trace.py — D750 启动桩「无 QEMU」单步模拟器（大肥鱼版，零依赖）

不用编译 QEMU、不用 MSYS2，纯 Python 单步模拟 b1010 的 ARM 启动桩
(0x9025D700)，一直跑到 `BX ip -> a1010`，把"到底进不进得去 a1010、
进哪个文件偏移、什么模式(ARM/Thumb)"动态定下来。

用法（Windows，路径按你机器改）：
  python stub_trace.py --b1010 D750_0115.dec.modules\\b1010_115a.bin \
                       --a1010 D750_0115.dec.modules\\a1010_011100.bin
  # 换基址：看是不是要 +0x40
  python stub_trace.py --b1010 ... --a1010 ... --a1010-base 0x10000040
  # 有整片 flash（0x10000000 起）→ 用它填 config 槽 0x100F48C0/C8
  python stub_trace.py --b1010 ... --a1010 ... --flash full_flash.bin
  # 模拟 QEMU 未映射默认读 0xFF（会暴露 blxne 跑飞）
  python stub_trace.py ... --unmapped 0xFF

覆盖的 ARM 指令子集（够跑启动桩 + 常见 init）：
  LDR/STR/LDRB/STRB、LDM/STM(含 PUSH/POP)、
  MOV/MOVW/MOVT/ADD/SUB/AND/ORR/EOR/BIC/MVN/CMP/TST…、
  B/BL、BX/BLX(寄存器)、MRC/MCR(p15 SCTLR)。
遇到没实现的指令会停下并打印该 32 位编码，方便补。

注意：默认 --skip-init 0x9025DA40 —— 把桩里对 init 的 BL 直接"跨过"（init 只做
硬件初始化，不会改变后面的 BX 目标，所以跳过它仍能准确判定 bx 去向）。若想看 init
内部，用 --skip-init 0 关掉。
"""
import argparse
import struct

# ---------------- 内存模型 ----------------
class Memory:
    def __init__(self, unmapped_fill=0):
        self.regions = []            # dicts: base,data,writable
        self.fill = unmapped_fill & 0xFF

    def add(self, base, data, writable=False):
        self.regions.append({"base": base, "data": bytearray(data), "wr": writable})

    def _find(self, addr):
        for r in self.regions:
            if r["base"] <= addr < r["base"] + len(r["data"]):
                return r
        return None

    def read32(self, addr):
        addr &= 0xFFFFFFFF
        r = self._find(addr)
        if r is None:
            return (self.fill * 0x01010101) & 0xFFFFFFFF
        o = addr - r["base"]
        d = r["data"]
        if o + 4 <= len(d):
            return struct.unpack_from("<I", d, o)[0]
        v = 0
        for k in range(4):
            a = (addr + k) & 0xFFFFFFFF
            rr = self._find(a)
            b = self.fill if rr is None else rr["data"][a - rr["base"]]
            v |= b << (8 * k)
        return v & 0xFFFFFFFF

    def write32(self, addr, val):
        addr &= 0xFFFFFFFF
        r = self._find(addr)
        if r is None or not r["wr"]:
            return False
        o = addr - r["base"]
        d = r["data"]
        if o + 4 <= len(d):
            struct.pack_into("<I", d, o, val & 0xFFFFFFFF)
            return True
        return False


def sx(v, bits):
    m = 1 << (bits - 1)
    return (v ^ m) - m


class Cpu:
    def __init__(self):
        self.v = 0x1D3            # SVC, I/F 屏蔽, T=0(ARM)
        self.sctlr = 0x00C50078


# ---------------- ARM 单步（子集，已按参考实现测通） ----------------
def step_arm(R, C, mem):
    """返回 (mnemonic, next_pc, branch_target_or_None, cond_ok)"""
    addr = R[15] & 0xFFFFFFFF
    ins = mem.read32(addr)
    nxt = (addr + 4) & 0xFFFFFFFF
    cond = (ins >> 28) & 0xF
    Z = bool(C.v & 0x40000000)
    take = True if cond == 0xE else (Z if cond == 0x0 else ((not Z) if cond == 0x1 else True))

    def reg(n):
        return (addr + 8) & 0xFFFFFFFF if n == 15 else R[n]

    mn = ""
    branch = None

    # ---- LDM / STM（块访存，含 PUSH/POP）----
    if (ins & 0x0E000000) == 0x08000000:
        P = bool(ins & (1 << 24)); U = bool(ins & (1 << 23))
        W = bool(ins & (1 << 21)); L = bool(ins & (1 << 20))
        rn = (ins >> 16) & 0xF; lst = ins & 0xFFFF
        mn = ("ldm" if L else "stm") + " r%d" % rn
        if take:
            cnt = sum(1 for i in range(16) if lst & (1 << i))
            base = (addr + 8) & 0xFFFFFFFF if rn == 15 else (R[rn] & 0xFFFFFFFF)
            adr = (base + 4) if (U and P) else (base if (U and not P) else base - 4 * cnt)
            if W or not P:
                R[rn] = (base + 4 * cnt) if U else (base - 4 * cnt)
            for i in range(16):
                if lst & (1 << i):
                    if L:
                        R[i] = mem.read32(adr)
                    else:
                        mem.write32(adr, R[i])
                    adr += 4
            if L and (lst & 0x8000):
                branch = R[15] & 0xFFFFFFFF

    # ---- 单数据访存 LDR/STR/LDRB/STRB（含 PC 相对字面量）----
    elif (ins & 0x0C000000) == 0x04000000:
        I = bool(ins & (1 << 25)); P = bool(ins & (1 << 24)); U = bool(ins & (1 << 23))
        Bb = bool(ins & (1 << 22)); W = bool(ins & (1 << 21)); L = bool(ins & (1 << 20))
        rn = (ins >> 16) & 0xF; rt = (ins >> 12) & 0xF
        mn = ("ldr" if L else "str") + ("b" if Bb else "") + " r%d" % rt
        if take:
            off = (ins & 0xFF) if I else (ins & 0xFFF)
            base = (addr + 8) & 0xFFFFFFFF if rn == 15 else (R[rn] & 0xFFFFFFFF)
            eff = (base + off if U else base - off) if P else base
            if Bb:
                if L:
                    R[rt] = mem.read32(eff) & 0xFF
                else:
                    mem.write32(eff, R[rt] & 0xFF)
            else:
                if L:
                    R[rt] = mem.read32(eff)
                else:
                    mem.write32(eff, R[rt])
            if (not P) or W:
                R[rn] = (base + off if U else base - off) & 0xFFFFFFFF

    # ---- B / BL ----
    elif (ins & 0x0E000000) == 0x0A000000:
        L = bool(ins & (1 << 24))
        tgt = (addr + 8 + (sx(ins & 0xFFFFFF, 24) << 2)) & 0xFFFFFFFF
        mn = ("bl" if L else "b")
        if take:
            if L:
                R[14] = nxt
            branch = tgt

    # ---- BX / BLX（寄存器）—— 必须在数据处理之前判定 ----
    elif ((ins & 0x0FFFFFF0) == 0x012FFF10) or ((ins & 0x0FFFFFF0) == 0x012FFF30):
        rm = ins & 0xF
        tgt = R[rm] & 0xFFFFFFFF
        is_blx = (ins & 0x0FFFFFF0) == 0x012FFF30
        mn = ("blx" if is_blx else "bx") + " r%d -> 0x%X" % (rm, tgt)
        if take:
            if is_blx:
                R[14] = nxt
            if tgt & 1:
                C.v |= 0x20
            else:
                C.v &= ~0x20
            branch = tgt & ~1

    # ---- MRC / MCR p15 ----
    elif (ins & 0x0F000010) == 0x0E000010:
        to_c = not bool(ins & (1 << 20))
        rt = (ins >> 12) & 0xF
        mn = ("mcr" if to_c else "mrc") + " p15"
        if take:
            if ((ins >> 16) & 0xF) == 1 and (ins & 0xF) == 0:   # c1,c0 = SCTLR
                if to_c:
                    C.sctlr = R[rt] & 0xFFFFFFFF
                else:
                    R[rt] = C.sctlr

    # ---- MOVW / MOVT ----
    elif (ins & 0x0FF00000) == 0x03000000:      # MOVW
        rd = (ins >> 12) & 0xF
        imm16 = (((ins >> 4) & 0xF000) | (ins & 0xFFF)) & 0xFFFF
        mn = "movw r%d,#0x%X" % (rd, imm16)
        if take:
            R[rd] = imm16
    elif (ins & 0x0FF00000) == 0x03400000:      # MOVT
        rd = (ins >> 12) & 0xF
        imm16 = (((ins >> 4) & 0xF000) | (ins & 0xFFF)) & 0xFFFF
        mn = "movt r%d,#0x%X" % (rd, imm16)
        if take:
            R[rd] = (R[rd] & 0xFFFF) | (imm16 << 16)

    # ---- 数据处理 ----
    elif (ins & 0x0C000000) == 0x00000000:
        op = (ins >> 21) & 0xF
        I = bool(ins & (1 << 25))
        rn = (ins >> 16) & 0xF
        rd = (ins >> 12) & 0xF
        if I:
            op2 = ins & 0xFF
            rot = ((ins >> 8) & 0xF) * 2
            if rot:
                op2 = ((op2 >> rot) | (op2 << (32 - rot))) & 0xFF
        else:
            op2 = reg(ins & 0xF)
            if not (ins & 0x10):     # 立即数移位
                sh = (ins >> 7) & 0x1F
                typ = (ins >> 5) & 0x3
                if typ == 0:                       # LSL
                    op2 = (op2 << sh) & 0xFFFFFFFF
                elif typ == 1:                      # LSR
                    op2 = (op2 >> (sh if sh else 32)) & 0xFFFFFFFF
                elif typ == 2:                      # ASR
                    op2 = (sx(op2, 32) >> (sh if sh else 32)) & 0xFFFFFFFF
                else:                               # ROR
                    if sh:
                        op2 = ((op2 >> sh) | (op2 << (32 - sh))) & 0xFFFFFFFF
        a = reg(rn)
        if take:
            if op == 0xD:
                R[rd] = op2 & 0xFFFFFFFF; mn = "mov r%d,#0x%X" % (rd, op2)
            elif op == 0xF:
                R[rd] = (~op2) & 0xFFFFFFFF; mn = "mvn"
            elif op == 0xC:
                R[rd] = (a | op2) & 0xFFFFFFFF; mn = "orr"
            elif op == 0x0:
                R[rd] = (a & op2) & 0xFFFFFFFF; mn = "and"
            elif op == 0x1:
                R[rd] = (a ^ op2) & 0xFFFFFFFF; mn = "eor"
            elif op == 0xE:
                R[rd] = (a & (~op2 & 0xFFFFFFFF)) & 0xFFFFFFFF; mn = "bic"
            elif op == 0x4:
                R[rd] = (a + op2) & 0xFFFFFFFF; mn = "add r%d,#0x%X" % (rd, op2)
            elif op == 0x2:
                R[rd] = (a - op2) & 0xFFFFFFFF; mn = "sub"
            elif op in (0xA, 0xB, 0x8, 0x9):
                r = (a - op2) & 0xFFFFFFFF
                C.v &= ~0xC0000000
                if r & 0x80000000: C.v |= 0x80000000
                if r == 0: C.v |= 0x40000000
                mn = {0xA: "cmp", 0xB: "cmn", 0x8: "tst", 0x9: "teq"}[op]
            else:
                mn = "UNKNOWN dp op0x%x 0x%08X" % (op, ins)

    else:
        mn = "UNKNOWN 0x%08X" % ins

    return mn, nxt, branch, take


# ---------------- Thumb 指令长度 walker ----------------
def thumb_len(hw0):
    top = (hw0 >> 11) & 0x1F
    if top in (0x1D, 0x1E, 0x1F):
        return 4
    return 2


def cmd_find_base(a1010, step=0x1000):
    """扫描页对齐基址，找哪个 base 让 bx 目标 0x1002CB8C 落在函数序言上。"""
    target = 0x1002CB8C
    L = len(a1010)
    print("== 找 a1010 基址：让 bx 目标 0x%X 正好落在 Thumb/ARM 函数序言上 ==" % target)
    print("   (bx 目标固定；base 改则 foff=target-base 改；只看页对齐 base)")

    def prologue(foff):
        if foff < 0 or foff + 4 > L:
            return None
        hw0 = a1010[foff] | (a1010[foff + 1] << 8)
        hw1 = a1010[foff + 2] | (a1010[foff + 3] << 8)
        # Thumb 16-bit push
        if (hw0 & 0xFF80) == 0xB500:   # push {...,lr}
            return "Thumb push {...,lr} 0x%04X" % hw0
        if (hw0 & 0xFF80) == 0xB400:   # push {...}
            return "Thumb push {...} 0x%04X" % hw0
        # Thumb-2 32-bit push.w = STMDB sp! = E92D xx
        if hw0 == 0xE92D:
            return "Thumb-2 push.w (E92D %04X)" % hw1
        return None

    def arm_prologue(foff):
        if foff < 0 or foff + 4 > L:
            return None
        w = struct.unpack_from("<I", a1010, foff)[0]
        if (w & 0xFFFF0000) == 0xE92D0000:   # STMFD sp!,{...}
            return "ARM push STMFD sp!,{0x%04X}" % (w & 0xFFFF)
        return None

    hits = []
    b = (0x10000000 // step) * step
    maxbase = target
    while b <= maxbase:
        foff = target - b
        if 0 <= foff < L:
            p = prologue(foff)
            pa = arm_prologue(foff)
            if p or pa:
                row = " ".join("%02X" % x for x in a1010[foff:foff + 6])
                hits.append((b, foff, p or pa, row))
        b += step
    if hits:
        for (b, foff, tag, row) in hits:
            print("  ★ base=0x%08X  foff=0x%05X  [%s]  %s" % (b, foff, row, tag))
        print("\n  → 优先看 foff 落在 0x14000~0x20000（a1010 代码区）的那个 base。")
    else:
        print("  页对齐基址下没有命中 push 序言。可试更小 step：--find-base --find-step 0x40，")
        print("  或直接看几个常见装载偏移: --a1010-base 0x10010000 / 0x10008000 / 0x10018000")


def dump_hex(mem, base, foff, n=0x40, label=""):
    if foff < 0:
        return
    print("   [hex %s file 0x%X]" % (label, foff))
    o = foff
    end = foff + n
    while o < end:
        row = mem.read32(base + o) if o + 4 <= end else 0
        bs = [(row >> (8 * k)) & 0xFF for k in range(4)]
        asc = "".join(chr(c) if 32 <= c < 127 else "." for c in bs)
        print("     0x%05X: %02X %02X %02X %02X  %s" % (o, bs[0], bs[1], bs[2], bs[3], asc))
        o += 4


def dump_thumb_walk(mem, off_va, n=16):
    print("   [Thumb 边界walker @ VA 0x%X]" % off_va)
    a = off_va
    for _ in range(n):
        hw0 = mem.read32(a) & 0xFFFF
        ln = thumb_len(hw0)
        if ln == 4:
            hw1 = (mem.read32(a) >> 16) & 0xFFFF
            print("     0x%X: %04X %04X  (32-bit)" % (a, hw0, hw1))
        else:
            print("     0x%X: %04X        (16-bit)" % (a, hw0))
        a += ln


# ---------------- 主流程 ----------------
def main():
    ap = argparse.ArgumentParser(description="D750 启动桩单步模拟（无 QEMU）")
    ap.add_argument("--b1010", help="b1010_115a.bin（--find-base 时不需要）")
    ap.add_argument("--a1010", required=True)
    ap.add_argument("--find-base", action="store_true", help="扫描基址，找让 bx 落入 %s 处函数序言的装载地址" % "0x1002CB8C")
    ap.add_argument("--find-step", type=lambda x: int(x, 0), default=0x1000, help="--find-base 的 base 步长")
    ap.add_argument("--b1010-base", type=lambda x: int(x, 0), default=0x90000000)
    ap.add_argument("--a1010-base", type=lambda x: int(x, 0), default=0x10000000)
    ap.add_argument("--flash", help="整片 flash（0x10000000 起），用于填 config 槽")
    ap.add_argument("--unmapped", type=lambda x: int(x, 0), default=0,
                    help="未映射读值，默认0(无回调)；QEMU 若返回0xFF设0xFF")
    ap.add_argument("--sp", type=lambda x: int(x, 0), default=0x80FFF000)
    ap.add_argument("--skip-init", type=lambda x: int(x, 0), default=0x9025DA40,
                    help="桩里 BL init 的地址，默认直接跨过(0=不跳)")
    ap.add_argument("--max-steps", type=int, default=400)
    ap.add_argument("--thumb-walk", type=int, default=16)
    args = ap.parse_args()

    a1010 = open(args.a1010, "rb").read()
    if args.find_base:
        cmd_find_base(a1010, args.find_step)
        return
    if not args.b1010:
        ap.error("--b1010 必填（除非用 --find-base）")
    b1010 = open(args.b1010, "rb").read()

    mem = Memory(unmapped_fill=args.unmapped)
    mem.add(args.b1010_base, b1010)
    mem.add(args.a1010_base, a1010)
    mem.add(0x80000000, bytearray(0x01000000), writable=True)   # 16MiB scratch(stack)
    if args.flash:
        mem.add(0x10000000, open(args.flash, "rb").read())
    else:
        mem.add(0x100F4000, bytearray([args.unmapped & 0xFF]) * 0x1000, writable=True)

    R = [0] * 16
    C = Cpu()
    R[15] = 0x9025D700
    R[13] = args.sp
    R[14] = 0

    print("== 启动桩单步  b1010@0x%X  a1010@0x%X  unmapped=0x%X  skip-init=0x%X ==" %
          (args.b1010_base, args.a1010_base, args.unmapped, args.skip_init))

    steps = 0
    entry = None
    while steps < args.max_steps:
        if C.v & 0x20:
            print("  !! 已进入 Thumb 态，ARM 单步停止")
            break
        addr = R[15] & 0xFFFFFFFF
        mn, nxt, branch, take = step_arm(R, C, mem)
        extra = ""
        if mn[:2] in ("ld", "st", "bl", "bx", "cm", "mo", "ad"):
            extra = "   [r0=0x%08X r1=0x%08X r12=0x%08X]" % (R[0], R[1], R[12])
        print("  0x%08X  %-22s%s%s" % (addr, mn, extra, "" if take else "  (cond false)"))

        # 跨过 init 调用
        if take and branch is not None and args.skip_init and branch == args.skip_init:
            print("      (skip init 0x%X, 直接返回 0x%X)" % (branch, R[14]))
            R[15] = R[14] & 0xFFFFFFFF
            steps += 1
            continue

        R[15] = (branch if (take and branch is not None) else nxt)
        steps += 1
        if mn.startswith("UNKNOWN"):
            print("\n  >>> 未实现指令 0x%08X @0x%X，停止。" % (mem.read32(addr), addr))
            print("      把这条编码发给大肥鱼，我加进子集即可。")
            break
        if take and branch is not None and args.a1010_base <= branch < args.a1010_base + len(a1010):
            entry = branch
            break
        if addr == 0x9025D750 and branch is not None:
            entry = branch
            break

    print("\n==================== 结论 ====================")
    if entry is None:
        print(" 未到达 -> a1010 的 BX（中途 halt 或走了别的分支）。看上面 trace。")
        _summary_cfg(mem, args)
        return
    foff = entry - args.a1010_base
    mode = "THUMB" if (entry & 1) else "ARM"
    in_range = 0 <= foff < len(a1010)
    print(" BX 目标 = 0x%08X  →  模式 %s（bit0=%d）" % (entry, mode, entry & 1))
    print(" 对应 a1010 文件偏移 = 0x%X  (a1010 size=0x%X, 在范围内=%s)" % (foff, len(a1010), in_range))
    # 直接 hexdump 关键偏移，便于人工同时按 ARM/Thumb 解码
    dump_hex(mem, args.a1010_base, foff, 0x40, "BX入口")
    for cand in (0x2CB4C, 0x2CB8C):
        if 0 <= cand < len(a1010) and cand != foff:
            dump_hex(mem, args.a1010_base, cand, 0x20, "候选")
    if mode == "THUMB":
        dump_thumb_walk(mem, entry & ~1, args.thumb_walk)
    else:
        print(" 目标是 ARM 态。若该处其实是 Thumb 函数体，就会跑飞 —— 这正指向")
        print(" 'base 偏 0x40 / 字面量应 +1(0x..BD)' 的问题。对比两个 offset：")
        print("   base=0x10000000 -> file 0x2CB8C ; base=0x10000040 -> file 0x2CB4C")
        print(" 建议：--a1010-base 0x10000040 再跑，看 file 0x2CB4C 是不是干净 Thumb 函数。")
    _summary_cfg(mem, args)


def _summary_cfg(mem, args):
    v8 = mem.read32(0x100F48C8)
    v0 = mem.read32(0x100F48C0)
    print(" config 槽：0x100F48C8=0x%08X  0x100F48C0=0x%08X %s" %
          (v8, v0, "(来自 --flash)" if args.flash else "(来自 --unmapped 填充)"))
    if v8 == 0:
        print("  → 0：桩跳过 blxne 回调，走“无回调”路径（正常首启动常见）")
    elif v8 == 0xFFFFFFFF:
        print("  → 0xFFFFFFFF：桩会 blxne 到 0xFFFFFFFF，末位=1 进 Thumb → 立刻跑飞！")
        print("     很可能就是 QEMU 里 0 MMIO 的隐藏原因：未映射 flash 默认读了 0xFF。")
        print("     对策：QEMU 未映射读改回 0，或提供真实整片 flash（--flash）。")
    else:
        print("  → 非 0：桩会 blxne 到 0x%08X 调回调，请确认该地址是合法函数。" % v8)


if __name__ == "__main__":
    main()
