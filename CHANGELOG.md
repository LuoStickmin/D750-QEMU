# Changelog

## v0.2.7 — 2026-11-10

D780（E6）实跑准备与首个真实外设路径；发布新二进制。

### 发行

- Linux x86-64 二进制：100,651,184 字节，SHA-256
  `c92876f841a3476fed059514aa2198974bba2a590a745ef51bb2f30cfc0a74dd`；
  `MANIFEST.json.binary` 与 `binary/qemu-system-arm.sha256` 已同步。

### 机器

- 新增 `e6-prep=on`：把 D780 页表（payload+`0x10000`）里的 1 MiB
  物理地址补成 identity section 描述符；映射 boot SRAM `0x04000000`、
  栈区 `0xC0000000`，并把 `0x20022300` 预置为 1。
  `tools/run.py` 同步 `--e6-prep`。

### E6 实跑

- `eg1510` 装到 `0x10020000`，从 header 分支进入 `0x1002BC88`；
  修好页表后 **0 异常**，MMU/SCTLR、`0x100202B8`、`0x1002D700`、
  `0x10020394` 全部跑通；
- 进入 `0x0426/0x0428` 外设块：`0x04264000=0x21`、
  `0x04264020=0x153B0902`、`0x0428102C=0x01630000`、
  `0x04281020=0x00090000`，最后在 `0x1002C298` 附近循环。
- E5 候选入口 `0x1037C518`/`0x1037C8C8` 实测都是普通函数（返回 LR），
  loader 入口仍未定位。

## v0.2.6 — 2026-11-10

E5（D850）实跑准备：payload 可装在 flash 窗口、新增 handler RAM；发布新二进制。

### 发行

- Linux x86-64 二进制：100,648,336 字节，SHA-256
  `ca72bf8d3acdb1dcb9ab2fbe74f1c287034668a990d0fe98617dda7fb03fa5e3`；
  `MANIFEST.json.binary` 与 `binary/qemu-system-arm.sha256` 已同步。

### 机器

- `payload-base` 现在允许落在 flash 窗口（`0x10000000` 起），用于 E5 的
  `0x10000000` 装载基址；`flash-size` 需覆盖镜像（D850 用 32M）。
- 新增 `aux2-base`/`aux2-size`：在任意地址加一块 RAM（E5 的 handler bank
  `0x40000000`）；`tools/run.py` 同步 `--aux2-base`/`--aux2-size`。

### E5 实跑

- `D850_b1330_131.bin` 装到 `0x10000000`，从 reset `0x1037CBA8` 起跑：
  **0 异常**，执行到 `0x1037CBC4` 后 `pop {r4,pc}` 从我们的零栈弹出 PC=0，
  随后在低内存滑到 halt；没有 MMIO。
- 该 reset 目标是一小段 `b/ldrb/str/pop` 桩，说明它依赖 boot ROM/loader
  预先设置的 r0/r4/栈；与 D750 的 `LR=0` 同类问题。E5 的 handler bank
  `0x40000000` 已可映射，但还没有内容。

## Unreleased — 2026-11-09

Z 系列 QEMU 引导方式调研与 E6→E5→E4 版图（仅文档/证据，无机器改动）：

- Z6/Z7/Z8/Z9 QEMU 均不还原 boot ROM：用户提供**提取后的 MAIN**，映射到
  建模基址（Z6/Z7 `0x10020000`、Z7II MAS Cortex-A7、Z8/Z9 四核 AArch64），
  用显式 fixture/virtual ROM/guest loader 补早期环境，主机侧 assisted
  startup 调用原始初始化函数并投递电源/MCU/按键输入。
- D850 (E5) 与 D780 (E6) 官方固件用同一套密钥解密成功：
  D850 `b1330` reset `0x1037CBA8`、异常向量 `0x4002xxxx`（单独 boot ROM）；
  D780 `eg1510` 以 `EA002F20` 分支 + 版本头开始，无基址向量表，
  `ex1510` reset `0x0800053D`。
- 形成 E6→E5→E4 反推链：E6 按 Z6/Z7 的 assisted startup 处理，E5 增加
  `0x10000000`/`0x40000000` 窗口，E4 维持 `0x90020000`。
- 详见 docs §2.7 与 `evidence/m1/tracks/e6-e5-e4-layout.txt`。

## v0.2.5 — 2026-11-09

D3300 跨机型固件与 EXPEED 寄存器块 stub；新二进制作为 Release v0.2.5 发布。

### 发行

- Linux x86-64 二进制：100,645,120 字节，SHA-256
  `398909e06fb15272fbdb8ca4555c46197e4d1301ebc39863921ce48fbcabcc90`；
  `MANIFEST.json.binary` 与 `binary/qemu-system-arm.sha256` 已同步。

### 机器

- 新增 `io-stub=on`：把 `0xA2000000`、`0xAD000000`、`0xAE000000`、
  `0xA3400000` 映射成寄存器堆，并让 `0xAE00060C` 读回 1；
  `tools/run.py` 同步 `--io-stub`。

### 跨机型

- `davidgfb/NikonHacker` 的 `D3300_0102.bin`（24.6 MB）用**同一套 D750 密钥**
  解密，得到 `a860_010101.bin`（768 KiB）与 `b860_102.bin`（23.8 MiB）。
- b860 的向量表与 b1010 前 0x20 字节相同，reset = `0x90352FE0`；在
  `payload-base=0x90020000`、`entry=0x90352FE8` 下 0 异常运行，访问同一组
  `A2/AD/AE` 外设块；D3300 写 `0xAE00060C=1`，D750 轮询它。
- D750 加 `io-stub` 后越过该轮询，继续到 `0x9027E5xx`（ARM 代码）后进入
  下一个等待。
- 结论：Nikon-Patch / NikonHacker **没有 flash dump 或 boot ROM**；可复用的
  是跨机型固件、同一套密钥、同一加载基址和同一组外设块。

## v0.2.4 — 2026-11-09

Nikon-Patch IDA 布局给出真实装入基址；新二进制作为 Release v0.2.4 发布。

### 发行

- Linux x86-64 二进制：100,633,336 字节，SHA-256
  `90fbeddb79e67bbb849434b5b4bb76169f48028ce07da3036cfec7400027daef`；
  `MANIFEST.json.binary` 与 `binary/qemu-system-arm.sha256` 已同步。

### 机器

- 新增 `payload-base=<addr>`：b1010 装入基址，默认 `0x90000000`；
  Nikon-Patch 的 `D750_Setup_RAM_1.10.idc` 使用 **`0x90020000`**。
  `tools/run.py` 同步 `--payload-base`。

### 发现

- Nikon-Patch / NikonHacker 仓库**没有 flash dump 或 boot ROM**；
  `davidgfb/NikonHacker` 有 D3200/D3300 的官方加密固件（非 dump）。
- `D750_Setup_RAM_1.10.idc`/`1.02.idc` 给出了真实加载布局：
  ROM 基址 `0x90020000`、reset `0x9027D524`、flash 来自文件内嵌 overlay、
  另有 16 KiB 拷到 `0x10500000`；此前 `0x90000000` 的装法整体错位 `0x20000`。
- 用 `payload-base=0x90020000` + 真实 reset `0x9027D52C` 重跑：0 异常，
  初始化 **`0xA3400000`** 外设块（通道每 `0x1000`、首寄存器 `+0x400`），
  然后轮询 `0xAE00060C` 8048 次而挂住。

## v0.2.3 — 2026-11-09

反推 loader 段表并加入可复现的搬运开关；新二进制作为 Release v0.2.3 发布。

### 发行

- Linux x86-64 二进制：100,631,632 字节，SHA-256
  `a8d63f43df43a9b5ed908f235821689c508c9265b2d6ca1e72aea510d4cec721`；
  `MANIFEST.json.binary` 与 `binary/qemu-system-arm.sha256` 已同步。

### 机器

- 新增 `loader-copies=on`：按 b1010 `0x25D760..0x25D7B8` 的 4 条
  `(dest, src, size)` 记录，把 flash 段搬进内存 payload；C 段越界时先补零
  扩展缓冲。`tools/run.py` 同步 `--loader-copies`。

### 发现

- 段表链式关系完全自洽：A.dest+A.size=B.dest、A.src+A.size=B.src、
  B.src+B.size=`0x1003FD16`（表项 `0x25D7D0` 的值）、
  C.src+C.size=`0x100F48CC`（越过 config 槽）。
- A 是 ARM `ldr pc` 跳转表，D 是 `movs r0,#0; bx lr` 默认回调；C 的目标区
  在镜像里是 0 占位。
- 应用 4 条拷贝后完整布局路径未变（没有 PC 进入 `0x91xxxxxx`），说明这些段
  在当前 b1010 路径上尚未被调用；段表和搬运机制已可复现。

## v0.2.2 — 2026-11-09

继续推进 SVC 返回与 veneer 重定位；新二进制作为 GitHub Release v0.2.2 发布。

### 发行

- Linux x86-64 二进制：100,628,416 字节，SHA-256
  `5f5b5a4d9db2063580e6cd69aba0dd903814565fa944521e8c3192c5f4584875`；
  `MANIFEST.json.binary` 与 `binary/qemu-system-arm.sha256` 已同步。

### 机器

- `vector-fix` 的 SVC handler 现在会恢复 SPSR.T（`mrs/orr/msr/movs`），
  使 `swi` 返回后按 Thumb 继续，而不是把 Thumb 字节当 ARM 执行。
- flash 镜像改为与 payload 共用补丁管线（直接读入宿主缓冲后注册 ROM blob），
  因此 `veneer-slot` 对 payload 和 flash 同时生效。
- 新增 `veneer-slot=<payload offset>`：把某个 `ldr pc,[pc,#-4]` veneer 的
  目标标记为 Thumb（+1）；`tools/run.py` 同步 `--veneer-slot`。

### 发现

- `0x80000000` 不是设备 ID，而是 `{pointer, count}` 工作队列槽；
  `0x10066490` 经 ARM `swi #0xE8BD` veneer 把它交给内核处理。
- b1010 flash 镜像里的 veneer 表**未重定位**（目标缺 Thumb 位）；用
  `veneer-slot=0x14e494` 修正后，完整 20 MiB b1010 + TTBR0 (`0x201E0000`)
  + `vector-fix` 的运行达到 **0 undefined、1 SVC、0 abort**，并继续深入约
  130 万条 TB，最终仍因 `LR=0` 在低内存滑到 halt。
- 结论：下一步的关键是 loader 的重定位表/SVC 服务语义，而不是继续加设备。

## v0.2.1 — 2026-11-09

三条无输入验证 + 后续 TTBR0 实验；新二进制作为 GitHub Release v0.2.1 发布。

### 发行

- Linux x86-64 二进制：100,624,848 字节，SHA-256
  `aa4f2a5f8bf97db4d2d310ddac4e0b2289ec98602edec854ba38184ca49cb891`；
  `MANIFEST.json.binary` 与 `binary/qemu-system-arm.sha256` 已同步。
- 新增机器选项：`flash-size`、`aux-ram-size`、`mmu-table`、`vector-fix`
  （`tools/run.py` 同名参数）。

- 静态：b1010 内无 `0x9025D700` 调用者、无 BSS 回调 `0x902A2EA0/A4/A8` 的
  写入者；描述符表解析为 4 条 `(dest, src, size)` 拷贝项，源地址全部落在
  “b1010 映射在 flash”的假设内。
- 布局枚举：12 种 flash 布局中，只有 **b1010@`0x10000000` + Thumb 修正**
  能跑出连贯 A-core 路径（39 个基本块 → 正常 SVC）；a1010 各基址均为数据、
  M 指令崩溃或提前返回。
- M-core：a1010 在 `mps2-an385`/`cortex-m3` 上零异常启动，随后卡在
  `0x00300F40` 时钟/PMU 轮询，确认 M-core 固件。
- **TTBR0 验证**：机器新增 `flash-size`、`aux-ram-size`、`mmu-table`、
  `vector-fix`；用完整 20 MiB b1010 作 flash、`mmu-table=0x201E0000`、
  `aux-ram-size=4M`、`vector-fix=on` 跑通：镜像内 `0x201E2200` 是有效
  TTBR0 指针，MMU init 不再 fault；全程 0 undefined、1 次 SVC、0 abort，
  并抓到 `0x80000000/0x80000004` 设备探测。对照（`vector-fix=off`）SVC 后
  立刻 1.1M 次 undefined。
- 结论：flash 窗口更像 b1010 镜像；`0x1002CB8C` 是 b1010 flash 副本中的
  Thumb veneer；缺的是一级 boot ROM（`0x90020000` 向量表、BSS 回调）。
- 新增 `docs/m1-tracks-2026-11-09.md`/`.en.md` 与
  `evidence/m1/tracks/`（布局矩阵、b1010 flash 轨迹、TTBR0 运行、M-core 日志）。

## v0.2.0 — 2026-11-08

M1 实跑轮：启动桩在 QEMU 里跑通并抓到第一条 a1010 MMIO；同时发现目标镜像
是 M-profile，A-core 启动链并未闭合。固件文件仍然零修改。

### 发行

- 新构建的 Linux x86-64 二进制作为 GitHub Release **v0.2.0** 附件发布：
  100,608,072 字节，SHA-256
  `3b97f46e797a2f110c1aef554c51b29f807fae7ba9ac8162eeb6ae45e08fd817`。
  包含 `boot-mode=stub|entry`、`a1010-base`、`thumb-fix`、`mmu-bringup`、
  `mpcore-base`；`MANIFEST.json.binary` 与 `binary/qemu-system-arm.sha256`
  已同步。v0.1.1 仍保留为历史附件。

### 新增

- 机器选项：`boot-mode=stub|entry`（默认 `stub`）、`a1010-base`（默认
  `0x10018000`）、`thumb-fix`（内存内修 `bx` 字面量）、`mmu-bringup`
  （identity 页表 + DACR/TTBR0/TTBCR 垫片 + config 槽回填）、`mpcore-base`。
- `d750-a1010-io:` 日志：把“来自 a1010 地址范围的未建模访问”单独标出；
  `tools/run.py` 汇总为 `mmio.a1010_events` / `mmio.first_a1010` 并打印。
- `tools/run.py`：`--boot`、`--a1010-base`、`--thumb-fix/--no-thumb-fix`、
  `--mmu-bringup/--no-mmu-bringup`、`--mpcore-base`、`--trace`。
- `tools/stub_trace.py`（零依赖启动桩模拟器）与 `tools/m1_analyze.py`
  （M1 静态分析四件套）：来自 2026-11-07 更新包，补 SPDX/来源头后原样保留。
- `docs/m1-boot-chain.md` / `.en.md` 与 `evidence/m1/`：M1 实跑记录、GDB
  现场、第一条 MMIO、失败点与复现命令。

### 修正

- **MPCore 基址 `0x1E000000` → `0xE000E000`**。依据：第一条 a1010 MMIO 是
  `wr 0xE000E180 ← 0x00100000`（GIC `ICENABLER0`），同一运行还有
  `gic_cpu_write: Bad offset 80`。
- 启动桩的本地 init 会写 `SCTLR=0x1C05` 打开 MMU，页表基址来自 config 槽
  `0x100F48C0`；不处理时 TTBR0 会被写成 `0x42` 并在 `0x9025DA84` 立即
  prefetch abort。这是 1107 更新（默认跳过该 init）没有覆盖的路径。
- 1107 的 `a1010-base=0x10018000` 与 Thumb 位在解码上成立，但 a1010 是
  **大端 Cortex-M 镜像**（MRS/MSR BASEPRI、M-profile 向量表），不是 A-core
  的下一阶段；M1 记为“到目标但未闭合”。

### 兼容性

- `boot-mode=entry` 保留 M0 行为；M0 证据（`evidence/m0*`）仍可用
  `--boot entry` 复现，只是 flash 装入地址默认已改为 `a1010-base=0x10018000`，
  复现旧证据时需同时加 `a1010-base=0x10000000`。
- 主机侧测试 26 passed；固件/密钥/改后镜像仍不入库。

## Unreleased — 2026-11-06

### 文档

- 新增 [`docs/hardware-test.md`](docs/hardware-test.md)（+ `.en.md`）：实机测试的
  前置条件、风险、最小流程与判据。
- 明确 D750 使用**包装 A**（`0x00` 起 32 个空格，无 20 字节带密钥摘要）；
  K8 / `STALE` 只影响包装 B（D850/D5 那类），与 D750 无关。
- 记录容器可逐字节复现：无修改重打包 = stock bit-identical；stock + 改表模块
  = `9c88f3cc…`；容器仅 36 B 差异（`0x3D6575..0x3D665C`、`0x148DC29..2A`）。
- `bitrate/README.md`、`SUMMARY.md`、`README.md`、`PRODUCT.md` 同步上述状态，
  并把重打包/独立验证器指向同作者的
  [Nikon-Expeed-4-and-5-firmware-tool](https://github.com/LuoStickmin/Nikon-Expeed-4-and-5-firmware-tool)
  仓库。
- 实机仍未验证：更新器接受度（含同版本重刷）、编码器行为、写卡/发热/回放。
- 新增 [`analysis/menu-bitrate-feasibility.md`](analysis/menu-bitrate-feasibility.md)
  （中文正文 + 文末英文版）：真正新增第三项 Movie quality 码率的可行性分析；
  当前卡在菜单描述符，没有生成第三项镜像。
- 新增 [`bitrate/MENU64.md`](bitrate/MENU64.md)（中文正文 + 文末英文版）与
  `bitrate/d750_menu_patch.py` / `test_d750_menu_patch.py`：复用现有两项的
  `64 Mbps HQ` / `Stock` 菜单可见版，英文/中文同长度改标签；**不是第三项**，
  相机 UI 未验证。

## v0.1.1 — 2026-11-06

修复 v0.1.0 评审中发现的证据与可用性问题；行为变化只涉及 `strict` 模式、
`halt` 记录格式和 `tools/run.py` 的汇总/退出码。

### 修复

- **`strict=on` 现在真的会停**：第一条未建模访问记为 `d750-strict:`
  （地址/宽度/方向/PC），随后停止本次运行；不再把未映射访问变成 guest abort。
  旧行为会让异常向量落到低内存 NOP 滑梯并滑进 halt 窗口，看起来像一次成功
  的 M0。
- **halt 状态校验**：`d750-halt:` 记录新增 `return_ok=` 与 `mode=`；只有
  SVC 模式、`LR=0xFF0`、`SP=RAM 顶` 才算正常返回。`run.py` 对
  `return_ok=false` 返回退出码 6。
- **`tools/run.py`**：记录 `payload_sha256` / `flash_sha256` / `*_size`；
  汇总 `status`；解析 `d750-strict:` 并写入 `session.json.strict`；`--strict`
  停止时退出码 7。旧的 v0.1.0 二进制输出仍可解析（无 `return_ok` 视为未知）。
- **构建后自检路径**：`Setup-D750.ps1` 与 `docs/build.md` 使用
  `.build/src/qemu-<版本>/build/`，与实际产物一致。
- **`bitrate/README.md` 重写**：原文件是双重编码的乱码（42/103 行不可读），
  按英文版重建，并补充“CRC/打包验证依赖未发布工具”的可复现边界。
- **文档一致性**：M0 实测时间统一为证据文件里的 0.39 s（原写 0.18 s）；
  `MANIFEST`/`PRODUCT` 的 bitrate 测试标注“需 `D750_MODULE`，否则 4 skipped”；
  清理英文文档里未翻译的中文片段；补充中文 README 目录。
- **许可**：`bitrate/*.py` 与 `analysis/tiff_scan.py` 补 SPDX 头。

### 新增

- `tools/manifest.py`：重新生成/校验 `SHA256SUMS` 与 `MANIFEST.json.files`。
- `.github/workflows/ci.yml`：Ubuntu + Windows 上跑主机侧测试、bitrate 测试
  （无模块时跳过）和清单校验。
- `CHANGELOG.md`。

### 兼容性

- 机器选项与命令行不变；M0 的寄存器结果与 v0.1.0 一致。
- 新的 Linux 二进制作为 v0.1.1 Release 附件发布，`binary/qemu-system-arm.sha256`
  与 `MANIFEST.json.binary` 同步更新。

## v0.1.0 — 2026-11-05

首个公开快照：`nikon-d750` QEMU 验证原型（M0）、LCD dump 管线、1080p
64/60 Mbps 改表工具、双语文档与 M0 证据。
