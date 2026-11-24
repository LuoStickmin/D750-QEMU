# A-core 启动链：从正确 reset 到 T-Kernel 服务循环

> [English](acore-boot.en.md) | 中文

> 日期：2026-11-24 · 机器：`nikon-d750` · 状态：**host-assisted A-core
> 启动链已跑通到下一阶段镜像/T-Kernel 服务循环；仍没有 console/GUI，
> 也没有完成整机 boot。**

本文记录 2026-11-24 的 A-core 推进。所有结论来自真实 b1010 字节与 QEMU
运行；`tools/acore_boot.py` 是**诊断夹具**，不是 boot ROM 还原。

## 1. 先修正布局

此前 M0/M1 把 b1010 装在 `0x90000000`。Nikon-Patch 的 D750 IDA 脚本给出
的真实布局是：

- ROM 基址 **`0x90020000`**；
- 文件 0 是 ARM 向量表，reset = **`0x9027D524`**；
- 旧的“`0x9025D700` 启动桩”其实是 `0x9027D700` 的代码。

`tools/run.py --payload-base 0x90020000 --entry 0x9027D524` 后，A-core
执行的是**真实 reset 路径**，而不是错位后的片段。

## 2. 这次补上的夹具

| 夹具 | 作用 | 性质 |
| --- | --- | --- |
| `aux2-base=0xB8000000` / `aux2-size=0x40000` | 提供 A-core 的 IRAM：栈在 `0xB801FFxx`，页表在 `0xB801FC00` | 运行必需；不是猜测的 RAM 基址 |
| `io-stub=on`：A2/A120/A161/A300/AD/AE/A340 | 让启动路径的 ready 轮询通过 | 诊断寄存器堆，不是硬件模型 |
| `--vector-fix`（可选；SVC 改为 `movs pc,lr`） | SVC 返回时保留 SPSR 的 ARM/Thumb 位 | 诊断旁路；默认关闭，走真实 SVC handler |
| 清零 `0x100A6704` | 越过下一阶段镜像里的共享 boot flag（原值 2） | 主机侧 GDB 写入，不改固件文件 |

> `0x400F2000/0x400F3000` 是 M-core 的；A-core 这次用的是
> `0x400F` 之外的 A2/A120/A161/A300/AE/A340 块，两者不要混用。

## 3. 实测链

```text
0x9027D524  reset
0x9027D944  MMU/cache 设置（SCTLR/TTBR/DACR）
0x9027D5A4  blx 0x90020098
0x90020098  构造页表（写入 0xB801FC00..，栈 0xB801FFE0）
0x1000E200  下一阶段镜像（已复制到 flash 窗口）
0x1000E24C  等待 [0x100A6704] == 0
0x1002AFE0  svc #5（T-Kernel 服务）
0x10025474  A300 状态轮询 / 服务循环
```

3–4 s 时的现场：

```text
PC=0x10025474  LR=0x10012938  SP=0x10600BD8
CPSR=0x20000093（ARM，SVC）
UART=0 B
```

`session.json` 还记录了清零前后的 flag（`0x02` → `0x00`）和 32 字节现场。
运行会停在一个**稳定的服务/轮询循环**，不是崩溃。

## 4. 这算走到哪一步

已经证实的：

- 真实 reset 路径能跑完，MMU 页表在 `0xB8000000` IRAM 上构造成功；
- 代码会跳到复制到 `0x1000xxxx` 的下一阶段镜像；
- 该镜像会调用 `svc #5`，并在 A300 状态上循环；
- 全程 0 未处理异常（`-d int,guest_errors`）。

**没有证实的**：

- 这不是完整的 A-core boot：没有 T-Kernel 服务实现、任务调度、console、
  文件系统或 GUI；
- SVC 默认走真实 handler；`--vector-fix` 只是诊断旁路，真实服务语义未知；
- `0x100A6704` 的写者已抓到：`0x1000E240` 写 2；镜像内没有清零者，
  清零来自主机夹具（见 §5）；
- A300/A161/A120 的 ready 位是诊断值，不是硬件语义。

## 5. Plugin 抓取（2026-11-24 22:00）

`tools/memtrace.c` 是过滤式 TCG plugin，覆盖 flag/页表/下一阶段镜像/向量/
栈/UART 候选。编译：

```sh
gcc -shared -fPIC -O2 $(pkg-config --cflags glib-2.0) \
  -I$QEMU/include/plugins -o tools/memtrace.so tools/memtrace.c
python3 tools/acore_boot.py ... --plugin tools/memtrace.so
```

canonical 运行（真实 SVC handler，6000 条事件）抓到 `0x100A6704`：

> 本次运行用的 `b1010` 由本地 `nov7/b1010_mmuoff.bin` 与
> `nov7/b1010_reloc1.bin` 互补恢复（两者只差 2 字节，SHA-256 回到
> `faada7fe…f82937fd`）；原始模块目录已不在，运行本身不修改固件。

```text
0x9027D854  w  0x100A6704 = 0   ; BSS/数据清零
0x1000E240  w  0x100A6704 = 2   ; A-core 门铃
0x1000E24C  r  0x100A6704 = 0   ; 主机清零后通过
```

镜像内没有第三个写者，说明这个 flag 是**跨核握手**：A-core 写 2 后等待
M-core/boot ROM 清零。plugin 没有看到 `0x80005010`/`0x440C4xxx` 的访问，
UART 仍为 0；栈上的 `0x1C200` 不能单独当作波特率证据。

另外发现一个 fixture bug：`vector-fix` 原来固定写 `payload+0x20000`，在
`payload-base=0x90020000` 时实际改的是 `0x90040000`，所以 SVC 仍走原向量
（plugin 看到 509 次 `pc=0x90020008` 读 `0x90020028`）。改为写
`payload+0` 后：`--vector-fix` 运行 4549 条事件、SVC 向量读消失，但最终
停在 `0x10000874` 的 `b .`；默认（不启用 vector-fix）仍到
`0x10025474` 的真实 handler 服务循环。

## 6. 复现

```sh
python3 tools/acore_boot.py \
  --qemu ~/d750-build/src/qemu-11.1.0/build/qemu-system-arm \
  --payload "$FW/b1010_115a.bin" \
  --out runs/acore-boot --seconds 5
```

脚本会：在 `0x1000E24C` 下硬件断点 → 清零 `0x100A6704` → 继续 →
保存 `session.json`/`qemu.log`/`uart.log`。原始证据在
[`evidence/acore/`](../evidence/acore/)（`memtrace*.qemu.log`、
`memtrace-summary.json`）。

## 7. 下一步

1. 把真实 SVC handler (`0x90291D30`) 的服务表/返回约定补出来，而不是只靠
   `--vector-fix`；
2. 用 plugin 继续追 `0x100A6704` 的**跨核清零者**（M-core 侧或 boot ROM）；
3. 建模 A300/A161 状态位，观察是否能进入真正的任务循环；
4. 仍然需要 boot ROM/flash dump 才能补上 A-core 的完整启动上下文。

**一句话：A-core 已经从 reset 跑到下一阶段镜像的 SVC/服务循环；离
“整机 boot”还差 T-Kernel 服务和缺失的 boot ROM 上下文。**
