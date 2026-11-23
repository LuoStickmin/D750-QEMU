> [English](SUMMARY.en.md) | 中文

# 项目总览：D750 QEMU 验证

本仓库只保留 D750 的 QEMU 验证原型。

## QEMU 验证原型（`nikon-d750`）

依据 WonderLantern 的 z7-qemu / z9-qemu 的组织方式，写了一个 QEMU 11.1
source overlay：

- 主镜像 `b1010_115a.bin` 装入 `0x90000000`，入口 `0x9027D52C`；
- 辅助启动：低 64 KiB RAM、SP=RAM 顶、LR 指向 `0xFF0` 的 halt 窗口；
- 结果：入口执行完正常返回，`exit=0`、0.39 s、`r0=0x80002000`、0 MMIO、0 UART；
- 交叉验证：`entry_pc=0x9027D52C`、`entry_ok=true`、CPSR `0x400001d3`；
- 入口是**被调用函数**，不是 reset；没有它时 `push` 到 `0xFFFFFFF0..FC` 并跳回 0；
- 镜像内 10 个候选入口全部 0 MMIO，`0x9025D700` 进入无 MMIO 等待循环；
  其调用者不在 `b1010` 内，后续布局枚举指向缺失的一级 boot ROM；
- 跨机型（2026-11-10）：E5 D850 的镜像内 init 已定位
  （`0x1035CE30..0x1035D040`），但仍缺 boot ROM 调用上下文；E6 D780 修页表后
  0 异常进入 `0x0426/0x0428` 外设块；
- M-core（2026-11-23）：新增 `nikon-d750-mcore`；a1010 是 BE8 Firmware A，
  从 reset `0xC20D` 跑到 `0x440CE000` 引脚/时钟块，`STIR=0x8F` 后 idle，
  3 s 内 0 异常、0 UART；见 [docs/mcore.md](docs/mcore.md)；
- LCD dump 管线已实现（可配置帧缓冲 → PPM），测试卡验证通过；
  固件 GUI 与 CMOS 仍无模型。

细节：[README.md](README.md)、[docs/findings.md](docs/findings.md)、
[docs/validation.md](docs/validation.md)、[docs/gui-cmos.md](docs/gui-cmos.md)。

## 状态与边界

- 本仓库是**本地研究/静态验证**，不是可刷机产品，也不承诺真机兼容；
- 没有签名、重打包服务、升级容器处理或相机安装包；
- 固件版权属于 Nikon；仓库不包含任何固件内容；
- QEMU overlay / 工具 / 文档：GPL-2.0-or-later；上游 QEMU 保留自身许可。

## 推荐阅读顺序

1. [README.md](README.md) — 机器模型、M0、LCD 管线、boot 结论；
2. [CONTRIBUTING.md](CONTRIBUTING.md) — 法律声明、贡献边界、DCO；
3. [docs/findings.md](docs/findings.md) — 静态证据与运行证据。
