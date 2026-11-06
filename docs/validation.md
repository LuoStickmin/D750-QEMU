# 验证计划：从“能加载”到“能解释”

> [English](validation.en.md) | 中文

## 0. 证据分层

沿用 z7-qemu 的纪律：把下面四件事分开记录，任何一件都不能替代另一件。

| 层 | 本原型的证据 | 不代表 |
| --- | --- | --- |
| 容器/静态 | `fwscan` 的 checks、sha256、向量/字面量 | 代码能执行 |
| 装入 | QEMU 未报 `cannot load payload`，RAM 中有字节 | 入口正确 |
| 执行 | PC 到达检查点、串口有字节、MMIO 序列 | 硬件行为正确 |
| 物理 | 无 | 刷机/真机兼容 |

## 1. 里程碑

### M0 — 装入与入口

命令：

```powershell
python tools/run.py --payload ...\b1010_115a.bin --flash ...\a1010_011100.bin --gdb --run-seconds 2
```

通过条件（全部满足）：

1. `session.json.snapshot.entry_pc == "0x9027d52c"`，`entry_ok == true`；
2. `snapshot.cpsr` 的模式位是 SVC（低 5 位 `0x13`），A/I/F 已屏蔽；
3. QEMU 没有在装入阶段退出；
4. `qemu.log` 里没有立刻出现“PC 在 `0x1041D9A8` 附近取指”的记录
   （若出现，说明 entry 假设错了，见 M0-neg）。

失败处理：

- 若 `entry_ok=false`：先看 `run.py` 打印的 `pc`，确认 `-machine entry=` 是否被
  解析；再检查 `-kernel` 是否真的指向 `b1010`。
- 若入口跑飞：用 `--strict` 重跑。第一条未建模访问会以 `d750-strict:` 记录
  （地址、宽度、方向、PC），`run.py` 以退出码 7 结束；这通常就是 M1 的第一个
  设备地址。
- 若 `halt.return_ok=false`（退出码 6）：guest 是从异常路径滑到 `0xFF0` 的，
  不能记为 M0 通过。

**实测结果（2026-11-05，已通过）**：

```
session runs/20261105-075610/
exit=0  timed_out=False  wall_seconds=0.393  uart=0B  mmio_events=0
qemu.log: d750-halt: pc=0x00000ff0 r0=0x80002000 r1=0x00000000
          sp=0x97ffff00 lr=0x00000ff0 firmware returned to the assisted trampoline
```

`wall_seconds` 含 QEMU 进程启动，随冷/热启动在 0.18–0.40 s 之间波动；上面的
数字取自 `evidence/m0/session.json`。

结论：入口能装入并执行完，经 halt 窗口正常退出；但它是**被调用函数**，不是
reset。无辅助时第一次运行会 `push` 到 `0xFFFFFFF0..0xFFFFFFFC` 并跳回 0，
这条负结果保存在 `docs/findings.md` §11。

`--gdb` 模式另有一次记录（`runs/20261105-075746/`）：

```
snapshot.entry_pc = 0x9027d52c
snapshot.entry_ok = true
snapshot.cpsr     = 0x400001d3   (SVC, A/I/F masked, Z set)
stop.kind         = connection-closed   (guest 自行退出，RSP 断开)
```

### M0-neg — 负对照

用 `-machine entry=0x90000000`（真 reset）跑一次，记录它在哪里停/崩。
这条对照用于证明“`0x9027D52C` 比向量字面量更像入口”，而不是把异常当成功。

### M1 — 第一段 MMIO 序列

命令：

```powershell
python tools/run.py --payload ... --flash ... --timeout 10
```

看 `session.json.mmio.by_address`：

- 前 10 个地址按次数排序，记录 `addr / rw / count / first_pc`；
- 与 `docs/findings.md` §6 的串口候选对照：`0x80005010..14` 是否出现；
- 与 `0x1E000000`（MPCore）对照：是否出现；若出现的是别的地址，记下来，
  下一轮把 `D750_MPCORE_BASE` 改过去。

通过条件：至少得到一个**可复现**的地址序列，并且两次运行的序列一致
（TCG 单线程、无外部输入时应当一致）。

**当前结果**：`mmio_events=0`。入口这一段只做 RAM 内的初始化（写 `0x0`
的向量槽、写栈），没有触达外设。所以 M1 的前置工作不是加设备，而是先找到
调用者/下一阶段；否则 catch-all 没有东西可记录。

### M2 — 串口输出

通过条件：`session.json.uart.bytes > 0`，且 `uart.tail` 是可读文本或稳定的
二进制前缀。

**当前结果**：`uart.bytes=0`，尚未到达串口路径；这与 M1 的“入口未触达外设”
一致，不是串口模型失败。

若 `uart.bytes == 0` 但 `qemu.log` 中有大量 `d750-uart: rd +0x11`：

- 说明地址对了、状态位不对。把读序列的返回值记下来（当前是 `0x03`），
  在 `nikon-d750-lab.c` 的 `d750_uart_read()` 里改状态值，或在
  `d750_uart_write()` 里加“写数据后置 TX-done”的状态机；
- 不要为了“让它输出”而把状态改成 `0xFF` 并宣布通过——那只是把轮询骗过去。

### M3 — 补第一个设备

流程固定：

1. `--strict` 跑：`qemu.log` 出现 `d750-strict:` 行（地址、宽度、方向、PC），
   `session.json.strict` 记录同样内容，`run.py` 退出码 7；
2. 在 `nikon-d750-lab.c` 里加最小 MemoryRegionOps，只实现**观察到的**访问；
3. 加一个拒绝用例（错误宽度/错误方向应记录并返回 0，而不是静默通过）；
4. 重跑 M0–M2，确认没有回退；
5. 把新地址/语义写进 `docs/findings.md`，并更新 `fwscan.PROFILE`（如适用）。

### L1 — LCD dump 管线自检（不依赖固件 UI）

```powershell
python tools/run.py --payload ... --flash ... `
  --lcd-base 0x92000000 --lcd-width 320 --lcd-height 240
```

通过条件：

- `runs/<ts>/lcd.ppm` 存在，P6 头与尺寸正确；
- 用 GDB 往该窗口写测试卡时，PNG 像素与写入值一致；
- 默认（固件不写帧缓冲）得到全黑图；
- 窗口越界时只记 `d750-lcd:` 日志、不写文件。

**实测（2026-11-05）**：320×240 ARGB8888，GDB 写入 8 色条 + 灰阶，
PPM/PNG 像素正确，产物 `analysis/lcd-testcard.png`。这只证明“guest RAM →
扫描/dump”链路，不证明固件 GUI；`docs/gui-cmos.md` §3.2 有同样声明。

### 运行退出码（`tools/run.py`）

| 退出码 | 含义 |
| --- | --- |
| 0 | 运行结束，未触发 strict / suspicious |
| 2 | 找不到 `qemu-system-arm` |
| 3 | 该 QEMU 没有 `nikon-d750` 机器（stock 构建） |
| 4 | `--gdb` 时 GDB stub 未打开 |
| 6 | halt 从异常状态到达（`return_ok=false`） |
| 7 | `--strict` 在第一条未建模访问处停止 |

## 2. 判定规则

- 没有 `session.json` 的运行不算证据；
- 没有记录命令行、payload/flash 的 SHA-256 的运行不算证据（`run.py` 自 v0.1.1
  起写入 `payload_sha256` / `flash_sha256`）；
- `session.json.halt.return_ok` 必须为 `true`；`false`（退出码 6）表示 guest 从
  异常路径到达 halt，不能记为 M0 通过；
- `session.json.status` 是机器可读结论：`halt` / `strict-stop` /
  `halt-suspicious` / `timeout` / `ran`；
- 串口里出现字符串不等于“启动完成”，只等于“这条输出路径通了”；
- PC 到达某个地址不等于“函数执行正确”，要同时看它前后是否触发了预期 MMIO；
- `-smp 2` 的结果不能外推到单核，反之亦然。

## 3. 常见失败与定位

| 现象 | 可能原因 | 下一步 |
| --- | --- | --- |
| `machine 'nikon-d750' not found` | 用的是 stock QEMU | 先构建 overlay |
| `cannot load payload` | 路径/大小超过 RAM | 检查路径与 `-m` |
| 一启动就 `Bad address` | 入口/RAM 窗口不对 | `--strict` + `entry=0x90000000` 对照 |
| PC 在 `0x0` 或 `0xFFFF0000` 循环 | PC 被复位覆盖 | 确认 `-S` 只用于 GDB；不要 `system_reset` |
| 串口 0 字节、轮询地址固定 | 状态位假设错 | 看 `rd +0x11` 的返回值，改状态机 |
| MMIO 日志刷屏 | 固件在等某个位 | 用 `mmio.by_address` 找最高频地址 |
| GDB 连不上 | 端口/防火墙/`-S` | `run.py` 已用 127.0.0.1 随机端口；看 `qemu.log` |

## 4. 证据存放

```
runs/20261105-123456/
├── command.json    精确 argv、entry、是否 GDB
├── uart.log         guest 串口原始字节
├── qemu.log         -d guest_errors 的诊断（含 d750-probe/d750-strict/d750-uart）
└── session.json     汇总：status、payload/flash SHA-256、exit、uart、mmio、halt、snapshot
```

这些文件可能包含固件行为/路径，**不要**直接公开；发布前按 z7-qemu 的
publication 流程单独审查。

## 5. 什么算“完成”

本原型的完成定义是：**M0 通过，M1 得到稳定序列，M2 至少有一次可解释的输出
或明确的“状态位假设错误”结论，M3 至少补上一个设备且不回退**。
不包含 UI、拍摄、图像通路；那些是后续 profile 的工作，不应写进本原型的
README 声称。
