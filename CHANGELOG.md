# Changelog

## Unreleased — 2026-11-09

三条无输入验证 + 后续 TTBR0 实验（机器新增 4 个选项，二进制待重新发布）：

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
