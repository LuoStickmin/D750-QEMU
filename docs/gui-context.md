# GUI 上下文启动：新方向（参考 z30-qemu）

> [English](gui-context.en.md) | 中文

> 日期：2026-11-25 · 状态：**方向调整，尚未实现**。
> 暂不追求自然启动；目标改为“提供上下文 → 调用原厂 GUI/显示函数 → 抓原厂画面”。

## 1. 为什么转向

D750 的 A-core host-assisted 已经能到 `0x10025474` 的 SVC/A300 服务循环，
但再往下需要 T-Kernel 服务、任务调度和跨核握手；这条路离“看到原厂 GUI”
还隔着一整层 RTOS。

z30-qemu 的做法不同：它明确**不做自然启动**，而是在版本相关的任务检查点
调用原厂固件函数，并由宿主提供显式诊断状态；原厂 GPU 命令因此能画出
720×480 菜单。这个模式更适合当前阶段。

参考（外部）：
- <https://github.com/WonderLantern/z30-qemu>
- 本地 README：`C:\Users\23795\Downloads\README.md`

## 2. 目标

在 D750 上复刻 z30 的“辅助 GUI”思路：

1. 找到 D750 原厂 **GUI/显示初始化函数或任务检查点**；
2. 由 QEMU 机器提供它需要的上下文（栈、全局状态、任务/队列、Display/GPU
   MMIO、帧缓冲、诊断返回值）；
3. 直接调用这些函数，让原厂代码自己绘制菜单/LCD；
4. 用现有 PPM dump（后续可接浏览器）证明“原厂像素”出现。

**不**以“自然上电完整 boot”为验收条件；也不把 host fixture 说成 boot ROM。

## 3. 当前证据与缺口

| 项目 | 状态 |
| --- | --- |
| A-core 真实 reset → 下一阶段 | ✅ host-assisted 到 `0x1000E200`/SVC 循环 |
| M-core `a1010` | ✅ BE8 到 idle `0xC04A` |
| GUI/Display/GPU 字符串 | ✅ 镜像里有 `Display/GPU/GDU/TFT/@APPMENU` 等 |
| GUI 函数地址/任务入口 | ❌ 未定位 |
| Display/GPU MMIO 契约 | ❌ 未观测到访问 |
| 帧缓冲地址/格式 | ❌ 未观测；现有 `lcd-base` 是主机配置 |
| 浏览器 GUI | ❌ 只有 host-side PPM dump |

## 4. 拟议架构

### 4.1 机器/模式

新增诊断模式（名称待定，例如 `nikon-d750-gui` 或 `gui-context=on`）：

- 仍然映射 b1010 到 `0x90020000`；
- 不跑自然 reset/SVC 链，由宿主设置初始 PC/SP/寄存器；
- 映射候选 Display/GPU/GDU 窗口为**可观测 stub**，记录地址/宽度/值；
- 复用现有 `lcd-base/width/height/stride/format/out` dump；
- 所有上下文来自版本相关的 checkpoint 表，不硬编码进通用启动路径。

### 4.2 上下文内容

第一批只求“能调用一个函数并返回”：

- 栈：IRAM/DRAM 中一块可写栈；
- 全局状态：函数签名要求的指针/结构体，先用零页/诊断块；
- 任务/队列：如果函数查 T-Kernel 任务表，提供最小静态表或返回固定句柄；
- Display/GPU：至少让初始化写寄存器不崩，再逐步补语义；
- 诊断：未建模访问记录 PC/地址，不返回“看起来合理”的假数据。

### 4.3 Checkpoint 表

按固件版本（`D750_0115`）维护：

```text
checkpoint name | firmware addr | call convention | required context | evidence
```

先手工/静态生成，后续用 plugin/GDB 补齐。

## 5. 工作顺序

1. **静态定位**：对 `@APPMENU`、`Display`、`GPU`、`GDU`、`TFT` 做字符串/
   指针 xref，找 UI 初始化、菜单绘制、GPU 提交函数；参考 z30 的
   `rom_xrefs.py` 思路。
2. **最小调用**：选依赖最少的一个函数（优先纯绘制/初始化），用合成栈和
   零上下文调用，记录异常/MMIO。
3. **补上下文**：按失败点逐步补结构体/任务/Display stub，直到函数返回或
   开始写帧缓冲/GPU 命令。
4. **抓画面**：配置 `lcd-base` 或 GPU 目标缓冲，dump PPM；若出现原厂
   字体/菜单像素，即第一个 GUI 里程碑。
5. **交互/浏览器**：最后再做输入注入和 HTTP GUI，不在第一步范围。

## 6. 验收与边界

- 验收：原厂函数执行、原厂 GPU 命令或帧缓冲像素出现；可重复的 checkpoint。
- 非验收：自然上电 boot、完整 T-Kernel、CMOS/ISP、视频录制。
- 风险：GUI 可能依赖任务调度/IPC/GPU 固件，单函数调用不一定成立；
  如果第一步失败，记录依赖并用 plugin 扩展上下文，而不是继续盲猜 SVC。

## 7. 与现有工作的关系

- 保留 A-core host-assisted/SVC 证据，作为“上下文来源”；
- 不再以 SVC 服务表为当前主线；
- M-core 继续作为独立研究，不阻塞 GUI 方向；
- 现有 `tools/memtrace.c`/GDB 脚本用于找 GUI 函数的访问上下文。
