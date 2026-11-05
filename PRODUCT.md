# D750-QEMU 产品快照

仓库根目录就是 `nikon-d750` 验证原型的**可交付产品目录**：源码、工具、文档、
已构建的 Linux 二进制、以及实际运行的证据。

可以整体拷走；拷贝后按新的绝对路径重跑 `tools/run.py` 即可。

## 1. 快照信息

| 项目 | 值 |
| --- | --- |
| 生成时间 | 2026-11-05（Asia/Shanghai） |
| 主机 | Windows + WSL2 Ubuntu 26.04.1 LTS |
| 编译器 | gcc 15.2.0 |
| QEMU | 11.1.0（overlay 构建） |
| 二进制 | `binary/qemu-system-arm`（Linux x86-64，约 96 MiB） |
| 主机侧测试 | 20 passed |

## 2. 已验证的事实

1. **M0 通过**：`b1010_115a.bin` 装入 `0x90000000`，入口 `0x9027D52C`
   执行完并返回 halt 窗口，0.18 s 正常退出。
   `evidence/m0/`、`evidence/m0-gdb/`。
2. **入口检查**：RSP 读到 `entry_pc=0x9027d52c`、`entry_ok=true`、
   `cpsr=0x400001d3`（SVC，A/I/F 屏蔽）。
3. **LCD dump 管线**：可配置帧缓冲 → PPM；用 GDB 往 guest RAM 写 320×240
   测试卡验证像素正确，见 `analysis/lcd-testcard.png`。
   **这是主机写入的测试卡，不是固件 UI。**
4. **boot 候选扫描**：镜像内 10 个候选入口全部 0 MMIO；下一阶段不在
   `b1010` 内（详见 `evidence/boot-scan.txt` 与 `docs/findings.md` §11.4）。

## 3. 目录

```text
D750-QEMU/
├── README.md             产品主说明（状态、快速开始、机器模型）
├── PRODUCT.md            本快照说明
├── NOTICE.md             独立研究/无固件/许可声明
├── MANIFEST.json         文件清单、SHA-256、证据摘要
├── SHA256SUMS            sha256sum -c 兼容的校验清单
├── qemu/                 QEMU overlay：nikon-d750-lab.c/.h + prepare_source.py
├── tools/                fwscan / run / probe / build
├── tests/                20 个主机侧测试（无需 QEMU 构建）
├── docs/                 findings / architecture / validation / build / gui-cmos
├── analysis/
│   ├── d750-0115.json    真实镜像的 profile 核对结果
│   ├── lcd-testcard.png  LCD 管线测试卡（主机写入）
│   └── ...               工作区已有的分析文件（见 §6）
├── binary/
│   ├── qemu-system-arm   已构建的 Linux 二进制（WSL 运行）
│   ├── COPYING           QEMU 的 GPLv2 许可
│   └── README.md         二进制来源、运行方式、校验
└── evidence/
    ├── m0/               非 GDB 的 M0 证据（session/command/logs）
    ├── m0-gdb/           GDB 入口检查 + 运行记录
    ├── lcd/              8×8 LCD dump 证据
    ├── boot-scan.txt     候选入口扫描结果（负结果）
    └── README.md         证据说明
```

## 4. 快速运行（WSL）

```bash
cd /path/to/D750-QEMU
FW=/path/to/D750_0115.dec.modules
python3 tools/run.py \
  --qemu binary/qemu-system-arm \
  --payload "$FW/b1010_115a.bin" \
  --flash   "$FW/a1010_011100.bin"
```

预期输出：

```
entry 0x9027d52c  exit=0  timed_out=False  uart=0B  mmio_events=0
halt: pc=0x00000ff0 r0=0x80002000 r1=0x00000000 sp=0x97ffff00 lr=0x00000ff0
```

LCD dump：

```bash
python3 tools/run.py --qemu binary/qemu-system-arm \
  --payload ... --flash ... \
  --lcd-base 0x92000000 --lcd-width 320 --lcd-height 240
```

`binary/qemu-system-arm` 是 **Linux x86-64**，只能在 WSL/Linux 里跑；
Windows 侧 `C:\Program Files\qemu` 的 stock 11.1.0 没有 `nikon-d750` 机器，
`tools/run.py` 会拒绝它（退出码 3）。重建方法见 `docs/build.md`。

## 5. 二进制来源

- QEMU 11.1.0 源码 + `qemu/` overlay；
- WSL2 Ubuntu 26.04 / gcc 15.2 / glib 2.88 / pixman 0.46.4；
- 构建参数：`--target-list=arm-softmmu --disable-werror --disable-docs --disable-tools`；
- 校验值见 `MANIFEST.json` 的 `binary.sha256`，或 `sha256sum binary/qemu-system-arm`。

## 6. 关于 `analysis/` 里的其他文件

`analysis/d750-0115.json` 与 `analysis/lcd-testcard.png` 由本 QEMU 产品生成。

其余文件（`nikon_patches.c`、`tiff-feasibility.md`、`strings_movie.txt`、
`scan_bitrate_*.py`、`dump_*_table.py` 等）是同一项目里**已有的固件分析产物**，
随产品保留，不是本次 QEMU 工作生成的，也不在本产品的验收范围内。保留它们是
为了不丢失已有工作；如需拆分，把它们移到独立目录即可。

## 7. 未完成 / 下一步

- 固件 GUI：需要观测到 Display/GPU/GDU 的真实寄存器与帧缓冲；当前只有主机侧
  dump 管线。
- CMOS：需要 Sensor/I2C/GDMA 的控制/数据契约；当前没有模型。
- boot 下一阶段：镜像内候选入口已扫描完，全部 0 MMIO；下一步需要 flash/ROM
  dump 或 loader 交接约定。
- 详见 `docs/gui-cmos.md`、`docs/findings.md` §11.4/§11.5。

## 8. 边界

不包含任何 Nikon 固件、密钥、dump 或相机 UI 截图；固件由使用者本地提供，工具
只读。许可：overlay/工具/文档 GPL-2.0-or-later；QEMU 保留其自身许可。
