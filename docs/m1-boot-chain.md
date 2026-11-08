# M1：启动桩实跑与 a1010 目标核验

> 日期：2026-11-08 · 环境：WSL2 Ubuntu 26.04、gcc 15.2、QEMU 11.1.0 overlay
> 固件：`b1010_115a.bin`（20,324,448 B，SHA-256 `faada7fe…`）、
> `a1010_011100.bin`（786,432 B，SHA-256 `690b7d1c…`）

承接 2026-11-07 的 M1 更新（启动桩 `0x9025D700`、a1010 基址 `0x10018000`、
Thumb 位修正）。本文只记录**在 QEMU 里真实跑出来**的结果，包括与上一轮
结论不一致、必须修正的部分。原始材料在 `update_1107.zip`（仓库根目录）。

## TL;DR

| 项目 | 结果 | 状态 |
|---|---|---|
| 启动桩 `0x9025D700` | 从 MMU 引导垫片 `0x1000` 跳入，逐条执行到 `bx ip` | ✅ 实跑 |
| a1010 映射 `0x10018000` | `bx ip` 目标 `0x1002CB8C` 落在文件 `0x14B8C`，进入 **Thumb** | ✅ 实跑 |
| 入口现场 | `PC=0x1002CB8C`、`CPSR.T=1`、`SVC`、`LR=0x9025D754`、`r0..r4=0,0,2,0,1` | ✅ GDB 实测 |
| 第一条 a1010 MMIO | `wr 0xE000E180 ← 0x00100000`（GIC distributor `ICENABLER0`） | ✅ 实跑 |
| QEMU 的 MPCore 基址 | 由 `0x1E000000` 改为 **`0xE000E000`**（同一次写入定位） | ✅ 已改 |
| 启动桩 MMU 开启 | b1010 init 会写 `SCTLR=0x1C05`；页表基址来自 config 槽 `0x100F48C0` | ✅ 机制已实测 |
| a1010 的核归属 | 该镜像带 **大端 Cortex-M 向量表**，并在 `0x100240AC` 执行 `MRS/MSR BASEPRI` → **M-profile 固件** | ⚠️ 新问题 |
| M1 是否“完成” | 1107 的地址/入口被实跑证实，但目标模块不属于 A-core → **不能称为闭合** | ⚠️ 待补输入 |

一句话：**1107 的地址推算在 QEMU 里确实能跑通，并且抓到了第一条 MMIO；
但那条 MMIO 来自一颗 Cortex-M 核的固件，不是 A-core 的下一阶段。**
下一步需要整片 flash / 模块偏移表来确定 A-core 真正的 `0x1002CB8C` 属于谁。

## 1. 机器新增的 M1 选项

| 选项 | 默认 | 作用 |
|---|---|---|
| `boot-mode=stub\|entry` | `stub` | `stub`：从 b1010 启动桩进链；`entry`：M0 的辅助入口 |
| `a1010-base=<addr>` | `0x10018000` | a1010 镜像在 flash 窗口内的装入地址 |
| `thumb-fix=on\|off` | `on` | 在**内存副本**里把 `0x25D7F8` 的字面量 `0x1002CB8C` 改成 `0x1002CB8D`，不改固件文件 |
| `mmu-bringup=on\|off` | `on` | 模拟缺失的 boot ROM：铺 4 GiB identity 页表、写 DACR/TTBR0/TTBCR，再把 config 槽填成页表基址 |
| `mpcore-base=<addr>` | `0xE000E000` | A9 MPCore（GIC/定时器/看门狗）基址；诊断时可改回 `0x1E000000` 复现“未映射”观测 |

`boot-mode=stub` 时初始 PC 是内部垫片 `0x1000`（不是 `0x9025D700`）；
`session.json` 仍把架构入口记为 `0x9025D700`，避免把实现细节写进证据。

## 2. 实跑现场（GDB，`evidence/m1/gdb-entry.json`）

```
power_on   pc=0x00001000  cpsr=0x400001d3  sp=0x97fff000
breakpoint a1010 entry:
           pc=0x1002cb8c  cpsr=0x600001f3  T=1  mode=0x13(SVC)
           sp=0x97fff000  lr=0x9025d754
           r0=0x00000000 r1=0x00000000 r2=0x00000002 r3=0 r4=0x00000001
           bytes: 10 b5 14 20 f9 f7 df ff 04 22 00 21 0f 20 f8 f7
```

`LR=0x9025D754` 正是桩里 `bx ip` 的下一条指令；`r0..r4` 正是桩传入的
`func(*(0x100F48C4), *(0x100F48C8), 2, 0, 1) = (0, 0, 2, 0, 1)`。这三项同时
对上，说明**交接现场完全符合 1107 的静态推断**。

单步前 6 条指令（Thumb 连续）：

```
0x1002cb8c  push {r4,lr}
0x1002cb8e  movs r0,#0x14
0x1002cb90  bl   0x10026b52
0x10026b52  ...
```

## 3. 启动桩的 MMU 是必须处理的坑

1107 的 `stub_trace.py` 默认 `--skip-init 0x9025DA40` 跳过 b1010 的本地 init，
因此没暴露这条路径。真实执行时：

- `0x9025DA40` 的 init 读 config 槽 `0x100F48C0`，把 `(值 & ~0x3FF) | 0x42`
  写入 **TTBR0/TTBR1**，再在 `0x9025DA80` 写 `SCTLR=0x1C05`（**M=1**）。
- 若 `0x100F48C0` 为 0（只装 a1010、无整片 flash），init 会把 TTBR0 写成
  `0x42`，下一条取指立刻 translation fault：

```
Taking exception 3 [Prefetch Abort] ... IFSR 0x5 IFAR 0x9025da84
```

- 因此 `mmu-bringup=on` 做两件事：
  1. 在 DRAM 顶部铺 4 GiB 的 1 MiB section identity 页表（`0x97ff0000`）；
  2. 把小端字 `0x97ff0000` 写进 config 槽 `0x100F48C0`。

这样一来 init 自己会写 `TTBR0=0x97ff0042`（低 10 位是页表属性），MMU 打开后
继续 identity 执行，**固件文件一个字节都没改**。

> 这条同时修正了 1107 文档里“config 槽只影响回调指针”的说法：**它首先影响
> 页表基址**。`0x100F48C0` 在真实 flash 里很可能就是页表基址。

## 4. 第一条 MMIO 与 GIC 基址

`evidence/m1/gic-unmapped/qemu.log`（故意把 MPCore 放在旧占位址 `0x1E000000`，
让访问落到诊断窗口）：

```
0x1002cb8c:  10b51420f9f7dfff          ; push {r4,lr}; movs r0,#0x14; bl ...
0x1002cb90:  ...
0x10026b52:  00f01f020121914040094ff0e02202eb8000c0f880117047
0x10026b64:  c0f88011
d750-a1010-io: pc=0x10026b64 wr addr=0xe000e180 size=4 value=0x00100000
```

- `0xE000E180` + 值 `0x00100000` = GIC distributor 的 `ICENABLER0`（IRQ 20）。
- 同一次运行还命中 `gic_cpu_write: Bad offset 80`，两处都指向
  **A9 MPCore 在 `0xE000E000`**，旧的 `0x1E000000` 是错的。
- 改到 `0xE000E000` 后重跑（`evidence/m1/default/`）：这一次写入被真实 GIC
  模型接收，**未建模 MMIO 计数 = 0**。两条证据互补：前者定位基址，后者证明
  设备已接上。

## 5. a1010 到底是哪颗核的固件？

把 a1010 映射到 `0x10018000`、强制 Thumb 后，入口确实跑起来了；但继续执行会
在 `0x100240AC` 遇到 undefined：

```
0x100240ac:  ef f3 11 80   ; MRS r0, BASEPRI
0x100240b0:  4f f0 20 01   ; mov.w r1,#0x20
0x100240b4:  81 f3 11 88   ; MSR BASEPRI, r1
```

`BASEPRI` 是 **ARMv7-M 专有**系统寄存器；Cortex-A9（A-profile）上必然
undefined。QEMU 的行为与之一致：

```
Taking exception 1 [Undefined Instruction] ... PC=0x100240ac
```

进一步把 a1010 当模块看：

| 偏移 | 内容 | 说明 |
|---|---|---|
| `0x00` | `20 00 f8 c0`（大端 `0x2000F8C0`） | 初始 MSP，指向 `0x20000000` SRAM |
| `0x04` | `00 00 c2 0d`（大端 `0x0000C20D`） | reset vector，Thumb → `0xC20C` |
| `0x08..` | `0x000138FB`、`0x00013321`… | NMI/HardFault/…/IRQ 向量 |
| `0xC20C` | `bl SystemInit; bl __libc_init_array; b .` + `.data` 拷贝循环 | 典型 Cortex-M `Reset_Handler` |
| `0xC0AC` | `MRS/MSR BASEPRI` | M-profile 临界区原语 |

也就是说，**a1010 是一份大端（BE8：数据大端、指令小端）的 Cortex-M 固件**，
字符串里也写着 `D750   Firmware A Copyright Nikon Corp.`。它不可能由 A-core
的 `bx` 直接调用。

这意味着两种可能，必须用外部输入判定：

1. **1107 的基址是巧合**：A-core 的 `0x1002CB8C` 属于另一份 A-profile 模块
   （不在已解出的 3 个模块里），a1010 只是恰好在这个偏移有一份可解码的
   Thumb 函数；
2. **核归属判断有误**：若 D750 真有两颗核，a1010 属于 M-core，那么 A-core 的
   下一阶段模块尚未拿到（整片 flash / 模块偏移表里才有的那一段）。

在拿到整片 flash 或模块偏移表之前，**不应把 M1 记为“完成”**。

## 6. 对 M2 的影响与下一步

- **GIC 已接上**：`mpcore-base=0xE000E000` 现在是默认值，下一次未建模访问才是
  真正的新设备线索（串口候选 `0x80005000` 仍未命中）。
- **串口仍未输出**：`uart=0B`，M2 的判定条件不变。
- **下一步优先级**：
  1. 拿整片 flash（或容器模块目录 + 每模块的 flash 偏移/大小），重建
     `0x10000000` 窗口；确认 `0x1002CB8C` 落在哪个模块；
  2. 若确认 a1010 属于 M-core，用 `cortex-m3` 单独启动它（复位向量 `0xC20D`、
     SRAM `0x20000000`），验证 M-core 侧行为；
  3. 继续用 `strict=on` + `-d in_asm` 找 A-core 真正的第一条新 MMIO。

## 7. 复现

```sh
# M1：启动桩 -> a1010 目标（GIC 已建模，无未建模访问）
FW=/path/to/D750_0115.dec.modules
python3 tools/run.py \
  --payload "$FW/b1010_115a.bin" --flash "$FW/a1010_011100.bin" \
  --boot stub --a1010-base 0x10018000 --timeout 6 --trace in_asm

# 复现“第一条 MMIO 是 0xE000E180”：把 MPCore 放回旧的占位址
python3 tools/run.py ... --boot stub --mpcore-base 0x1E000000
# session.json 里应出现 mmio.first_a1010 = {wr 0xe000e180, pc 0x10026b64}

# GDB 现场（另开终端，先 -S 起 QEMU，再用 tools/probe.py）
```

现有证据：`evidence/m1/{gic-unmapped,default,gdb-entry.json}`。

## 8. 边界

- 本文的“M-profile”判断基于指令编码、向量表和 reset handler 三处独立证据；
  仍建议在真实硬件或用 M-core 模拟器交叉验证。
- `mmu-bringup` 是**替代 boot ROM 的仿真垫片**，不是对 D750 boot ROM 的还原；
  它只保证 identity 映射，不保证 cache/权限属性与真机一致。
- `thumb-fix` 只改内存副本；容器 CRC / `SHA1(body||K8)` 不受影响。
