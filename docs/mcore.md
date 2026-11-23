# D750 M-core（Firmware A / a1010）验证原型

> [English](mcore.en.md) | 中文

> 日期：2026-11-23 · 机器：`nikon-d750-mcore` · 状态：**能启动到 idle，
> 但还没有 console/GUI，也没有证明 RTOS 已完整初始化。**

本文记录 `a1010_011100.bin` 在独立 Cortex-M 模型上的真实执行结果。它回答
一个问题：**a1010 作为 D750 的 M-core 固件，离开 reset 后能走多远、最先需要
哪些外设？** 所有结论来自本地镜像与 QEMU 运行记录，不包含固件本体。

## 1. 输入与身份

| 项目 | 值 |
| --- | --- |
| 镜像 | `a1010_011100.bin`，786,432 B |
| SHA-256 | `690b7d1c7683cda36c72b5911cdd474ad5bc78f9467b369f3f86dc7316600213` |
| 身份字符串 | `D750   Firmware A Copyright Nikon Corp.` @ `0x1F08` |
| 向量表 | `0x0`，16 项，**32 位大端** |
| MSP | `0x2000F8C0` |
| reset | `0x0000C20D`（Thumb） |
| 指令/数据 | BE8：指令小端 Thumb，数据访问大端 |

reset 值与 D850 的 `a1330` 相同（`0x0000C20D`），这是两台机器 M-core 启动
代码同源的强线索；地址相同不等于代码逐字节相同，本文只按 D750 的真实字节
下结论。

## 2. 机器模型

```sh
qemu-system-arm -M nikon-d750-mcore \
  -kernel /path/to/a1010_011100.bin \
  -display none -monitor none -serial file:uart.log \
  -D qemu.log -d int,guest_errors -no-reboot -nic none
```

| 项目 | 取值 |
| --- | --- |
| CPU | `cortex-m4`（VFP 打开，`-cpu` 可换） |
| Flash | 1 MiB @ `0x00000000`，直接装入 a1010 |
| SRAM | 256 KiB @ `0x20000000`（MSP 在 `0x2000F8C0`） |
| 向量表夹具 | 把前 `0x40` 字节的 16 项按 32 位字交换，供 QEMU 的小端向量读取 |
| BE8 修复 | 在 `0xE000ED00` 放 0x100 字节大端 SCB 窗口，接管 `VTOR`/`CPACR` |
| 诊断 | 4 GiB catch-all：未建模访问记录 PC/地址/宽度/方向 |
| 首批外设 | `0x400F2000`、`0x400F3000` 各 0x1000 的诊断寄存器堆 |

### 2.1 哪些是夹具，哪些是结论

- **镜像没有修改**：向量表的字交换只发生在 QEMU 的 flash 副本里；SP/PC 从
  原始大端字节读取。
- `0x400F2000` / `0x400F3000` 的寄存器堆只是“读回最后写入值”的诊断夹具，
  用于让 mailbox 的 echo/busy/ready 轮询通过；**不是**对硬件语义的还原。
- `0xE000ED00` 的大端 SCB 窗口是 BE8 修复，不是 SCB 模型。
- 4 GiB catch-all 会把未建模访问记成 `d750-mcore-probe:`；strict 模式在
  第一条未建模访问处停止。

## 3. 实测启动轨迹

实际 probe 日志（`0x400F2/3` 已映射成寄存器堆，所以不再出现在 probe 里）：

```text
Loaded reset SP 0x2000f8c0 PC 0xc20d from vector table
0xFF3A  rd  0x440CE000
0xFF40  wr  0x440CE000 = 0x80000000
0xFFB4  rd  0x440CE004
0xFFC2  wr  0x440CE004 = 0x40000000
0xFFE4  rd  0x440CE008
0xFFEC  wr  0x440CE008 = 0
0xFFCC  rd  0x440CE004
0xFFDA  wr  0x440CE004 = 0x03000000
```

第一次 probe 运行（还没有加 `0x400F` 寄存器堆）另外记录到：

```text
0xC2B0  rd  0x400F2000
0xC2B6  wr  0x400F2000 = 0
0xC2BE  wr  0x400F2004 = 0xB1000000   ; QEMU LE 视图；BE 写值为 0xB1
0x1036C rd  0x400F3004
0x10376 wr  0x400F3004 = 0x00015DC3   ; QEMU 的 LE 视图；BE 写值为 0xC35D0100
0x10378 rd  0x400F3004  (轮询)
```

`0xC03C` 的 `STR 0x8F -> 0xE000EF00`（NVIC STIR）来自反汇编和 3 s 时的
寄存器（`R1=0xE000EF00`、`PC=0xC04A`），不是 probe 日志（该地址由 NVIC 建模）。

3 s 时寄存器（QMP）：

```text
PC=0x0000C04A  LR=0x0000C04B  SP=0x2000F8B8
R1=0xE000EF00  R2=0x00000004  R9=0x2000FC00
XPSR=0x61000000  T priv-thread
```

- `0xC04A` 是 `bx lr`；`LR=0xC04B` 使 BX 清 bit0 后回到 `0xC04A`，即一个
  稳定的 **idle self-loop**。
- 运行 3 s：**0 异常、0 UART 字节**；8 次 MMIO 全部在 `0x440CE000`。
- strict 模式第一条未建模访问：`pc=0xFF3A rd 0x440CE000`。

## 4. 读出来的语义（强线索，未硬件验证）

### 4.1 `0x400F3004` 是命令/状态 mailbox

反汇编 `0x10368..0x103B0`：

1. 读 `[0x400F3004]`，取低 20 位，OR 上 `0xC35D0100`，写回；
2. 轮询直到读回值的高 12 位与写入值相同（echo）；
3. 置 bit0，轮询 bit1 清零（busy→done）；
4. 写 `(低 20 位) | 0x03E20000`，轮询 bit17 置位（ready）；
5. 清 bit16，写 `0x400F300C = 0xE09A`，再等一次高 12 位 echo。

这与 D850 a1330 的 `0x400F3004` 命令/状态握手**地址和形状都相同**。目前的
寄存器堆让这些轮询通过，但没有证明真实硬件的位语义。

### 4.2 `0x440CE000` 是引脚/时钟块

8 次访问的模式是：读 `+0x00`、置 bit7；改 `+0x04` 的 bit30/25/24；改
`+0x08` 的低位；再读 `+0x04`。这与 D850 M-core 的 pin/clock 序列同构，
**不是 UART TX**。本轮没有看到任何数据寄存器写入。

### 4.3 串口候选

静态扫描 a1010 里的大端 32 位字：

- `0x440C4xxx`：62 处；
- `0x440CE000`：48 处；
- `0x400F2xxx`：6 处；`0x400F3xxx`：30 处。

`0x440C4xxx` 是 D850 已定位的 UART 候选区，但 **a1010 的启动路径没有访问
它**；本轮 UART 仍是 0 B。镜像里也没有 `UART`/`console` 字符串，不能仅凭
地址就宣称串口存在。

## 5. 与 D850-QEMU 的关系

可直接迁移的：

- `nikon-d850-mcore` 的机器骨架（Cortex-M4、1 MiB flash、256 KiB SRAM、
  BE8 向量表、SCB 窗口、catch-all、strict）；
- `0x400F2000` / `0x400F3000` / `0x440CE000` 的**地址同构**观察；
- “先修向量表/SCB，再看未建模访问”的方法；
- 证据/文档格式。

不能直接迁移的：

- D850 A-core 的 LPAE/Cortex-A15 页表夹具不适用于 D750 E4；D750 A-core
  仍是独立的 A9/短描述符问题；
- D850 的 `0xC05E` idle 与 D750 的 `0xC04A` idle 地址不同，不能把 D850 的
  函数边界直接套到 D750。

## 6. 边界与下一步

1. **这不是“M-core 启动完成”**：只证明 reset/SystemInit/时钟 mailbox/
   引脚块/STIR 这条路径能走到 idle；没有 RTOS 任务、console 或显示证据。
2. `STIR=0x8F`（143）超出当前 `num-irq=96`；中断行为未建模。下一步可以
   把 IRQ 数扩到 240，观察是否有 pending IRQ 或异常。
3. 继续找 console：反汇编 `0x440C4xxx` 初始化函数的调用者，或在 idle 后
   注入一个 IRQ 触发任务；不要在未观测到 TX 前声称有串口输出。
4. A-core 的下一阶段仍是独立问题：需要真实 flash/boot ROM 或 loader 交接，
   M-core 结果不能替代它。

## 7. 复现

```sh
# 构建（WSL）
cp qemu/nikon-d750-lab.c qemu/nikon-d750-lab.h \
   ~/d750-build/src/qemu-11.1.0/hw/arm/
ninja -C ~/d750-build/src/qemu-11.1.0/build -j 12 qemu-system-arm

# 运行
qemu-system-arm -M nikon-d750-mcore \
  -kernel "$FW/a1010_011100.bin" \
  -display none -monitor none -serial file:uart.log \
  -D qemu.log -d int,guest_errors -no-reboot -nic none
```

证据：[`evidence/mcore/session.json`](../evidence/mcore/session.json)、
[`boot.qemu.log`](../evidence/mcore/boot.qemu.log)、
[`strict.qemu.log`](../evidence/mcore/strict.qemu.log)。
