# D750 菜单可见码率切换：64 Mbps HQ / Stock

> 这是 `bitrate/d750_menu_patch.py` 的说明与验证摘要。它**不是**新增第三项；
> 真正新增第三项目前卡在菜单描述符，见
> [../analysis/menu-bitrate-feasibility.md](../analysis/menu-bitrate-feasibility.md)。

## 1. 设计

复用 Movie quality 现有两项，同长度就地替换标签：

| 菜单项 | 原标签 | 新标签 | 1080p 行为 |
| --- | --- | --- | --- |
| 第 1 项 | `High quality` / `高品质` | `64 Mbps HQ  ` / `64M` | HQ 行 1/3/5/7/9 = `64/60` Mbps |
| 第 2 项 | `Normal` / `标准` | `Stock ` / `原厂` | NQ 行 2/4/6/8 = stock HQ（`42/35` 或 `24/20`） |

标签长度必须保持不变：

- 英文 `High quality` 12 字符 → `64 Mbps HQ  ` 12 字符（末尾两个空格）
- 英文 `Normal` 6 字符 → `Stock ` 6 字符（末尾一个空格）
- 中文 `高品质` 3 字符 → `64M` 3 字符
- 中文 `标准` 2 字符 → `原厂` 2 字符

码率表（文件偏移 `0x2AA9AC`，28 B/行）：

| 行 | stock | menu64 |
| --- | --- | --- |
| 1 | 42/35 | **64/60** |
| 2 | 24/20 | **42/35** |
| 3 | 42/35 | **64/60** |
| 4 | 24/20 | **42/35** |
| 5 | 24/20 | **64/60** |
| 6 | 12/10 | **24/20** |
| 7 | 24/20 | **64/60** |
| 8 | 12/10 | **24/20** |
| 9 | 24/20 | **64/60** |

entry 10 起的低分辨率组、两个其他模块不变。

**代价**：原来的 Normal 低码率档被 `Stock` 占用；除英文/简体中文外的语言
标签没有改，行为仍会变成 High=64、Normal=Stock。

## 2. 工具

```sh
# 只检查 stock 表和标签
python bitrate/d750_menu_patch.py \
  --module D750_0115.dec.modules/b1010_115a.bin --check

# 生成改后模块
python bitrate/d750_menu_patch.py \
  --module D750_0115.dec.modules/b1010_115a.bin \
  --out b1010_115a.menu64.bin --json patch_report.json

# 单元测试（没有本地模块时全部 skipped）
D750_MODULE=/path/to/b1010_115a.bin python bitrate/test_d750_menu_patch.py
```

重打包 / 重新加密 / 容器 CRC 不在本仓库；使用同作者的
[Nikon-Expeed-4-and-5-firmware-tool](https://github.com/LuoStickmin/Nikon-Expeed-4-and-5-firmware-tool)
中的 `repack_firmware.py`。本仓库不提供固件、密钥、解密器或改后镜像。

## 3. 本地验证摘要

在 D750 `1.15` stock 模块上生成并验证（本地，不随仓库发布）：

- 模块 20,324,448 B 中 92 B 不同；
- 模块 CRC `0x12CA → 0x8B42`；
- 包 CRC `0x7EE4 → 0x7EE4`（CRC residue 性质）；
- 解密镜像 94 B 差异（9 行字段 + 4 个标签 + 模块 CRC），字段外 0 B；
- 3 个模块目录、长度、tag、两级 CRC 全过；`a1010`/`_wma` 未变；
- QEMU M0 与 stock 一致：`exit=0`、同一 halt 寄存器、0 MMIO、0 UART；
- 5 个单元测试通过。

哈希：

| 文件 | SHA-256 |
| --- | --- |
| stock 镜像 | `6c1dfadc8feb38bc783522c37f6351e1e8006f4684c8234690afb9aa08444859` |
| menu64 镜像 | `556a0ad88749e9dd492abc22510c4e2785f5f2fb647d15d17b5799d41f08f2a2` |
| stock 模块 | `faada7fe2bcc90fef8877fae37965ee836f867b08f5736c67c5266b1f82937fd` |
| menu64 模块 | `bf936b896057b370f32ce0f3e53c5a40e49641c63ae736e207c6691f28dfc5b9` |

## 4. 未验证与风险

1. **菜单 UI 未验证**：没有真机或 UI 模拟器，无法证明文字显示、选中行为、
   是否被截断/错位。
2. **持久化未验证**：菜单选择是否写入 NVRAM、重启是否保持。
3. **其他语言标签未改**：行为变但文字仍旧。
4. **Normal 低码率档被占用**。
5. **编码器/写卡/回放未验证**：64 Mbps 对 1080p30 约为 stock 24 Mbps 的
   2.7 倍，慢卡/发热/机内回放都可能出问题。
6. **刷机风险**：容器 CRC 自洽不等于相机接受；保留 stock，先短录测试。

---

# English version

## D750 menu-visible bit-rate switch: 64 Mbps HQ / Stock

> This is the design and verification summary for
> `bitrate/d750_menu_patch.py`. It is **not** a third Movie quality item; a
> genuine third item is currently blocked at the menu descriptor, see
> [../analysis/menu-bitrate-feasibility.md](../analysis/menu-bitrate-feasibility.md).

### 1. Design

Reuse the two existing Movie quality slots and replace their labels in place,
with the same UTF-16 length:

| Menu item | Old label | New label | 1080p behaviour |
| --- | --- | --- | --- |
| item 1 | `High quality` / `高品质` | `64 Mbps HQ  ` / `64M` | HQ rows 1/3/5/7/9 = `64/60` Mbps |
| item 2 | `Normal` / `标准` | `Stock ` / `原厂` | NQ rows 2/4/6/8 = stock HQ (`42/35` or `24/20`) |

Label lengths must stay unchanged:

- English `High quality` 12 chars -> `64 Mbps HQ  ` 12 chars (two trailing spaces)
- English `Normal` 6 chars -> `Stock ` 6 chars (one trailing space)
- Chinese `高品质` 3 chars -> `64M` 3 chars
- Chinese `标准` 2 chars -> `原厂` 2 chars

Bit-rate table (file offset `0x2AA9AC`, 28 B/row):

| Row | stock | menu64 |
| --- | --- | --- |
| 1 | 42/35 | **64/60** |
| 2 | 24/20 | **42/35** |
| 3 | 42/35 | **64/60** |
| 4 | 24/20 | **42/35** |
| 5 | 24/20 | **64/60** |
| 6 | 12/10 | **24/20** |
| 7 | 24/20 | **64/60** |
| 8 | 12/10 | **24/20** |
| 9 | 24/20 | **64/60** |

The lower-resolution group from entry 10 onward and the other two modules are
unchanged.

**Cost**: the old Normal low-bit-rate slot is consumed by `Stock`; labels in
languages other than English/Simplified Chinese are unchanged, while their
behaviour still becomes High=64, Normal=Stock.

### 2. Tool

```sh
# check the stock table and labels only
python bitrate/d750_menu_patch.py \
  --module D750_0115.dec.modules/b1010_115a.bin --check

# generate the patched module
python bitrate/d750_menu_patch.py \
  --module D750_0115.dec.modules/b1010_115a.bin \
  --out b1010_115a.menu64.bin --json patch_report.json

# unit tests (all skipped without a local module)
D750_MODULE=/path/to/b1010_115a.bin python bitrate/test_d750_menu_patch.py
```

Repack/encryption/container CRC are not in this repository; use
`repack_firmware.py` from the sibling
[Nikon-Expeed-4-and-5-firmware-tool](https://github.com/LuoStickmin/Nikon-Expeed-4-and-5-firmware-tool)
repository. This repository ships no firmware, keys, decryptor, or patched
images.

### 3. Local verification summary

Generated and verified on the D750 `1.15` stock module (local, not published):

- 92 B differ in the 20,324,448 B module;
- module CRC `0x12CA -> 0x8B42`;
- package CRC `0x7EE4 -> 0x7EE4` (CRC residue property);
- the decrypted image differs by 94 B (9 row fields + 4 labels + module CRC),
  with 0 B outside those regions;
- all 3 module directory entries, lengths, tags, and both CRC levels pass;
  `a1010`/`_wma` are unchanged;
- QEMU M0 matches stock: `exit=0`, same halt registers, 0 MMIO, 0 UART;
- 5 unit tests pass.

Hashes:

| File | SHA-256 |
| --- | --- |
| stock image | `6c1dfadc8feb38bc783522c37f6351e1e8006f4684c8234690afb9aa08444859` |
| menu64 image | `556a0ad88749e9dd492abc22510c4e2785f5f2fb647d15d17b5799d41f08f2a2` |
| stock module | `faada7fe2bcc90fef8877fae37965ee836f867b08f5736c67c5266b1f82937fd` |
| menu64 module | `bf936b896057b370f32ce0f3e53c5a40e49641c63ae736e207c6691f28dfc5b9` |

### 4. Unverified items and risks

1. **Menu UI unverified**: no camera or UI emulator, so label rendering,
   selection behaviour, truncation, and layout are unproven.
2. **Persistence unverified**: whether the selection is written to NVRAM and
   survives a reboot is untested.
3. **Other language labels unchanged**: behaviour changes but text does not.
4. **Normal low-bit-rate slot is consumed.**
5. **Encoder/card/playback unverified**: 64 Mbps is about 2.7x the stock
   24 Mbps at 1080p30; slow cards, heat, or in-camera playback may fail.
6. **Flashing risk**: a self-consistent container CRC does not mean the camera
   accepts the image; keep stock and start with a short test clip.
