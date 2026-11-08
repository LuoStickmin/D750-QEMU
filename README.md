# D750 QEMU 验证原型（`nikon-d750`）

> [English](README.en.md) | 中文

> **更新日志（近期）**
>
> | 日期 | 进展 |
> | --- | --- |
> | 2026-11-09 | **三条无输入验证**：静态调用链、12 种 flash 布局、M-core 启动。结论：flash 窗口更像 **b1010 镜像**，`0x1002CB8C` 是 b1010 flash 副本里的 Thumb veneer；a1010 已在 `cortex-m3` 上零异常启动，确认是 M-core 固件；同日后续用**完整 20 MiB b1010** 验证镜像内 `0x201E2200` 是可用 TTBR0（页表 `0x201E0000`），最小向量表让 SVC 正常返回，并抓到 `0x80000000/4` 设备探测。详见 [docs/m1-tracks-2026-11-09.md](docs/m1-tracks-2026-11-09.md) |
> | 2026-11-08 | **M1 实跑 + v0.2.0**：桩 → `0x1002CB8C`（Thumb，`args=0/0/2/0/1`，`LR=0x9025D754`），首条 MMIO `wr 0xE000E180 ← 0x00100000`；MPCore 基址修正为 **`0xE000E000`**；发现 a1010 是 M-profile 镜像，M1 记为“到目标未闭合”；Linux x86-64 二进制已作为 [Release v0.2.0](https://github.com/LuoStickmin/D750-QEMU/releases/tag/v0.2.0) 发布。详见 [docs/m1-boot-chain.md](docs/m1-boot-chain.md) |
> | 2026-11-07 | **静态定位**：a1010 基址 `0x10018000`、入口文件偏移 `0x14B8C`、Thumb 位、config 槽 `0x100F48C0/C4/C8`；原始材料在 `update_1107.zip` |
> | 2026-11-06 | **v0.1.1**：M0 通过、strict/halt 证据修复、LCD dump 管线、64/60 Mbps 改表；见 [CHANGELOG.md](CHANGELOG.md) |
> | 2026-11-05 | **v0.1.0**：首个公开快照（M0、LCD dump、双语文档） |
>
> 完整变更与兼容性说明见 [CHANGELOG.md](CHANGELOG.md)。

---

> **本仓库有两条工作线**：QEMU 验证原型（本文）与 D750 1080p 高码率修改
> （5 个 HQ 行 42/35、24/20 → 64/60 Mbps）。合并总览见
> [SUMMARY.md](SUMMARY.md)，高码率细节见 [bitrate/README.md](bitrate/README.md)，
> 法律与贡献边界见 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

依据 [WonderLantern/z7-qemu](https://github.com/WonderLantern/z7-qemu) 与
[WonderLantern/z9-qemu](https://github.com/WonderLantern/z9-qemu) 的组织方式，为
Nikon D750（EXPEED 4，`D750_0115`）写的最小验证原型：**一个 QEMU 板级 overlay +
一组主机侧证据工具**。目标不是模拟整台相机，而是按顺序回答四个问题：

- **M0** 主镜像能否按推断基址装入、按推断入口启动？
- **M1** 第一段执行会访问哪些 MMIO 窗口？
- **M2** 固件是否从候选串口块输出字节？
- **M3** 补上第一个缺失设备后能走到哪里？

> 本项目不包含、不下载任何 Nikon 固件。固件由你本地提供，工具只读。

## 目录

- [项目总览（两条工作线）](SUMMARY.md)
- [高码率修改](bitrate/README.md)
- [菜单可见版 64 Mbps / Stock](bitrate/MENU64.md)
- [贡献与法律边界](CONTRIBUTING.md)
- [1. 当前状态](#1-当前状态先读这一节)
- [2. 快速开始](#2-快速开始)
  - [2.1 构建（需要 C 工具链）](#21-构建需要-c-工具链)
  - [2.2 跑](#22-跑)
  - [2.3 只做静态核对](#23-只做静态核对)
  - [2.4 第一次实跑（M0 已通过）](#24-第一次实跑m0-已通过)
  - [2.5 M1 实跑（启动桩 → a1010 目标）](#25-m1-实跑启动桩--a1010-目标)
- [3. 机器模型（一句话版）](#3-机器模型一句话版)
  - [3.1 GUI 与 CMOS 现在到哪一步](#31-gui-与-cmos-现在到哪一步)
- [4. 已经拿到的静态证据（真实字节）](#4-已经拿到的静态证据真实字节)
- [5. 目录](#5-目录)
- [6. 与 z7-qemu / z9-qemu 的关系](#6-与-z7-qemu--z9-qemu-的关系)
- [7. 边界](#7-边界)

---

## 1. 当前状态（先读这一节）

当前**已经完成并验证**的部分：

| 项目 | 状态 |
| --- | --- |
| 静态证据：向量表、入口、页表、flash/RAM 窗口、串口候选 | ✅ 在真实 `D750_0115` 模块上跑通，见 [docs/findings.md](docs/findings.md) |
| 板级源码 `nikon-d750-lab.c/.h` | ✅ 已写（QEMU 11.1 API；10.2.4 由 prepare 脚本做文本适配，未实际编译验证） |
| overlay 安装脚本 `qemu/prepare_source.py` | ✅ 幂等，单测覆盖 11.1 / 10.2 / 拒绝未知版本 |
| `fwscan` / `run` / `probe` / `build` 工具 | ✅ 已写；`probe` 手工对**已安装的 stock QEMU `-M virt`** 做过真实 RSP 联调（测试套件只覆盖协议编解码） |
| 主机侧测试 | ✅ `python tests/run_tests.py` → 27 passed |
| 板级 C 代码编译 | ✅ 已在 WSL Ubuntu 26.04（gcc 15.2）+ QEMU 11.1.0 上编译通过 |
| `nikon-d750` 机器实跑 | ✅ **M0 通过**：装入 `0x90000000`、入口 `0x9027D52C` 执行并正常返回，0.39 s 正常退出 |
| M1 启动链实跑 | ⚠️ **到目标但未闭合**：桩 → `0x1002CB8C`（Thumb）→ 第一条 MMIO `0xE000E180`；随后在 `0x100240AC` 撞到 M-profile 指令，说明目标模块不属于 A-core。见 [docs/m1-boot-chain.md](docs/m1-boot-chain.md) |
| M1 机器选项 | ✅ `boot-mode=stub`、`a1010-base`、`thumb-fix`、`mmu-bringup`、`mpcore-base`；固件文件零修改 |
| strict 诊断 / halt 校验 | ✅ 第一条未建模访问记 `d750-strict:` 后停止（`run.py` 退出码 7）；halt 记录带 `return_ok=`，异常路径退出码 6 |
| LCD 扫描输出/dump 管线 | ✅ 可配置帧缓冲 → PPM；测试卡验证通过；固件画面仍无 |
| 容器重打包 / 改后镜像复现 | ✅ 同作者工具链可逐字节复现（无修改回环 bit-identical；改后镜像 `9c88f3cc…` 可精确重建），见 [docs/hardware-test.md](docs/hardware-test.md) |
| 实机测试 | ⚠️ **未验证**：更新器接受度、编码器行为、写卡/发热/回放都还没有实机记录 |
| M2（串口）/ M3（补设备） | ⏳ 未推进：本轮仍无串口输出（`uart=0B`）；GIC 已接上，等待下一条未建模访问 |
| 完整相机 UI / ISP / CMOS / 存储 | ❌ 不在本原型范围 |

> **另一条工作线（1080p 高码率）**：D750 码率表的 5 个 HQ 行已从
> `42/35`、`24/20` 提到 `64/60` Mbps；容器级验证通过，且改后镜像可由
> stock + 改表模块**逐字节复现**（`repack_firmware.py` 无修改回环
> bit-identical）；QEMU M0 回归与 stock 一致，但**相机实拍未验证**。
> 摘要见 [SUMMARY.md](SUMMARY.md)，细节见 [bitrate/README.md](bitrate/README.md)，
> 实机前置条件见 [docs/hardware-test.md](docs/hardware-test.md)。仓库只含改表
> 工具，不含固件/密钥/改后镜像。Movie quality 新增第三项的可行性以及
> “64 Mbps / Stock”两项复用工具见
> [analysis/menu-bitrate-feasibility.md](analysis/menu-bitrate-feasibility.md)
> 与 [bitrate/MENU64.md](bitrate/MENU64.md)。

**这意味着什么：** 如果你装的是 stock QEMU（例如 Windows 的
`C:\Program Files\qemu`），它通常只有 `qemu-system-arm` / `qemu-system-aarch64`
目标，`-M help` 里**没有 `nikon-*` 机器**。QEMU 的 machine 是编译期注册的，
不能像插件一样在运行时加载。因此“直接用已安装的 QEMU 启动 D750”做不到；
必须用 `tools/build.py` 把 overlay 编进 `qemu-system-arm`。stock 安装的
版本/目标列表见 [docs/build.md](docs/build.md)，`tools/run.py` 也会在启动前
明确拒绝它（退出码 3）。`binary/` 里是 COPYING 与说明；Linux 版
`qemu-system-arm` 通过 GitHub Release 提供：
<https://github.com/LuoStickmin/D750-QEMU/releases/latest>，可在 WSL 里直接运行。

---

## 2. 快速开始

### 2.1 构建（需要 C 工具链）

Linux / WSL：

```sh
sudo apt-get install build-essential ninja-build pkg-config \
    libglib2.0-dev libpixman-1-dev zlib1g-dev libfdt-dev
python3 tools/build.py --jobs 4
```

Windows（MSYS2 UCRT64，z7-qemu 同款路径）：

```powershell
python tools/build.py --msys-root C:\msys64 --jobs 4
```

离线或已有源码：

```powershell
python tools/build.py --archive C:\downloads\qemu-11.1.0.tar.xz
python tools/build.py --source C:\src\qemu-11.1.0 --overlay-only
```

产物：`.build/src/qemu-<版本>/build/qemu-system-arm[.exe]`（`--work-dir` 可改），
构建记录在 `.local/build-manifest.json`。详见 [docs/build.md](docs/build.md)。

### 2.2 跑

Windows PowerShell：

```powershell
$FW = "D:\path\to\D750_0115.dec.modules"   # 换成你的固件目录
python tools/run.py `
  --payload "$FW\b1010_115a.bin" `
  --flash   "$FW\a1010_011100.bin" `
  --timeout 10
```

Linux / WSL：

```sh
FW=/path/to/D750_0115.dec.modules
python3 tools/run.py \
  --payload "$FW/b1010_115a.bin" \
  --flash   "$FW/a1010_011100.bin" \
  --timeout 10
```

带 RSP 快照（先停住、核对入口，再让 guest 跑）：

```sh
python3 tools/run.py --payload ... --flash ... --gdb --run-seconds 2
```

每次运行都会生成 `runs/<时间戳>/`：`command.json`、`uart.log`、`qemu.log`、
`session.json`（含 MMIO 访问统计与串口尾部）。验收标准见
[docs/validation.md](docs/validation.md)。

> 上面的命令使用默认 `boot-mode=stub`（M1，从启动桩进链）。要回到 M0 的
> 辅助入口，加 `--boot entry --a1010-base 0x10000000`，见 §2.4。

### 2.3 只做静态核对

```powershell
$FW = "D:\path\to\D750_0115.dec.modules"
python tools/fwscan.py `
  --main  "$FW\b1010_115a.bin" `
  --flash "$FW\a1010_011100.bin" `
  --out   analysis\d750-0115.json
```

### 2.4 第一次实跑（M0 已通过）

环境：WSL Ubuntu 26.04、gcc 15.2、QEMU 11.1.0。在仓库根目录构建：

```sh
python3 tools/build.py --work-dir ~/d750-build --jobs 12
```

（`--work-dir` 放在 WSL 原生文件系统；`/root` 对默认用户不可写。）

运行（也可以直接用仓库里的 `binary/qemu-system-arm` 跳过构建）：

```sh
FW=/path/to/D750_0115.dec.modules
python3 tools/run.py \
  --qemu ~/d750-build/src/qemu-11.1.0/build/qemu-system-arm \
  --payload "$FW/b1010_115a.bin" \
  --flash   "$FW/a1010_011100.bin" \
  --boot entry --a1010-base 0x10000000
```

实测（证据保存在 `evidence/m0/`、`evidence/m0-gdb/`）：

```
exit=0  timed_out=False  wall_seconds=0.393  uart=0B  mmio_events=0
d750-halt: pc=0x00000ff0 r0=0x80002000 r1=0x00000000 sp=0x97ffff00 lr=0x00000ff0
```

解读：

- 入口 `0x9027D52C` 是一个**被调用函数**，不是 reset。没有辅助时它把
  `{r4,r5,r6,lr}` 压到 `0xFFFFFFF0..0xFFFFFFFC`（SP=0），执行完 `pop` 回
  LR=0，PC 跑飞到 0 —— 这是第一次运行最重要的发现。
- 机器因此加入**辅助启动**：低 64 KiB RAM、SP=RAM 顶、LR 指向 `0xFF0` 的
  halt 窗口、r0=0。函数返回后 halt 设备记录寄存器并请求 QEMU 正常退出。
- 这一片段**没有访问任何 MMIO**（`mmio_events=0`），也**没有串口输出**
  （`uart=0B`）。所以 M1/M2 的下一步不是“再加设备”，而是**找到这个 init
  函数的调用者或下一阶段入口**；`-machine entry=...` 可以直接试别的假设。
- 对镜像内 10 个候选入口（`0x25D0D4..0x25D720`、向量表、默认入口）的扫描
  全部是 `0 MMIO`，`0x9025D700` 则进入无 MMIO 的等待循环。结论：**下一阶段
  不在 `b1010` 里**，更可能来自 boot ROM 或 `a1010` 之外的 flash 内容。
  详见 [findings §11.4](docs/findings.md#114-候选入口扫描负结果)。

### 2.5 M1 实跑（启动桩 → a1010 目标）

2026-11-08 新增。默认机器模式已经是 `boot-mode=stub`；M1 的完整记录（含失败点）
见 [docs/m1-boot-chain.md](docs/m1-boot-chain.md)，证据在 `evidence/m1/`。

```sh
FW=/path/to/D750_0115.dec.modules
python3 tools/run.py \
  --qemu ~/d750-build/src/qemu-11.1.0/build/qemu-system-arm \
  --payload "$FW/b1010_115a.bin" --flash "$FW/a1010_011100.bin" \
  --boot stub --a1010-base 0x10018000 --timeout 6 --trace in_asm
```

预期：

```
status=timeout  entry 0x9025d700  ...
a1010_io=0                       # GIC 已按 0xE000E000 建模
```

把 MPCore 放回旧占位址可以复现“第一条 MMIO”的发现：

```sh
python3 tools/run.py ... --boot stub --mpcore-base 0x1E000000
# session.json: mmio.first_a1010 = wr 0xe000e180 size=4 at pc 0x10026b64
```

GDB 现场（`-S -gdb tcp::12345` + `tools/probe.py`）应看到
`pc=0x1002cb8c cpsr=0x600001f3`（T=1、SVC）、`lr=0x9025d754`、
`r0..r4=0,0,2,0,1`。

> **不要把它读成“M1 完成”**：`0x100240AC` 处是 `MRS/MSR BASEPRI`（ARMv7-M
> 专有），继续执行必然 undefined；a1010 的头部也是大端 Cortex-M 向量表。
> A-core 的下一阶段模块还没有拿到。

---

## 3. 机器模型（一句话版）

| 项目 | 取值 | 依据强度 |
| --- | --- | --- |
| CPU | 1× Cortex-A9（`-smp 2` 可试） | 中：ARMv7 Thumb-2 + VFP/NEON + T-Kernel 字符串 |
| 主 RAM | `0x90000000`，默认 128 MiB | 高：`0x90020000` 页表字面量、`0x9027D52C` 等指针 |
| 主镜像装入 | `b1010_115a.bin` @ `0x90000000` | 高 |
| 初始 PC | `boot-mode=stub` 时为 `0x9025D700`（内部先经 `0x1000` 垫片）；`boot-mode=entry` 时为 `0x9027D52C` | 运行证据：两模式都实跑过 |
| 低内存 | `0x0..0xFFFF` RAM；`0xFF0` 是 halt 窗口，`0x1000` 是 M1 MMU 垫片 | 运行证据：入口会向 `0x0` 写向量字 |
| 辅助启动 | SP=RAM 顶、LR=`0xFF0`、r0=0（entry 模式） | 运行证据：入口 `push`/`pop` 后返回 |
| Flash 窗口 | `0x10000000`，8 MiB；`-bios` 镜像按 `a1010-base` 装入（默认 `0x10018000`） | 中：a1010 在该基址下 `bx` 目标落在 Thumb 序言；但镜像本身是 M-profile，见 M1 文档 |
| MMU 垫片 | `mmu-bringup=on`：DRAM 顶部 16 KiB identity 页表 + `DACR/TTBR0/TTBCR` 垫片；config 槽 `0x100F48C0` 填入页表基址 | 运行证据：不启用时 `SCTLR=0x1C05` 后立即 prefetch abort |
| 串口候选 | `0x80005010..0x80005014` 字节寄存器 | 中：driver 片段 `0x27CC00..0x27D304` |
| GIC/定时器 | `a9mpcore_priv` @ **`0xE000E000`**（可 `mpcore-base=` 覆盖） | 高：第一条 a1010 MMIO 为 `0xE000E180 ← 0x00100000` |
| 诊断 | 4 GiB 低优先级 catch-all；`strict=on` 时记录第一条后停止 | — |

机器是**诊断优先**的：默认把未建模访问记进 `qemu.log`（PC/地址/宽度/方向），
而不是返回貌似合理的值；`-machine strict=on` 仍会记录第一条未建模访问
（前缀 `d750-strict:`），随后立即停止本次运行，`tools/run.py` 以退出码 7 报告该地址。
这比“先填一堆零把 boot 骗过去”更适合验证阶段。

### 3.1 GUI 与 CMOS 现在到哪一步

**GUI：固件画面还没有，但扫描输出管线已经可用。** 机器提供 host 侧 LCD dump：

```powershell
python tools/run.py --payload ... --flash ... `
  --lcd-base 0x92000000 --lcd-width 320 --lcd-height 240
```

- 可配置 `lcd-base / lcd-width / lcd-height / lcd-stride / lcd-format / lcd-out`；
- halt 时以及每 2 秒把该窗口 dump 成 PPM（`runs/<ts>/lcd.ppm`）；
- 不猜地址：`lcd-base=0`（默认）时完全不启用；
- 已用 GDB 往 guest RAM 写测试卡验证整条链路：

  ![LCD test card](analysis/lcd-testcard.png)

  这张图是**主机写入的测试卡**，不是固件 UI；它证明“guest RAM → 扫描 →
  PPM/PNG”这段是通的。真实固件目前不写帧缓冲，所以默认运行得到的是黑图。

**CMOS：还没有。** 本次执行片段 `mmio_events=0`，从未访问 Sensor/I2C/GDMA；
镜像里有 Sensor/ImageProcess/GDMA/I2C 这些驱动名，但没有观测到控制/数据契约。
路线与验收见 [gui-cmos.md](docs/gui-cmos.md)。一句话：**CMOS 卡在“找到 boot
下一阶段 + 观测到 DMA 描述符”这两个前置条件上**；在拿到真实访问序列之前不会
猜寄存器，也不会用“往 RAM 里放一张图”冒充传感器。

---

## 4. 已经拿到的静态证据（真实字节）

`D750_0115` 主模块 `b1010_115a.bin`（20,324,448 B，SHA-256
`faada7fe…f82937fd`）开头是 8 条 ARM 异常向量：

```
0x00  E59FF018  ldr pc,[pc,#0x18]  -> 0x9027D524
0x04  E59FF018                     -> 0x90291C80
0x08  E59FF018                     -> 0x90291D30
0x0C  E59FF018                     -> 0x90291DA8
0x10  E59FF018                     -> 0x90291DB8
0x14  E320F000  nop
0x18  EA00000D  b   +0x34
0x1C  E59FF018                     -> 0x90291DEC
```

**关键矛盾**：`0x9027D524` 处不是代码，而是两个字面量
`0x1041D9A8 / 0x1041DBA8`（ARM 条件码 0x1，不是 AL）。真正的函数入口在
`0x9027D52C`（`cmp r0,#2; mov r3,#0; push {r4-r6,lr}`），且该地址在文件
`0x25D760` 的启动描述符表里被引用。所以原型默认从 `0x9027D52C` 进入，并在
`fwscan` 里把这条矛盾作为 `WARN` 保留下来，而不是掩盖。

同一模块文件 `0x25D7FC` 处有字面量 `0x90020000`（MMU 页表目标），
`0x25D760` 附近还有 `0x90284000 / 0x90280000 / 0x9128DB64 / 0x9132EC00`
等 RAM 指针，以及 `0x100xxxxx` 的 flash 指针（最大到 `0x107FFF24`，正好落在
8 MiB 窗口内）。完整报告：`analysis/d750-0115.json`。

---

## 5. 目录

```text
.
├── .github/workflows/ci.yml    主机侧测试 + 清单校验
├── qemu/
│   ├── nikon-d750-lab.c/.h     板级模型（CPU/RAM/flash/MPCore/串口/LCD dump/诊断窗口）
│   └── prepare_source.py       把 overlay 装进 QEMU 源码树（幂等）
├── tools/
│   ├── fwscan.py               静态核对 profile，生成 manifest
│   ├── run.py                  启动、超时、证据收集（M0/M1 两套参数）
│   ├── probe.py                最小 GDB RSP 客户端
│   ├── stub_trace.py           启动桩单步模拟器（1107 更新工具，零依赖）
│   ├── m1_analyze.py           M1 静态分析四件套（1107 更新工具，disasm 需 capstone）
│   ├── manifest.py             重新生成/校验 SHA256SUMS 与 MANIFEST
│   └── build.py                下载/解包/overlay/构建/记录
├── tests/                      27 个主机侧测试（无需 QEMU 构建）
├── bitrate/                    D750 1080p 64/60 Mbps 改表工具、测试、说明
├── analysis/
│   ├── d750-0115.json          真实镜像的扫描结果
│   ├── lcd-testcard.png        LCD 管线测试卡（主机写入）
│   └── ...                     仓库里已有的其他固件分析产物（见下）
├── binary/                     COPYING + 说明（二进制通过 GitHub Release 发布）
├── evidence/                   M0 / M1 / GDB / LCD / boot-scan 运行证据
├── docs/                       findings / m1-boot-chain / architecture / validation / build / gui-cmos / hardware-test（含 .en.md）
├── SUMMARY.md / SUMMARY.en.md  两条工作线总览
├── CONTRIBUTING.md / .en.md    法律与贡献边界
├── README.md / README.en.md    本文与英文版
├── PRODUCT.md  MANIFEST.json  SHA256SUMS
├── CHANGELOG.md                版本与修复记录
├── LICENSE                     GPLv2 文本（GPL-2.0-or-later）
├── Setup-D750.ps1  Run-D750.ps1
└── .build/ .local/ runs/       本地生成物（Git 忽略）
```

`analysis/` 里只有 `d750-0115.json` 和 `lcd-testcard.png` 由本 QEMU 产品生成；
其余（movie bitrate、TIFF、patch 等）是同一仓库里已有的固件分析产物，随仓库
保留，但不在 QEMU 产品的验收范围内。

> **大文件**：`binary/qemu-system-arm` 约 96 MiB，**不进入 Git 历史**，
> 而是作为 GitHub Release 附件发布：
> <https://github.com/LuoStickmin/D750-QEMU/releases/latest>。`binary/` 只保留
> COPYING 与来源说明。

---

## 6. 与 z7-qemu / z9-qemu 的关系

- **沿用**：source overlay 的形态、`prepare_source.py` 的幂等注册、
  “用户自带固件 + 本地 manifest + 不发布固件”的边界、RSP/GDB 与串口证据习惯。
- **不同**：Z7 是双 Cortex-A15、33 MB payload、有 ISP/LCD/浏览器控制；
  Z9 是四核 AArch64、82 MB payload。D750 原型只有 **M0–M3 的启动验证**，
  没有任何 UI/传感器/图像通路，CPU 也换成了 A9 假设。
- **不继承**：地址、IRQ、外设协议、启动调用。所有常量都来自 D750 自己的字节，
  且都标了置信度。

---

## 7. 边界

- 这是**辅助验证原型**：入口是主机选定的、SP/LR 是主机给的，不等于自然上电启动。
- 已在 WSL 上编译并实跑：M0 干净返回；M1 到达 1107 的目标地址并抓到第一条
  MMIO，但目标镜像是 M-profile，A-core 启动链尚未闭合。MPCore 基址已由运行
  证据定为 `0xE000E000`；串口寄存器语义、CPU 型号仍是假设。
- 没有签名、没有重打包、没有升级容器处理；固件文件全程只读。
- 另见 [NOTICE.md](NOTICE.md) 与 [docs/validation.md](docs/validation.md)。

许可：overlay 与工具为 **GPL-2.0-or-later**；上游 QEMU 保留其自身许可。
