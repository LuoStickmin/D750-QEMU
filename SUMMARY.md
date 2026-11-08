> [English](SUMMARY.en.md) | 中文

# 项目总览：D750 QEMU 验证 + 1080p 高码率修改

本仓库有两条相互独立、但共享同一份 D750 固件研究的工作线：

| 工作线 | 内容 | 状态 |
| --- | --- | --- |
| **A. QEMU 验证原型** | `nikon-d750` 机器、M0 启动、LCD dump、boot 扫描 | M0 已通过；M1 到目标但未闭合（a1010 是 M-profile）；M2–M3 未开始 |
| **B. 1080p 高码率修改** | 把 5 个 HQ 表项从 42/35、24/20 提到 64/60 Mbps | 容器级验证通过且可逐字节复现；相机实拍未验证 |

两条线都**不包含固件、密钥、解密镜像或改后镜像**；固件由使用者本地提供，
工具只读输入。法律与贡献边界见 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## A. QEMU 验证原型（`nikon-d750`）

依据 WonderLantern 的 z7-qemu / z9-qemu 的组织方式，写了一个 QEMU 11.1
source overlay：

- 主镜像 `b1010_115a.bin` 装入 `0x90000000`，入口 `0x9027D52C`；
- 辅助启动：低 64 KiB RAM、SP=RAM 顶、LR 指向 `0xFF0` 的 halt 窗口；
- 结果：入口执行完正常返回，`exit=0`、0.39 s、`r0=0x80002000`、0 MMIO、0 UART；
- 交叉验证：`entry_pc=0x9027D52C`、`entry_ok=true`、CPSR `0x400001d3`；
- 入口是**被调用函数**，不是 reset；没有它时 `push` 到 `0xFFFFFFF0..FC` 并跳回 0；
- 镜像内 10 个候选入口全部 0 MMIO，`0x9025D700` 进入无 MMIO 等待循环；
  下一阶段不在 `b1010` 内，可能需要 flash/ROM dump 或 loader 交接约定；
- LCD dump 管线已实现（可配置帧缓冲 → PPM），测试卡验证通过；
  固件 GUI 与 CMOS 仍无模型。

细节：[README.md](README.md)、[docs/findings.md](docs/findings.md)、
[docs/validation.md](docs/validation.md)、[docs/gui-cmos.md](docs/gui-cmos.md)。

## B. 1080p 高码率修改（64/60 Mbps）

目标固件 `D750_0115`，模块 `b1010_115a.bin`，1080p 码率表从
`0x2AA9AC` 开始、28 字节/项：

| 行 | 偏移 | stock | 修改后 |
| --- | --- | --- | --- |
| entry 1 | `0x2AA9AC` | 42/35 Mbps | 64/60 Mbps |
| entry 3 | `0x2AA9E4` | 42/35 Mbps | 64/60 Mbps |
| entry 5 | `0x2AAA1C` | 24/20 Mbps | 64/60 Mbps |
| entry 7 | `0x2AAA54` | 24/20 Mbps | 64/60 Mbps |
| entry 9 | `0x2AAA8C` | 24/20 Mbps | 64/60 Mbps |

- 4 个 NQ 行、entry 10 起的低分辨率组、另外两个模块完全未改；
- 模块 CRC `0x12CA → 0x4314`；包 CRC 仍为 `0x7EE4`（CRC residue，正常）；
- 改后解密镜像与 stock 只差 36 B（34 B 字段 + 2 B CRC），字段外 0 B；
- 独立验证器（不导入修改器）重解密、重算两级 CRC、逐项核对，全部通过；
- 容器可逐字节复现：无修改重打包 stock 与输入 bit-identical；stock + 改表模块
  重打包得到 `9c88f3cc…`，与发布的改后镜像完全一致；容器仅 36 B 差异；
- D750 是包装 A（无 20B 摘要头），K8/`STALE` 不适用；
- 同一 QEMU M0 路径跑 stock 与改后模块，结果一致（exit 0、同 halt、0 MMIO）；
- **未验证**：更新器接受度（含同版本重刷策略）、相机编码器、SD 写卡、回放；
  64 Mbps 对 1080p30 是 stock 的约 2.7 倍，慢卡/发热/编码器上限都可能出问题；
- 仓库只提供改表工具与测试，不提供改后镜像、密钥或解密器；
- 菜单可见替代：复用 Movie quality 两项为 `64 Mbps HQ` / `Stock`；
  真正第三项目前卡在菜单描述符，见
  [analysis/menu-bitrate-feasibility.md](analysis/menu-bitrate-feasibility.md)；
  工具与验证见 [bitrate/MENU64.md](bitrate/MENU64.md)。

细节：[bitrate/README.md](bitrate/README.md)；实机前置条件：
[docs/hardware-test.md](docs/hardware-test.md)。

## 状态与边界

- 两条线都是**本地研究/静态验证**，不是可刷机产品，也不承诺真机兼容；
- 没有签名、重打包服务、升级容器处理或相机安装包；
- 固件版权属于 Nikon；仓库不包含任何固件内容；
- QEMU overlay / 工具 / 文档：GPL-2.0-or-later；上游 QEMU 保留自身许可。

## 推荐阅读顺序

1. [README.md](README.md) — 机器模型、M0、LCD 管线、boot 结论；
2. [bitrate/README.md](bitrate/README.md) — 64/60 修改与验证；
3. [CONTRIBUTING.md](CONTRIBUTING.md) — 法律声明、贡献边界、DCO；
4. [docs/findings.md](docs/findings.md) — 静态证据与运行证据。
