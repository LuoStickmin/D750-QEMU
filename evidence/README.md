# evidence/

> [English](README.en.md) | 中文

本目录是**实际运行**留下的证据，不是手工编写的说明。

| 目录/文件 | 内容 | 关键结论 |
| --- | --- | --- |
| `m0/` | `command.json`、`session.json`、`qemu.log`、`uart.log` | 非 GDB 的 M0：exit 0、0.18 s、halt 记录 `r0=0x80002000` |
| `m0-gdb/` | 同上，含 RSP 快照 | `entry_pc=0x9027d52c`、`entry_ok=true`、CPSR `0x400001d3`；guest 自行退出后 RSP 断开 |
| `lcd/` | 同上 + `lcd.ppm` | 8×8 ARGB8888 从 `0x92000000` dump；证明扫描/dump 链路 |
| `boot-scan.txt` | 10 个候选入口的扫描输出 | 全部 0 MMIO；`0x9025d700` 2 s 未返回；下一阶段不在 `b1010` 内 |

## 怎么读

- `session.json` 的 `halt` 字段是入口返回时的寄存器快照；`lcd` 字段是最后一次
  dump 的尺寸/格式/路径；`mmio.by_address` 是未建模访问的聚合。
- `qemu.log` 是 `-d guest_errors` 的原始日志；`d750-halt:` / `d750-lcd:` /
  `d750-probe:` 是机器自己写的前缀。
- `command.json` / `session.json` 里的路径已替换为 `<repo>`、`<firmware>`、
  `<build>` 占位符（公开仓库的隐私处理）；换机器/换目录后按新路径重跑即可。

## 边界

- `m0*` 只证明“入口执行并返回”，不证明固件启动完成。
- `lcd/` 是空/默认帧缓冲的 dump；测试卡（`analysis/lcd-testcard.png`）是主机
  通过 GDB 写入的，不是固件渲染。
- 没有串口输出，没有 MMIO 访问；不要把这些证据描述成“GUI/CMOS 已工作”。
