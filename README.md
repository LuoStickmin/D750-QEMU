# D750 QEMU 验证原型（`nikon-d750`）

> [English](README.en.md) | 中文

> **更新日志（近期）**
>
> | 日期 | 进展 |
> | --- | --- |
> | 2026-11-24 | **A-core 启动链推进**：修正布局为 `0x90020000`/reset `0x9027D524`，补 `0xB8000000` IRAM 与 A2/A120/A161/A300 stubs；真实 reset → MMU 页表 → `0x1000E200` 下一阶段镜像 → `svc #5`/A300 服务循环。仍无 console/GUI，详见 [docs/acore-boot.md](docs/acore-boot.md) |
> | 2026-11-23 | **M-core 实跑 + v0.2.9 准备**：新增 `nikon-d750-mcore`（Cortex-M4），确认 a1010 是 BE8 Firmware A；从 reset `0xC20D` 跑到 `0x440CE000` 引脚/时钟块，`STIR=0x8F` 后停在 `0xC04A` 的 idle，**0 异常、0 UART**。见 [docs/mcore.md](docs/mcore.md) |
> | 2026-11-10 | **E5/E6 实跑 + v0.2.8**：D850 reset `0x1037CBA8` 确认是 boot-service 桩，虚拟 `0x40000000` boot ROM 只放 `bx lr` 仍缺入口上下文；定位到 E5 镜像内完整 init（`0x1035CE30..0x1035D040`，自建页表并设 TTBR/SCTLR/VBAR）；D780 用 `e6-prep` 修页表后 **0 异常**进入 `0x0426/0x0428` 外设块，A15 下进入 `0x04266000` 定时器块。详见 [docs/m1-tracks-2026-11-09.md](docs/m1-tracks-2026-11-09.md) 与 `evidence/m1/tracks/e5-*` |
> | 2026-11-09 | **三条无输入验证 + 六轮跟进**：静态调用链、12 种 flash 布局、M-core 启动 → TTBR0 验证 → 工作队列槽/veneer 重定位（**0 undefined、1 SVC、0 abort**）→ loader 段表 → Nikon-Patch IDA 真实基址 **`0x90020000`** → **D3300/D850/D780 固件同密钥解密**（E6→E5→E4 版图：D780 头部+branch、D850 reset `0x1037CBA8`/handler `0x4002xxxx`、D750 `0x90020000`），`io-stub` 越过 `0xAE00060C`。详见 [docs/m1-tracks-2026-11-09.md](docs/m1-tracks-2026-11-09.md) |
> | 2026-11-08 | **M1 实跑 + v0.2.0**：桩 → `0x1002CB8C`（Thumb，`args=0/0/2/0/1`，`LR=0x9025D754`），首条 MMIO `wr 0xE000E180 ← 0x00100000`；MPCore 基址修正为 **`0xE000E000`**；发现 a1010 是 M-profile 镜像，M1 记为“到目标未闭合”；Linux x86-64 二进制已作为 [Release v0.2.0](https://github.com/LuoStickmin/D750-QEMU/releases/tag/v0.2.0) 发布。详见 [docs/m1-boot-chain.md](docs/m1-boot-chain.md) |
> | 2026-11-07 | **静态定位**：a1010 基址 `0x10018000`、入口文件偏移 `0x14B8C`、Thumb 位、config 槽 `0x100F48C0/C4/C8`；原始材料在 `update_1107.zip` |
> | 2026-11-06 | **v0.1.1**：M0 通过、strict/halt 证据修复、LCD dump 管线；见 [CHANGELOG.md](CHANGELOG.md) |
> | 2026-11-05 | **v0.1.0**：首个公开快照（M0、LCD dump、双语文档） |
>
> 完整变更与兼容性说明见 [CHANGELOG.md](CHANGELOG.md)。

---

> **本仓库只保留 QEMU 验证原型**。总览见 [SUMMARY.md](SUMMARY.md)，法律与
> 贡献边界见 [CONTRIBUTING.md](CONTRIBUTING.md)。

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

- [项目总览](SUMMARY.md)
- [贡献与法律边界](CONTRIBUTING.md)
- [1. 当前状态](#1-当前状态先读这一节)
- [2. 快速开始](#2-快速开始)
  - [2.1 构建（需要 C 工具链）](#21-构建需要-c-工具链)
  - [2.2 跑](#22-跑)
  - [2.3 只做静态核对](#23-只做静态核对)
  - [2.4 第一次实跑（M0 已通过）](#24-第一次实跑m0-已通过)
  - [2.5 M1 实跑（启动桩 → a1010 目标）](#25-m1-实跑启动桩--a1010-目标)
  - [2.6 A-core host-assisted 启动](#26-a-core-host-assisted-启动)
- [3. 机器模型（一句话版）](#3-机器模型一句话版)
  - [3.1 GUI 与 CMOS 现在到哪一步](#31-gui-与-cmos-现在到哪一步)
  - [3.2 M-core（a1010 Firmware A）](#32-mcorea1010-firmware-a)
- [4. 已经拿到的静态证据（真实字节）](#4-已经拿到的静态证据真实字节)
- [5. 目录](#5-目录)
- [6. 与 z7-qemu / z9-qemu 的关系](#6-与-z7-qemu--z9-qemu-的关系)
- [7. 边界](#7-边界)

---

## 1. 当前状态（先读这一节）

当前**已经完成并验证**的部分：

> **最新（2026-11-24）**：M-core `a1010` 已能跑到 idle；A-core host-assisted
> 从真实 reset `0x9027D524` 跑到 `0x1000E200` 下一阶段镜像和 `svc #5`/A300
> 服务循环。**仍未完成整机 boot**；细节见 [docs/acore-boot.md](docs/acore-boot.md)
> 与 [docs/mcore.md](docs/mcore.md)。

| 项目 | 状态 |
| --- | --- |
| 静态证据：向量表、入口、页表、flash/RAM 窗口、串口候选 | ✅ 在真实 `D750_0115` 模块上跑通，见 [docs/findings.md](docs/findings.md) |
| 板级源码 `nikon-d750-lab.c/.h` | ✅ 已写（QEMU 11.1 API；10.2.4 由 prepare 脚本做文本适配，未实际编译验证） |
| overlay 安装脚本 `qemu/prepare_source.py` | ✅ 幂等，单测覆盖 11.1 / 10.2 / 拒绝未知版本 |
| `fwscan` / `run` / `probe` / `build` 工具 | ✅ 已写；`probe` 手工对**已安装的 stock QEMU `-M virt`** 做过真实 RSP 联调（测试套件只覆盖协议编解码） |
| 主机侧测试 | ✅ `python tests/run_tests.py` → 27 个用例（1 个依赖本机 stock QEMU，缺失时会失败） |
| 板级 C 代码编译 | ✅ 已在 WSL Ubuntu 26.04（gcc 15.2）+ QEMU 11.1.0 上编译通过 |
| `nikon-d750` 机器实跑 | ✅ **M0（历史）**：早期在 `0x90000000`/入口 `0x9027D52C` 验证函数可执行并返回；后续确认正确布局是 `0x90020000`/reset `0x9027D524` |
| M1 启动链实跑 | ⚠️ **历史实验**：桩 → `0x1002CB8C`（Thumb）→ 第一条 MMIO `0xE000E180`；`0x1002CB8C` 已确认属于 a1010（M-core），不是 A-core 下一阶段。见 [docs/m1-boot-chain.md](docs/m1-boot-chain.md) |
| M1 机器选项 | ✅ `boot-mode=stub`、`a1010-base`、`thumb-fix`、`mmu-bringup`、`mpcore-base`；固件文件零修改 |
| M-core（`a1010` Firmware A） | ✅ **新增 `nikon-d750-mcore`**：BE8 reset `0xC20D` → `0x400F` mailbox → `0x440CE000` 引脚/时钟 → `STIR=0x8F` → idle `0xC04A`；3 s **0 异常、0 UART**。见 [docs/mcore.md](docs/mcore.md) |
| A-core 启动链（host-assisted） | ⚠️ **到下一阶段镜像/T-Kernel 服务循环**：reset `0x9027D524` → MMU 页表 @`0xB8000000` → 镜像 `0x1000E200` → `svc #5`/A300 轮询；plugin 已抓到 flag 写者 `0x1000E240=2`（跨核清零仍未观测）；无 console/GUI。见 [docs/acore-boot.md](docs/acore-boot.md) |
| E5（D850）实跑 | ⚠️ **缺 boot ROM 入口上下文**：`0x1037CBA8` 是 boot-service 桩；只放虚拟 `0x40000000` 返回桩仍会 `pop` 到 PC=0。已定位镜像内 init `0x1035CE30..0x1035D040`，下一步走 host-assisted 入口。见 `docs/m1-tracks-2026-11-09.md` 与 `evidence/m1/tracks/e5-*.txt` |
| E6（D780）实跑 | ✅ **已进入真实外设初始化**：`e6-prep` 修页表后 0 异常跑到 `0x0426/0x0428` 块；`cortex-a15` 下 0 undefined、2 SVC，进入 `0x04266000` 定时器块，当前在 `0x1011C000` 附近循环。见 `docs/m1-tracks-2026-11-09.md` |
| E5/E6 机器选项 | ✅ `flash-size`、`aux2-base`/`aux2-size`、`virtual-boot-rom`、`e6-prep`、`cortex-a7/a15`；证据在 `evidence/m1/tracks/` |
| strict 诊断 / halt 校验 | ✅ 第一条未建模访问记 `d750-strict:` 后停止（`run.py` 退出码 7）；halt 记录带 `return_ok=`，异常路径退出码 6 |
| LCD 扫描输出/dump 管线 | ✅ 可配置帧缓冲 → PPM；测试卡验证通过；固件画面仍无 |
| M2（串口）/ M3（补设备） | ⏳ UART 仍为 0 B；A-core host-assisted 也未访问 `0x80005010..14`/`0x440C4xxx`；下一步用 plugin/watchpoint 抓访问和 flag 写者 |
| 完整相机 UI / ISP / CMOS / 存储 | ❌ 不在本原型范围 |

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
  全部是 `0 MMIO`，`0x9025D700` 则进入无 MMIO 的等待循环。**`0x9025D700`
  的调用者不在 `b1010` 里**；后续布局枚举进一步表明 flash 窗口更像 `b1010`
  的副本，真正缺的是一级 boot ROM（见 §2.5 与
  [findings §11.4](docs/findings.md#114-候选入口扫描负结果)）。

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

> **不要把它读成“A-core 的下一阶段”**：`0x1002CB8C` 属于 a1010（M-core，
> `0x100240AC` 的 `MRS/MSR BASEPRI` 是 M-profile 指令），不是 A-core 的
> 下一阶段。A-core 的正确路径见 §2.6 和 [docs/acore-boot.md](docs/acore-boot.md)。

### 2.6 A-core host-assisted 启动

2026-11-24 新增。真实布局是 `payload-base=0x90020000`、reset `0x9027D524`；
`tools/acore_boot.py` 会在 `0x1000E24C` 断下、清零共享 boot flag
`0x100A6704`，再继续执行：

```sh
python3 tools/acore_boot.py \
  --qemu ~/d750-build/src/qemu-11.1.0/build/qemu-system-arm \
  --payload "$FW/b1010_115a.bin" \
  --out runs/acore-boot --seconds 5
```

预期：`PC≈0x10025474`（A300 状态轮询/SVC 服务循环）、`uart=0 B`。
这是**诊断夹具**，不是自然上电；细节和边界见 [docs/acore-boot.md](docs/acore-boot.md)。

---

## 3. 机器模型（一句话版）

| 项目 | 取值 | 依据强度 |
| --- | --- | --- |
| CPU | 1× Cortex-A9（`-smp 2` 可试）；E6 可切 `cortex-a7`/`cortex-a15` | 中：ARMv7 Thumb-2 + VFP/NEON + T-Kernel 字符串 |
| 主 RAM | `0x90000000`，默认 128 MiB | 高：`0x90020000` 页表字面量、`0x9027D52C` 等指针 |
| 主镜像装入 | E4 D750 `b1010` @ `0x90000000`；E5 D850 @ `0x10000000`；E6 D780 @ `0x10020000` | 高：各机型运行证据 |
| 初始 PC | D750：`boot-mode=stub` 为 `0x9025D700`，`entry` 为 `0x9027D52C`；E5：`entry=0x1037CBA8`；E6：header 分支 `0x1002BC88` | 运行证据：各机型都实跑过 |
| 低内存 | `0x0..0xFFFF` RAM；`0xFF0` 是 halt 窗口，`0x1000` 是 M1 MMU 垫片 | 运行证据：入口会向 `0x0` 写向量字 |
| 辅助启动 | SP=RAM 顶、LR=`0xFF0`、r0=0（entry 模式） | 运行证据：入口 `push`/`pop` 后返回 |
| Flash 窗口 | `0x10000000`，默认 8 MiB；E5 D850 用 `flash-size=0x2000000`（32 MiB）；`-bios` 镜像按 `a1010-base` 装入（默认 `0x10018000`） | 中：a1010 在该基址下 `bx` 目标落在 Thumb 序言；但镜像本身是 M-profile，见 M1 文档 |
| E5 handler / E6 prep | `aux2-base`/`aux2-size` 把 `0x40000000` 映射为 RAM；`e6-prep` 把 D780 页表补成 identity section 并预置 `0x20022300` | 运行证据：E5 虚拟 boot ROM、E6 0 异常 startup |
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

### 3.2 M-core（`a1010` Firmware A）

M-core 不再是“把 a1010 塞进 A-core 的 flash 窗口”，而是独立机器
`nikon-d750-mcore`：

- CPU `cortex-m4`，1 MiB flash @0，256 KiB SRAM @`0x20000000`；
- a1010 是 BE8：前 16 个**大端**向量项，MSP `0x2000F8C0`、reset `0x0000C20D`；
- QEMU 用 LE 读向量表，机器只在 flash 副本里交换前 `0x40` 字节；SP/PC 仍从
  原始大端字节取；
- 在 `0xE000ED00` 放 0x100 字节大端 SCB 窗口，修 VTOR/CPACR；
- `0x400F2000` / `0x400F3000` 用“读回最后值”的诊断寄存器堆越过启动 mailbox，
  这是夹具，不是硬件模型；
- 8 次 `0x440CE000` 引脚/时钟访问后，`STIR=0x8F`，停在 `0xC04A` 的
  `bx lr` self-loop；3 s 内 **0 异常、0 UART**。

细节、反汇编与 UART 候选扫描见 [docs/mcore.md](docs/mcore.md)，原始日志见
`evidence/mcore/`。**边界**：这只证明 M-core 能走到 idle，不代表 RTOS/console/
GUI 已经启动，也不能替代 A-core 的 boot ROM 问题。

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
│   ├── acore_boot.py           host-assisted A-core 启动 + flag/watchpoint
│   ├── memtrace.c              过滤式 TCG plugin（运行时内存访问）
│   ├── stub_trace.py           启动桩单步模拟器（1107 更新工具，零依赖）
│   ├── m1_analyze.py           M1 静态分析四件套（1107 更新工具，disasm 需 capstone）
│   ├── manifest.py             重新生成/校验 SHA256SUMS 与 MANIFEST
│   └── build.py                下载/解包/overlay/构建/记录
├── tests/                      27 个主机侧测试（无需 QEMU 构建）
├── analysis/
│   ├── d750-0115.json          真实镜像的扫描结果
│   ├── lcd-testcard.png        LCD 管线测试卡（主机写入）
│   └── ...                     仓库里已有的其他固件分析产物（见下）
├── binary/                     COPYING + 说明（二进制通过 GitHub Release 发布）
├── evidence/                   M0 / M1 / GDB / LCD / boot-scan 运行证据
├── docs/                       findings / m1-boot-chain / mcore / acore-boot / architecture / validation / build / gui-cmos（含 .en.md）
├── SUMMARY.md / SUMMARY.en.md  QEMU 原型总览
├── CONTRIBUTING.md / .en.md    法律与贡献边界
├── README.md / README.en.md    本文与英文版
├── PRODUCT.md  MANIFEST.json  SHA256SUMS
├── CHANGELOG.md                版本与修复记录
├── LICENSE                     GPLv2 文本（GPL-2.0-or-later）
├── Setup-D750.ps1  Run-D750.ps1
└── .build/ .local/ runs/       本地生成物（Git 忽略）
```

`analysis/` 里只有 `d750-0115.json` 和 `lcd-testcard.png` 由本 QEMU 产品生成；
其余（TIFF、patch 等）是同一仓库里已有的固件分析产物，随仓库保留，但不在
QEMU 产品的验收范围内。

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
  MMIO，但目标镜像是 M-profile；A-core host-assisted 已从真实 reset 跑到
  `0x1000E200` 的 SVC/A300 服务循环，但**不是自然上电、没有 T-Kernel 服务/
  console**。E5/E6 的跨机型结果来自辅助入口/修页表，同样不是自然上电。
  MPCore 基址已由运行证据定为 `0xE000E000`；串口寄存器语义、CPU 型号仍是假设。
- 本仓库不提供签名、重打包工具或升级容器处理；容器级复现依赖同作者的
  外置工具链，固件文件全程只读。
- 另见 [NOTICE.md](NOTICE.md) 与 [docs/validation.md](docs/validation.md)。

## 8. 还需要什么（输入需求）

三套目标的进度不同：**E6 D780** 已能跑到真实外设初始化（`0x0426/0x0428`），
下一步是建模该块；**E5 D850/D5** 已定位镜像内 init，但缺 boot ROM 的调用上下文
（栈/LR/r4）；**E4 D750** 的 A-core 已由 host-assisted 路径到 SVC/A300 服务
循环，但仍缺一级 boot ROM/T-Kernel 服务。共同最缺的仍是整片 dump：

1. **整片 SPI flash dump**（D750/D850/D5 任意一台）——最直接，可能包含 boot
   分区或第一级 loader；可用 CH341A/测试夹读取，或从维修渠道获取。
2. **Nikon 服务软件/维修固件里的 recovery/boot 镜像**（如 Tornado NKN 等）。
3. **E5 的 boot ROM 本体或 `0x40000000` 附近 RAM dump**——虚拟 `bx lr` 桩已
   证明不足以补出入口契约（见 `evidence/m1/tracks/e5-vbr-run.txt`）。
4. **其他机型整片 dump**（D5100/D7000/D800）——用于理解 Nikon 的 boot 分区结构。
5. **硬件 UART 启动日志**——确认 boot ROM 之后第一段代码的加载地址与大小。

已经具备、无需再提供：D750/D850/D5/D780 的解密镜像、E4/E5/E6 机器、
`io-stub`/`early_control` 等模型、E5 镜像内 init 地址，以及各代向量/加载基址结论。
`0x40000000` 的 relocation 反查已完成（镜像内没有拷贝循环，见
`evidence/m1/tracks/e5-40000000-reloc.txt`）。

没有新输入时仍可做：E5 走 host-assisted 入口（`0x1035CE30` 附近的 init）；
E6 建模 `0x0426/0x0428` 寄存器块；A-core 继续补 T-Kernel SVC 语义/抓
`0x100A6704` 写者，M-core 继续找 console/UART 路径。

许可：overlay 与工具为 **GPL-2.0-or-later**；上游 QEMU 保留其自身许可。
