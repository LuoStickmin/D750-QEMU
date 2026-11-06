# GUI 输出与 CMOS 模拟：现状、证据与路线

> [English](gui-cmos.en.md) | 中文

## 1. 结论（2026-11-05）

| 能力 | 当前状态 | 原因 |
| --- | --- | --- |
| GUI / LCD 输出 | 🟡 主机侧扫描输出/dump 已实现；固件画面无 | 入口片段 `mmio_events=0`，从未触达 Display/GPU/GDU |
| CMOS / 图像输入 | ❌ 没有 | 同上；没有观测到 Sensor/I2C/GDMA 的任何访问 |
| 串口日志 | ❌ 还没有 | 串口候选 `0x80005010` 尚未被访问 |
| 启动到驱动初始化 | ❌ 还没有 | M0 只证明“入口函数能执行并返回”；调用者/下一阶段未找到 |

GUI 的“管线”已经能工作：可配置帧缓冲窗口 → halt/定时 PPM dump → PNG。
但它没有解决“固件画什么”，因为固件还没走到 Display/GPU 驱动。见 §3.2。

不是“模型写不出来”，而是**还没有证据决定模型长什么样**。本项目的原则是：
不知道的寄存器不猜、不返回“看起来合理”的值；先把真实访问序列拿到，再实现。
`qemu.log` 里的 catch-all 就是为这一步准备的。

## 2. 镜像里的证据：软件路径确实存在

`b1010_115a.bin` 的文件偏移 `0x12AD3C0..0x12AD510` 是一张**驱动/服务名字符串表**：

```
GDMA | I2C | ADC | CEC | HDMI | KRCOM | CGN | GPIO | SIO | DSP |
STAR | TIMER | NOR | I2S | UART | GDU | GPU |
DriverCreate End | DriverInitialize End | DriverStart End |
FrontEnd | Storage | Kr | Sensor | ImageProcess |
DriverCreate Start | DriverInitialize Start | DriverStart Start |
Display | ApplCreate End | ApplInitialize End | ApplStart End |
NetCService | WmaService
```

另外：

- `AxisSensor` 在 `0x1BD904`、`0x2AA310`（传感器名字/ID 字符串）；
- `CMOS` 在 `0x10D939`（夹在代码/数据里）；
- `EVF` 在 `0x12A8D93`；
- `HDMI` 在 `0x5634`、`0xFA76C8`、`0x126CC6D`、`0x12AD3EA`。

这说明固件里确实有 **Display / GPU / GDU / HDMI** 和 **Sensor / ImageProcess /
GDMA / I2C** 这些驱动/服务，也有分阶段的初始化日志字符串。但：

- 没有找到指向这些名字的绝对指针（多半是 PC 相对引用），所以**没有直接拿到
  驱动表或寄存器基址**；
- 本次执行片段没有访问任何 MMIO，连串口都没有；
- 因此没有帧缓冲地址、像素格式、stride、传感器 ID、DMA 描述符或中断号。

## 3. GUI 输出路线

### G0 — 先到 Display 驱动

前置：找到 `0x9027D52C` 的调用者/下一阶段（见 `docs/validation.md` 的下一步）。
到达后，catch-all 会记录第一批 `0x80xxxxxx` 访问；那才是 Display/GPU/GDU 的候选。

### G1 — 判定渲染路径

两种可能，工作量差一个数量级：

1. **CPU 直接画帧缓冲**：固件往 RAM 里写像素，Display 控制器只负责扫描。
   这种情况下 G2 很快：找到基址/格式/stride，QEMU 侧做扫描输出即可。
2. **GPU 命令流**：CPU 提交命令给 GPU/GDU，由 GPU 合成。Z7 就是这一路，
   `nikon-z7-gpu.h` 实现了一个 SMAPH-F/OpenVG 子集（路径、描边、位图、alpha）。
   D750 若同构，需要按真实命令流做子集，工作量以周计。

判据：看 catch-all 里是“RAM 写 + 一个 scanout 寄存器”还是“成批的命令/描述符
写 + 完成中断”。

### G2 — 扫描输出

在机器里加一个 `d750-lcd` 设备（或复用 RAM 窗口）：

- 可配置 `lcd-base`、`lcd-width`、`lcd-height`、`lcd-stride`、`lcd-format`
  （RGB565/ARGB8888/RGB888）；
- 定时或按需把帧缓冲 dump 成 PPM/PNG，供无头环境检查；
- 若要交互，再走 z7 的路线：QEMU display surface + QMP `screendump` + 浏览器。

验收不是“有图”，而是：**画面里出现固件自己的 UI 元素**（文字、图标、菜单），
并且能解释它们来自哪段帧缓冲/哪条 GPU 命令。

### G2 现状（已实现的部分）

机器属性（`-M nikon-d750,...`）：

| 属性 | 默认 | 说明 |
| --- | --- | --- |
| `lcd-base` | `0`（关闭） | guest 物理帧缓冲基址 |
| `lcd-width` / `lcd-height` | 640 / 480 | 像素尺寸 |
| `lcd-stride` | 0 | 0 = width × bpp |
| `lcd-format` | `argb8888` | 也支持 `rgb888`、`rgb565` |
| `lcd-out` | `lcd.ppm` | PPM 输出路径 |

行为：

- 每次 halt（入口返回）和每 2 秒把窗口 dump 成 P6 PPM；
- 窗口必须完整落在 `0x90000000 + ram_size` 内，否则只记日志不写文件；
- `lcd-base=0` 时零开销、不产生文件。

已用 GDB 往 `0x92000000` 写 320×240 测试卡验证：

```
d750-lcd: dumped 320x240 (argb8888, stride 1280) from 0x92000000 to /tmp/lcd.ppm
```

![test card](../analysis/lcd-testcard.png)

这张图是**主机写入的测试卡**，证明“guest RAM → 扫描 → PPM/PNG”这段是通的；
它**不是**固件 UI。真实固件不写帧缓冲，默认运行得到黑图。

### G3 — 输入与刷新

按钮/拨轮注入、菜单切换、LCD 刷新节流；这些是 z7 的 `interactive.py` 级别工作，
只有在 G1/G2 稳定后再做。

## 4. CMOS 模拟路线

### C0 — 先到 Sensor/I2C 驱动

同样以 M1 为前提。第一批访问可能落在 `0x80xxxxxx` 的 I2C 控制器或 Sensor
控制块；catch-all 会给出地址、宽度、方向。

### C1 — 传感器控制面

需要回答：

- 传感器是接在 I2C 上，还是由独立 MCU 代理？
- 主机读的 ID 寄存器是什么？返回什么值才能让驱动继续？
- 上电时序、复位、时钟、增益/曝光寄存器的最小集合。

CMOS 模型在这一层通常是一个 **寄存器桩 + 合成 ID/状态**，而不是完整传感器。

### C2 — 数据面

需要描述符/中断契约：

- 帧几何、位深（12/14-bit）、Bayer 排列、stride；
- GDMA/GDU 描述符格式、目标缓冲区、完成中断/状态位；
- live view 与静态拍摄是否走不同通路。

拿到这些之前，“往 RAM 里放一张图”不会让固件消费它。

### C3 — 功能 ISP（可选）

Z7 的做法是：合成 RGGB u16 → 按固件的 DMA 描述符写入 → 功能性 ISP（去马赛克、
tone、NV12）→ 写回固件提交的输出缓冲区 → 由 LCD 扫描。Nikon 的真实 ISP 算法
不实现，也不声称实现。

D750 若只需要“有画面”，可以先做 C1+C2 的最小闭环；要做“像照片的画面”，才需要
C3，而且必须明确这是**功能性近似**，不是 Nikon 的算法。

## 5. 与 z7-qemu / z9-qemu 的差距

| 能力 | Z7 | Z9 | D750（当前） |
| --- | --- | --- | --- |
| 启动 | 已知 MAIN 入口 + 辅助调用 | 已知入口 + 外部 peer | 只到 init 函数返回 |
| GUI | GPU 子集 + LCD 扫描 + 浏览器 | GPU + LCD + 浏览器 | 无 |
| CMOS | 合成 RGGB + RAW DMA + ISP | NV12/NV16 + 虚拟 NVMe | 无 |
| 证据 | 107 指令检查/16 QEMU 检查等 | 完整拍摄/录像验收 | M0（入口执行并返回） |

差距的根因不是 QEMU 设备写不出来，而是 **D750 的启动链和寄存器契约还没被观测到**。
Z7/Z9 的地址、IRQ、协议不能按“同是 EXPEED”复用；这一点在它们的
`docs/research-notes.md` 里也明确写了。

## 6. 现在能做什么

按优先级：

1. **找 boot 下一阶段**（推荐，所有 GUI/CMOS 工作的前置）：
   - 在镜像里找描述符表的消费者/ROM 交接约定；
   - 用 `-machine entry=` 逐个验证候选入口；
   - 用 `--strict` 抓第一个未建模访问（`d750-strict:` 日志，`run.py` 退出码 7）。
2. **LCD dump hook（已完成）**：
   - `lcd-base/width/height/stride/format/out` 可配；
   - halt 与每 2 秒 dump PPM；`lcd-base=0` 时关闭；
   - 已用测试卡验证管线；等 G1 拿到真实基址/格式即可直接用。
3. **CMOS 测试帧 fixture**（同样不猜契约）：
   - 从文件加载一张 raw RGGB，预置到 RAM；
   - 等 C2 的描述符确定后，再由 GDMA 模型搬进固件缓冲区；
   - 在契约未知时只作为“数据源”，不假装成传感器。

## 7. 验收标准（避免把“有输出”当“模拟成功”）

- GUI：画面包含固件渲染的 UI 元素；能指出帧缓冲/命令流的来源；不是主机贴图。
- CMOS：固件**消费**了帧（DMA 完成、ISP 输出、live view 更新），而不只是
  “RAM 里有一张图”。
- 两者都要记录：地址、格式、中断、计数器，以及哪些是假设、哪些是观测。

## 8. 参考

- Z7 的 RAW/ISP/LCD 路径：<https://github.com/WonderLantern/z7-qemu>
  （`docs/architecture.md` 的 “RAW and functional ISP”“GPU and LCD”）
- Z9 的 NV12/NV16、虚拟 NVMe、拍摄闭环：<https://github.com/WonderLantern/z9-qemu>
- 本项目当前的 M0 证据：`docs/validation.md`、`docs/findings.md` §11
