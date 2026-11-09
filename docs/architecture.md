# 机器模型与实现边界

> [English](architecture.en.md) | 中文

## 1. 目标与实现形态

`nikon-d750` 是一个**验证原型**，用于驱动本地解密后的 D750 主镜像走完尽可能
早的启动路径，并把“缺什么”以最小代价暴露出来。它不追求完整 EXPEED 4 规格。

实现形态与 z7-qemu / z9-qemu 相同：一个 **QEMU source overlay**。

```
hw/arm/nikon-d750-lab.c   板级模型（约 850 行）
hw/arm/nikon-d750-lab.h   内存映射常量
hw/arm/meson.build        + arm_ss.add(...)
hw/arm/Kconfig            + config NIKON_D750_LAB
configs/devices/arm-softmmu/default.mak  + CONFIG_NIKON_D750_LAB=y
```

`qemu/prepare_source.py` 负责把上述内容装进 QEMU 源码树，幂等、可重复。
QEMU 11.1 的 chardev 前端类型叫 `CharFrontend`；10.x 叫 `CharBackend`。
overlay 以 11.1 为准；prepare 脚本在 10.x 树上做一次文本替换，让两代共用同一份
源码。本仓库只在 11.1.0 上实际编译过，10.x 的编译支持尚未验证。

## 2. 内存映射（原型默认值）

| 起始 | 大小 | 内容 | 属性 |
| --- | --- | --- | --- |
| `0x00000000` | 4 GiB | 诊断 catch-all | `MemoryRegionOps`，优先级 -1000；strict 时记录首条后停止 |
| `0x00000000` | 64 KiB | 低内存 RAM（向量/启动全局） | RAM，优先级 0 |
| `0x00000FF0` | 4 B | halt 窗口（辅助 LR 返回点） | IO，优先级 1 |
| `0x10000000` | 8 MiB | flash 窗口；`-bios` 镜像按 `a1010-base`（默认 `0x10018000`）装入 | RAM 后端，原型可写 |
| `0xE000E000` | 0x2000 | `a9mpcore_priv`（GIC/定时器/看门狗） | 运行证据：首条 a1010 MMIO 为 `0xE000E180` |
| `0x80005000` | 0x100 | 候选字节串口 | 子区域，优先级 0 |
| `0x90000000` | `-m`（默认 128 MiB） | 主镜像与 DRAM | `machine->ram` |

优先级关系：具体区域 > catch-all（-1000）。低 64 KiB 必须存在，是因为入口会
向 `0x0` 写一个向量字并读回；`0xFF0` 的 4 字节 halt 窗口覆盖同一段 RAM。

## 3. 启动流程

1. `-kernel`（或 `-machine payload=`）给出 `b1010`，装入 `0x90000000`；
   `-bios`（或 `flash=`）给出 `a1010`，装入 flash 窗口内的 `a1010-base`
   （默认 `0x10018000`）。镜像只读打开，payload 由机器读入宿主缓冲后
   注册为 ROM blob（便于 `thumb-fix` 只改内存副本）。
2. 创建 `-smp` 个 `machine->cpu_type` CPU（默认 `cortex-a9`）。
3. 创建 `a9mpcore_priv` 并映射到 `mpcore-base`（默认 `0xE000E000`），把每个
   CPU 的 IRQ/FIQ/VIRQ/VFIQ 接到 GIC 的 4×N 个 sysbus IRQ 输出。
4. 初始 PC 由 `boot-mode` 决定：
   - `boot-mode=stub`（默认，M1）：先建 4 GiB identity 页表与一小段 ARM
     垫片（`0x1000`），垫片写 `DACR/TTBR0/TTBCR` 后跳 `0x9025D700`；
     同时把页表基址写进 config 槽 `0x100F48C0`，并把 b1010 的
     `bx` 字面量在内存里改成 `0x1002CB8D`（`thumb-fix`）。
   - `boot-mode=entry`（M0）：PC = `entry`（默认 `0x9027D52C`），
     `-machine entry=0x...` 显式覆盖。
5. **辅助启动状态**（M0 第一次实跑后加入，entry 模式使用）：
   - `SP = D750_RAM_BASE + ram_size - 0x100`（默认 `0x97FFFF00`）；
   - `LR = 0x00000FF0`（halt 窗口）；
   - `r0 = 0`；
   - CPSR 保持 QEMU ARM reset 的 SVC + A/I/F 屏蔽值。
   - stub 模式改用 `SP = RAM 顶 - 0x1000`、`LR = 0`，让错误返回可见。

入口在 `0x9027D52C` 处先 `push {r4,r5,r6,lr}`，所以没有 SP 时会写
`0xFFFFFFF0..0xFFFFFFFC`；执行完 `pop` 回 LR。第一次实跑里 LR=0 导致 PC 跑飞，
因此辅助状态是**必需的**，不是可选优化。

### 为什么不用 `arm_load_kernel()`

`arm_load_kernel()` 会替板子写 bootloader、处理 DTB/PSCI，并把 `-kernel`
当成 Linux 镜像或裸机镜像来跑。D750 的主镜像不是 Linux，也不需要 QEMU 的
bootloader；这里直接 `load_image_targphys` + `cpu_set_pc`，保持“字节进去、
PC 指过去”的最小语义，避免多一层无法解释的行为。

### reset 行为

`system_reset` 会把 CPU 拉回 QEMU 的默认复位向量（0 或 0xFFFF0000），
不会自动回到 `entry`。这是原型的已知限制：验证请用新的 `run.py` 进程，
不要依赖 monitor 的 `system_reset`。

## 4. 设备合同

### 4.1 catch-all 诊断窗口（`0x00000000`，4 GiB）

- 读：记录 `pc/addr/size`，返回 0。
- 写：记录 `pc/addr/size/value`，丢弃。
- 每条记录走 `LOG_GUEST_ERROR`，由 `-d guest_errors -D qemu.log` 收集。
- 前 512 条逐条记录，之后每 4096 条抽样一次，避免轮询刷爆日志。
- `run.py` 会把日志聚合成 `session.json.mmio.by_address`（地址 × 方向 × 次数
  × 首次 PC）。
- `strict=on`：第一条访问改记 `d750-strict:` 并请求 QEMU 退出；`run.py` 把它
  写入 `session.json.strict`，退出码 7。地址不会丢，也不会掉进异常向量。
  注意：shutdown 请求在当前 TB 结束后才生效，日志里 `d750-strict:` 之后可能
  还跟一条 halt；以 `session.json.status=strict-stop` 为准。

这不是“返回合理值”的模型。默认让 guest 继续跑，把真实访问序列留给下一轮建模；
strict 则把“第一个缺失设备”变成一次显式停止。

### 4.2 串口（`0x80005000`）

| 偏移 | 读 | 写 |
| --- | --- | --- |
| `+0x10` | 0 | 低字节送 chardev（`-serial file:uart.log`） |
| `+0x11` | `uart_status`（默认 0x03） | 记录 |
| `+0x12` | 0 | 记录 |
| `+0x14` | `uart_status` | 记录 |
| 其他 | 0，记录 | 记录 |

状态位是**假设**。如果固件轮询的是“bit5 = TX empty”之类，第一次运行会在
`qemu.log` 里看到密集的 `rd +0x11`，据此调整模型，而不是猜一个“全 1”。

### 4.3 MPCore

`a9mpcore_priv` 提供 GIC、per-CPU 私有定时器、全局定时器和看门狗。
基址由 2026-11-08 的运行证据定为 **`0xE000E000`**：a1010 的第一条 MMIO 是
`wr 0xE000E180 ← 0x00100000`（GIC distributor `ICENABLER0`），同一次运行
还出现 `gic_cpu_write: Bad offset 80`。旧的 `0x1E000000` 是 A9 参考布局，
没有 D750 访问证据；现在保留 `mpcore-base=` 属性，便于诊断时改回旧地址复现
“未映射”观测。

### 4.4 SMP

默认 1 核。`-smp 2` 可以试，但原型的 GIC 输出只按 `smp.cpus` 连接，
第二个核的启动约定（spin-table/bootreg）没有建模；如果固件等待 CPU1，
`entry` 应在两个核上一致，或后续加 `smp_bootreg` 属性。

### 4.5 LCD dump（主机侧观察，不是显示设备）

`lcd-base` 非 0 时启用：

- 每次 halt 和每 2 秒，从 guest RAM 读取
  `[lcd-base, lcd-base + stride*height)`，写 P6 PPM 到 `lcd-out`；
- `lcd-stride=0` 时按 `width * bpp` 计算；`argb8888` 按内存 B,G,R,A
  解析，`rgb888` 按 R,G,B，`rgb565` 按小端 16 位；
- 窗口越界只记 `d750-lcd:` 日志，不写文件；
- `lcd-base=0`（默认）时完全不启用，不分配 timer、不产生文件。

它不提供窗口、QMP `screendump` 或输入事件；这些要等 G2 后期或 z7 式
display surface。测试卡的生成/验证见 `docs/gui-cmos.md` §3.2。

## 5. 诊断优先的设计取舍

| 取舍 | 理由 |
| --- | --- |
| 未知 MMIO 返回 0 而不是随机值 | 让 guest 继续走，同时留下真实地址；随机值会制造无法解释的状态 |
| 默认不 strict | 一次运行拿到整段访问序列，比每次停在一个新地址快 |
| `strict=on` | 记录第一条未建模访问（`d750-strict:`）后停止；`run.py` 退出码 7 |
| 不做 HLE/不做 RAM 补丁 | 当前阶段要证明的是“哪些行为是固件自己的”，不是把 UI 骗出来 |
| UART 只做 TX + 固定状态 | 先把“有没有输出”变成可观测事实 |

## 6. 与 Z7 / Z9 的差异

| | Z7 | Z9 | D750（本原型） |
| --- | --- | --- | --- |
| CPU | 2× Cortex-A15 | 4× AArch64 | 1× Cortex-A9（假设） |
| payload | 33 MB @ `0x10020000` | 82 MB | 20 MB @ `0x90000000` |
| 显示/ISP | 有 | 有 | 无 |
| 启动辅助 | 有（显式调用原函数） | 有 | 有（辅助 SP/LR + halt 窗口） |
| 验收 | UI/拍摄/RAW | UI/拍摄/RAW/录像 | M0–M3 启动证据 |

不继承任何地址、IRQ 或外设协议；只继承工程形态和证据纪律。

## 7. 代码结构

- `nikon_d750_init()`：映射、装载、CPU、MPCore、串口、PC、可选 LCD timer。
- `d750_probe_read/write()`：catch-all。
- `d750_uart_read/write()`：候选串口。
- `d750_halt_read()`：入口返回点；可选的 LCD dump 也在这里触发。
- `d750_halt_state_is_clean()`：校验 CPSR 模式、LR、SP，区分正常返回与异常路径。
- `d750_lcd_dump()`：guest RAM → PPM。
- 机器属性：`payload`、`flash`、`entry`、`boot-mode`、`payload-base`、
  `a1010-base`、`thumb-fix`、`mmu-bringup`、`mmu-table`、`flash-size`、
  `aux-ram-size`、`vector-fix`、`veneer-slot`、`loader-copies`、`io-stub`、
  `mpcore-base`、`strict`、`lcd-*`。
- 日志前缀：`d750-probe:` / `d750-uart:` / `d750-a1010-io:`，`run.py` 按前缀解析。

## 8. 已知限制

1. 已在 WSL（Ubuntu 26.04 / gcc 15.2）编译并跑到 M0；Windows MSYS2 产物未构建。
2. M1 已到达 1107 的目标并抓到第一条 MMIO，但目标镜像是 M-profile，A-core
   启动链未闭合。
3. `a1010` 之外的 flash 内容缺失，读到的是 0；config 槽 `0x100F48C0` 由
   `mmu-bringup` 垫片回填。
4. 串口语义、CPU 型号仍为假设；GIC 基址已由运行证据定为 `0xE000E000`。
5. 没有 VMState/迁移；恢复方式是重新起进程。
6. 没有实现 cache/TLB 行为差异、没有 cycle 精度；TCG 的时序不代表硬件。
7. halt 窗口位于低内存 NOP 滑梯末端：正常返回和“异常后滑到 `0xFF0`”都可能
   触发它；机器用 `return_ok` 区分，`run.py` 对 `false` 返回退出码 6。
