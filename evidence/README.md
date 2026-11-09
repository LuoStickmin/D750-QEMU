# evidence/

> [English](README.en.md) | 中文

本目录是**实际运行**留下的证据，不是手工编写的说明。

| 目录/文件 | 内容 | 关键结论 |
| --- | --- | --- |
| `m0/` | `command.json`、`session.json`、`qemu.log`、`uart.log` | 非 GDB 的 M0：exit 0、0.39 s、halt 记录 `r0=0x80002000` |
| `m0-gdb/` | 同上，含 RSP 快照 | `entry_pc=0x9027d52c`、`entry_ok=true`、CPSR `0x400001d3`；guest 自行退出后 RSP 断开 |
| `lcd/` | 同上 + `lcd.ppm` | 8×8 ARGB8888 从 `0x92000000` dump；证明扫描/dump 链路 |
| `m1/` | `command.json`、`session.json`、`qemu.log`、`uart.log` + `gdb-entry.json` | M1：桩 → `0x1002CB8C`（Thumb，参数 0/0/2/0/1）；第一条 MMIO `0xe000e180←0x00100000`；随后在 `0x100240AC` 撞 M-profile 指令 |
| `m1/tracks/` | `layout-matrix.md`、`b1010-flash-svc.log`、`ttbr0-run.log`、`veneer-reloc-run.log`、`veneer-scan.txt`、`loader-segments.txt`、`ida-layout.txt`、`ida-layout-run.log`、`cross-model-d3300.txt`、`e6-e5-e4-layout.txt`、`e5-run.log`、`e5-loader-candidates.txt`、`e6-run.log`、`expeed-io-run.log`、`m0-entry-fullflash.log`、`mcore-boot.log`/`.md` | 12 种布局；TTBR0 验证；`veneer-slot` 后 0 undefined、1 SVC、0 abort；loader 段表；Nikon-Patch IDA 布局；D3300 跨机型；E6/E5/E4 版图；E5 入口候选（两个普通函数）；E6 D780 修页表后 0 异常跑到 `0x0426/0x0428` 外设块；`io-stub` 越过 `0xAE00060C` |
| `boot-scan.txt` | 10 个候选入口的扫描输出 | 全部 0 MMIO；`0x9025d700` 2 s 未返回；下一阶段不在 `b1010` 内 |

## 怎么读

- `session.json` 的 `halt` 字段是入口返回时的寄存器快照；`lcd` 字段是最后一次
  dump 的尺寸/格式/路径；`mmio.by_address` 是未建模访问的聚合。
- `qemu.log` 是 `-d guest_errors` 的原始日志；`d750-halt:` / `d750-lcd:` /
  `d750-probe:` / `d750-a1010-io:` 是机器自己写的前缀。后者只统计来自 a1010
  地址范围的未建模访问（`session.json.mmio.first_a1010`）。
- `command.json` / `session.json` 里的路径已替换为 `<repo>`、`<firmware>`、
  `<build>` 占位符（公开仓库的隐私处理）；换机器/换目录后按新路径重跑即可。
- 本目录的 M0/GDB/LCD 证据由 **v0.1.0** 二进制生成。v0.1.1 起 `session.json`
  另记 `status`、`payload_sha256`、`flash_sha256`，`halt` 另记
  `return_ok` / `mode`；旧文件没有这些字段，`run.py` 仍可解析。

## 边界

- `m0*` 只证明“入口执行并返回”，不证明固件启动完成。
- `lcd/` 是空/默认帧缓冲的 dump；测试卡（`analysis/lcd-testcard.png`）是主机
  通过 GDB 写入的，不是固件渲染。
- `m1/gic-unmapped/` 故意把 MPCore 放在旧占位址，以暴露第一条 MMIO 的地址；
  `m1/default/` 是修正基址后的默认运行。两者合起来才说明“地址定位 + 设备接上”。
- `m1` 的 `gdb-entry.json` 是主机侧 RSP 快照，不是固件自报；`0x100240AC` 的
  undefined 已在 `qemu.log` 的 `-d int` 运行中复现（见 `docs/m1-boot-chain.md`）。
- 没有串口输出；M1 也不能称为“启动链闭合”。
