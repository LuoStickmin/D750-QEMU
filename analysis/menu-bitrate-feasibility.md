# D750 电影菜单增加第三个码率选项：可行性分析

日期：2026-11-06

对象：Nikon D750，固件 `D750_0115`，主模块 `b1010_115a.bin`

性质：**只读静态分析；本文没有生成或刷入任何固件。**

## 结论

**“在 Movie quality 下真正新增第三项 64 Mbps”目前不能作为一个安全的静态补丁交付。**

原因不是码率表，而是菜单层：

1. 菜单文本是按语言打包的连续 UTF-16 池，没有 NUL 分隔；新增一个标签会让
   它后面所有标签的偏移变化。
2. 已找到多个 u32 偏移表，但它们指向的是**子串/排序索引**（测试中会指到
   字符串中间），不是可以直接扩展的“菜单项数组”。没有找到一个“2 项 →
   3 项”的菜单描述符。
3. `APPMENU`（`0x10CDA0` 附近）是事件/命令分发代码，不是纯数据菜单表；
   新增一项还要有新的枚举值、设置持久化和 UI 布局。
4. QEMU 原型只跑 M0，不模拟 UI；无法验证新项是否显示、是否可选中、重启后
   是否保持。没有真机时生成这种镜像风险过高。

因此本次**没有修改固件**。可交付的最小方案是复用现有的两个 Movie quality
档位（见 §3），它不是“第三项”，但能达到菜单可选的效果。

## 1. 已确认的菜单文本

英文 Movie quality 组：

| 偏移 | 标签 | 长度 |
| --- | --- | --- |
| `0x75765A` | `Movie quality` | 13 字符 / 26 B |
| `0x757674` | `High quality` | 12 字符 / 24 B |
| `0x75768C` | `Normal` | 6 字符 / 12 B |

中文简体组：

| 偏移 | 标签 | 长度 |
| --- | --- | --- |
| `0x8870D8` | `动画品质` | 4 字符 / 8 B |
| `0x8870E0` | `高品质` | 3 字符 / 6 B |
| `0x8870E6` | `标准` | 2 字符 / 4 B |

这些标签在池中首尾相接，没有 NUL。**同长度替换**（例如 `Normal` → `64Mbps`）
不会改变后续标签的偏移，是风险最低的文字修改；插入一个新标签则必须重排
该语言池的偏移表，36 种语言都要处理。

## 2. 为什么没找到可直接扩展的菜单表

尝试过以下定位：

- 直接搜索 `0x756CC8` / `0x90756CC8` / `0x75765A` 等绝对指针：0 命中。
- 搜索 16/32 位相对偏移的连续数组：有大量命中，但把候选表加上基址后，
  多数指向字符串中间，属于子串/排序索引，不是菜单项数组。
- 搜索“Movie quality / High quality / Normal”三连偏移：没有一组合法基址
  同时指向三个标签起点。
- 反汇编 `APPMENU` 附近：看到的是按事件 ID 的 `cmp/branch` 分发，不是
  “项目数 + 项目指针”的静态表。

这说明菜单层至少还有一层**运行时构造/查表**逻辑。没有真机 UI 或更完整的
符号/调用链时，直接改偏移表很可能让菜单错位、空白或崩溃。

### 2.1 进一步搜索（2026-11-06）

继续按“候选偏移表 + 基址”验证，找到几组**前两项正好落在 High quality /
Normal** 的 u32 表：

| 表偏移 | 试算基址 | 现象 |
| --- | --- | --- |
| `0xB2BA74` | `0x72F400` | 前两项指向 `0x757674/0x75768C`，第三项开始落入字符串中间 |
| `0xC295B0` | `0x72E400` | 前两项命中，后续项落入 `NowChoose...` 中间 |
| `0xC55F1C` | `0x74C800` | 前两项命中，后续项落入 `sensitivity...` 中间 |

这些表更像**排序/子串索引**：只有相邻两项恰好与标签边界重合，继续读就会
指到词中间，不能当作“菜单项数组”扩展。`0x1CEA1C` 等较大的 u32 表也一样，
映射到的是 `0x75739E`、`0x7571AA` 等串中间位置，不是标签起点。

结论不变：**没有找到可安全扩展的 Movie quality 菜单描述符**。下一步需要
动态证据（见 §4）而不是继续猜表。

## 3. 可交付的最小菜单方案（复用两项）

把现有 Movie quality 两项改成“64 Mbps / Stock”：

| 菜单项 | 码率表 | 行为 |
| --- | --- | --- |
| `64 Mbps HQ`（中文 `64M`） | 1080p HQ 行 1/3/5/7/9 | `64/60` Mbps |
| `Stock`（中文 `原厂`） | 1080p NQ 行 2/4/6/8 | stock HQ：`42/35`、`42/35`、`24/20`、`24/20` |

同长度标签：

- 英文：`High quality`（12）→ `64 Mbps HQ  `（12，末尾两个空格）；
  `Normal`（6）→ `Stock `（6，末尾一个空格）。
- 中文：`高品质`（3）→ `64M`（3）；`标准`（2）→ `原厂`（2）。

这只改：
- 2 个英文标签、2 个中文标签（同长度）；
- 5 个 HQ 行、4 个 NQ 行（表内 u32）；
- 容器 CRC/加密由重打包工具处理。

它**不是**第三项：原来的 Normal 低码率档被占用。优点是菜单确实能在
“64 Mbps”和“Stock”之间切换，且不需要动菜单描述符。

> 该最小方案已在本地实现并做过静态/容器验证，产物在
> `D750_0115.menu64.out/`（不随本仓库发布）；报告见该目录的 `REPORT.md`。

## 4. 如果坚持真正第三项

需要按顺序完成：

1. 定位 Movie quality 的菜单描述符：项目数、项目文本 ID/偏移、设置枚举。
2. 确认设置持久化位置（NVRAM/配置文件）以及 UI 是否按枚举值索引。
3. 在英文/中文（以及其余 34 种语言）池中追加标签，重排该语言所有偏移。
4. 给码率选择逻辑增加第三个分支，映射到一组新的 1080p 表行。
5. 在真机上验证：菜单显示、切换、重启保持、录制文件码率、回放、恢复默认。
6. 没有真机时，至少需要 QEMU 能跑到 UI 层并 dump 菜单；当前原型做不到。

第 1 步是当前卡点；在找到菜单描述符之前，不应生成“第三项”镜像。

### 4.1 下一步需要的动态证据

静态表搜索已经到边界，继续下去需要以下任一条件：

1. **真机/调试器**：在相机打开 Movie quality 菜单时，对 `0x75765A` 附近的
   读取下断点，记录调用者、读取宽度和后续索引；由此反推“项目数/项目数组”
   的真实位置。
2. **能跑到 UI 层的模拟器**：当前 `nikon-d750` 只到 M0，没有 UI/显示服务；
   需要先补齐 boot 下一阶段和显示/输入设备，才能在 QEMU 里复现菜单。
3. **同代机型对照**：D810/D850 的菜单项更多，若能定位它们同类菜单的
   描述符，可用差分推断 D750 的格式；目前没有完成这一步。

在这三条之前，改任何候选表都只是猜测，不应生成刷机镜像。

## 5. 复现

标签位置可用任意 UTF-16 扫描器复核：在 `b1010_115a.bin` 中搜索
`Movie quality`、`High quality`、`Normal`，应分别落在 `0x75765A`、
`0x757674`、`0x75768C`；搜索 `动画品质`、`高品质`、`标准`，应落在
`0x8870D8`、`0x8870E0`、`0x8870E6`。一次性探索脚本保留在本地
`.local/private-analysis/`，不随仓库公开。

## 6. 边界

- 本文是静态分析结论，不是对相机 UI 的实测。
- “没找到菜单描述符”是当前搜索范围内的负结果，不等于固件里不存在；但
  足以否定“改一个字节就能多一项”的说法。
- 没有生成、重打包或刷入任何固件。

---

# English version

## Adding a Third Bit-rate Item to the D750 Movie Menu: Feasibility

Date: 2026-11-06

Target: Nikon D750, firmware `D750_0115`, main module `b1010_115a.bin`

Scope: **read-only static analysis; no firmware was generated or flashed.**

### Conclusion

**Adding a genuine third "64 Mbps" item under Movie quality is not a safe
static patch with the current evidence.** The blocker is the menu layer, not
the bit-rate table:

1. Menu text is a packed UTF-16 pool per language with no NUL separators.
   Inserting a label shifts every following label in that language.
2. Several u32 offset tables exist, but they resolve to substrings/sorted
   indexes (they point into the middle of strings in tests), not to an
   editable "menu item array". No two-to-three-item menu descriptor was found.
3. `APPMENU` near `0x10CDA0` is an event/command dispatcher, not a pure data
   menu table. A new item also needs a new enum value, settings persistence,
   and UI layout.
4. The QEMU prototype stops at M0 and does not model the UI, so it cannot
   verify that a new item displays, is selectable, or survives a reboot.

This analysis therefore did not modify firmware. The smallest deliverable is
to reuse the existing two Movie quality slots (see §3); it is not a third item,
but it gives a menu-selectable choice.

### 1. Confirmed menu labels

English Movie quality group:

| Offset | Label | Length |
| --- | --- | --- |
| `0x75765A` | `Movie quality` | 13 chars / 26 B |
| `0x757674` | `High quality` | 12 chars / 24 B |
| `0x75768C` | `Normal` | 6 chars / 12 B |

Simplified Chinese group:

| Offset | Label | Length |
| --- | --- | --- |
| `0x8870D8` | `动画品质` | 4 chars / 8 B |
| `0x8870E0` | `高品质` | 3 chars / 6 B |
| `0x8870E6` | `标准` | 2 chars / 4 B |

The labels are adjacent with no NUL. A **same-length** replacement (for
example `Normal` -> `64Mbps`) does not move later labels and is the lowest-risk
text edit. Inserting a new label requires re-laying out that language's offset
table, for all 36 languages.

### 2. Why no directly extendable menu table was found

Attempts:

- searching absolute pointers `0x756CC8` / `0x90756CC8` / `0x75765A`: zero hits;
- searching contiguous 16/32-bit relative-offset arrays: many hits, but most
  candidate tables resolve into the middle of strings when a base is applied;
  they are substring/sorted indexes, not menu item arrays;
- searching for the exact triplet "Movie quality / High quality / Normal":
  no candidate table with a valid base points at all three label starts;
- disassembling around `APPMENU`: it is a `cmp/branch` dispatcher over event
  IDs, not a static "count + item pointers" menu table.

The menu layer therefore has at least one runtime construction/lookup step.
Without a UI-capable emulator or a real camera, editing candidate tables risks
a shifted, blank, or crashing menu.

#### 2.1 Further search (2026-11-06)

Several u32 tables have their first two entries exactly at `High quality` /
`Normal` for a trial base:

| Table offset | Trial base | Observation |
| --- | --- | --- |
| `0xB2BA74` | `0x72F400` | first two point at `0x757674/0x75768C`; third falls inside a string |
| `0xC295B0` | `0x72E400` | first two hit; later entries fall inside `NowChoose...` |
| `0xC55F1C` | `0x74C800` | first two hit; later entries fall inside `sensitivity...` |

These look like **sorted/substring indexes**: only the adjacent pair happens to
coincide with label boundaries, and the next entry points into the middle of a
word. They cannot be extended as a menu item array. Larger u32 tables such as
`0x1CEA1C` behave the same way, pointing at `0x75739E`, `0x7571AA`, etc.

The conclusion is unchanged: **no safely extendable Movie quality menu
descriptor was found**. The next step needs dynamic evidence (see §4).

### 3. Smallest feasible menu variant (reuse two slots)

Turn the existing two Movie quality slots into:

| Menu item | Bit-rate rows | Behaviour |
| --- | --- | --- |
| `64 Mbps HQ` (Chinese `64M`) | 1080p HQ rows 1/3/5/7/9 | `64/60` Mbps |
| `Stock` (Chinese `原厂`) | 1080p NQ rows 2/4/6/8 | stock HQ: `42/35`, `42/35`, `24/20`, `24/20` |

Same-length labels:

- English: `High quality` (12) -> `64 Mbps HQ  ` (12, two trailing spaces);
  `Normal` (6) -> `Stock ` (6, one trailing space).
- Chinese: `高品质` (3) -> `64M` (3); `标准` (2) -> `原厂` (2).

This changes only two English labels, two Chinese labels, five HQ rows, four
NQ rows, and the container CRC/encryption (handled by the repack tool). It is
**not** a third item: the old Normal low-bit-rate slot is consumed. Its
advantage is a real menu-selectable "64 Mbps / Stock" choice with no menu
descriptor changes.

> This smallest variant was implemented locally and statically/container
> verified; artifacts are in `D750_0115.menu64.out/` (not published in this
> repository); see its `REPORT.md`.

### 4. A genuine third item would require

1. Locating the Movie quality menu descriptor: item count, text IDs/offsets,
   and the settings enum.
2. Confirming settings persistence (NVRAM/config) and whether the UI indexes
   by enum value.
3. Appending labels to English, Chinese, and the other 34 language pools and
   re-laying out all their offsets.
4. Adding a third branch in the bit-rate selection logic, mapped to a new set
   of 1080p rows.
5. Real-hardware validation: menu display, selection, reboot persistence,
   recorded bit rate, playback, and factory reset.
6. Without hardware, at least a QEMU run that reaches the UI and dumps the
   menu; the current prototype cannot do that.

Step 1 is the current blocker. Do not generate a "third item" image before the
descriptor is found.

#### 4.1 Dynamic evidence needed

Static table search has reached its limit. The next step requires one of:

1. **Real camera/debugger**: break on reads near `0x75765A` while the Movie
   quality menu is open; log the caller, access width, and following index to
   recover the real item count/array.
2. **A UI-capable emulator**: the current `nikon-d750` machine stops at M0 and
   has no UI/display/input services; boot-next-stage work would be required.
3. **Same-generation comparison**: D810/D850 have more menu items; locating
   their equivalent descriptor could reveal the format. Not done yet.

Until one of these exists, editing a candidate table is guesswork and must not
produce a flashable image.

### 5. Boundaries

- Static conclusions, not a camera UI test.
- "Menu descriptor not found" is a negative result within the current search
  scope, not a proof that none exists; it is enough to reject a one-byte patch.
- No firmware was generated, repacked, or flashed.
