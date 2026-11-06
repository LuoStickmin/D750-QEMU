> [English](README.en.md) | 中文

# D750 1080p 高码率修改（64/60 Mbps）

> **范围**：本文与 `bitrate/` 工具只做**本地静态修改与容器级验证**。
> 不包含固件、密钥、解密镜像或改后镜像；相机实拍未验证，刷机风险自担。
> 见 [CONTRIBUTING.md](../CONTRIBUTING.md) 与 [NOTICE.md](../NOTICE.md)。

## 1. 结论

| 项目 | 结果 |
| --- | --- |
| 目标 | Nikon D750，`D750_0115`（1.15），模块 `b1010_115a.bin` |
| 修改表 | 文件偏移 `0x2AA9AC`，28 字节/项，1080p 组共 9 项 |
| 命中行 | entry 1 / 3 / 5 / 7 / 9（HQ 行） |
| 修改前 | `42/35`、`42/35`、`24/20`、`24/20`、`24/20` Mbps |
| 修改后 | 全部 `64/60` Mbps（`0x03D09000` / `0x03938700`） |
| 未改动 | 4 个 NQ 行、entry 10 起的低分辨率组、另外两个模块 |
| 模块 CRC | `0x12CA` → `0x4314` |
| 包 CRC | `0x7EE4` → `0x7EE4`（CRC residue 性质，不是“没改到”，见 §3） |
| 解密镜像差异 | 36 B：34 B 码率字段 + 2 B 模块 CRC；字段外 0 B |
| QEMU M0 回归 | 与 stock 一致：exit 0、同一 halt 寄存器、0 MMIO、0 UART |
| 相机实拍 | **未验证** |

## 2. 表项与偏移

`b1010_115a.bin` 中 1080p 组从 `0x2AA9AC` 开始：

```
entry 1  0x2AA9AC
entry 2  0x2AA9C8
entry 3  0x2AA9E4
entry 4  0x2AAA00
entry 5  0x2AAA1C
entry 6  0x2AAA38
entry 7  0x2AAA54
entry 8  0x2AAA70
entry 9  0x2AAA8C
entry 10 0x2AAAA8   <- 上限降到 47.19 Mbps，推断为 720p/480p 组，未改
```

每项前两个 little-endian u32 是两档码率，随后是 `flag=1`、该项上限
（1080p 组为 `0x04380780` = 70,780,800 bps），以及时间基/帧率字段。
64/60 Mbps 低于 70,780,800 的上限。

这个“5 个 HQ 行”的映射与 Nikon Hacker 的 D810 1.14 补丁同构：D810 的
`Video 1080 HQ 64mbps` 也是改 entry 1/3/5/7/9，写
`64,000,000 / 60,000,000`；两机的表都是 28 字节/项、字段顺序与上限相同。

## 3. 验证

修改器 `bitrate/d750_bitrate_patch.py` 在写入前强制核对：

1. 9 个 1080p 行的 stock 值必须与 `STOCK_ROWS` 完全一致；
2. 5 个 HQ 行必须是 `42/35` 或 `24/20`，且 `flag == 1`、上限为 70,780,800；
3. 目标 64/60 必须低于上限；
4. 改后重新解析，5 行必须读回 64/60；
5. 4 个 NQ 行逐字节不变；
6. 差异只能落在 5 行 × 2 个 u32 字段内（`verify_patch()` 逐字节检查）。

独立验证（`d750_bitrate_verify.py`、`repack_firmware.py` 在同作者的
[Nikon-Expeed-4-and-5-firmware-tool](https://github.com/LuoStickmin/Nikon-Expeed-4-and-5-firmware-tool)
仓库中，运行需要你本地持有的密钥/解密器）：

```
stock   image sha256 6c1dfadc8feb38bc783522c37f6351e1e8006f4684c8234690afb9aa08444859
patched image sha256 9c88f3cc80e5e19d780055ced0e4e539739f0e858af1e831228e5f19e904988a
module  sha256       ea0c161dd8bfc7fdd7037c13005e8a4f7f3ddf98a79c9565e2c8aa973ba3f579
package CRC 0x7EE4 -> 0x7EE4
b1010 CRC   0x12CA -> 0x4314
changed decrypted bytes: 36 (fields+CRCs), outside: 0
HQ rows at target:
  entry 1 @0x2AA9AC  64000000 / 60000000
  entry 3 @0x2AA9E4  64000000 / 60000000
  entry 5 @0x2AAA1C  64000000 / 60000000
  entry 7 @0x2AAA54  64000000 / 60000000
  entry 9 @0x2AAA8C  64000000 / 60000000
all checks passed
```

**可复现边界（2026-11-06 更新）**：改后镜像现在可以逐字节复现——

- 无修改重打包 stock：`repack_firmware.py --selftest` 的输出与输入
  **bit-identical**（sha256 `6c1dfadc…08444859`）；
- stock + 改后 `b1010` 模块重打包：输出与本文的 `9c88f3cc…e904988a`
  **逐字节一致**；
- 容器差异：同大小 21,552,187 B；文件头 32 B 不变；仅 **36 B** 不同，位置为
  `0x3D6575..0x3D665C`（5 个 HQ 行）与 `0x148DC29..2A`（b1010 模块 CRC）；
  包 CRC 字段 `0x148DC2B` 保持 `f540`（residue）；另外两个模块逐字节相同。

**包装说明**：D750 使用**包装 A**（`0x00` 起 32 个空格，文件里没有 20 字节
带密钥摘要），因此 K8/`STALE` 只影响包装 B（D850/D5 那类），与 D750 无关。

这证明容器/CRC/重加密链路可复现，**不**证明相机更新器接受，也不证明编码器
行为；实机前置条件见 [docs/hardware-test.md](../docs/hardware-test.md)。

**为什么包 CRC 没变：** CRC-16 的 residue 性质使
`CRC16(payload || CRC16(payload)) == 0`；每个模块末尾带自己的 CRC，包 CRC
对“模块 payload 变化 + 模块 CRC 重算”不敏感。payload 确实变了，证据是模块
CRC `0x12CA → 0x4314` 和 36 B 差异，而不是包 CRC。

## 4. 哈希

| 文件 | 大小 | SHA-256 |
| --- | ---: | --- |
| `D750_0115.bin`（stock 加密镜像） | 21,552,187 | `6c1dfadc…08444859` |
| `D750_0115.hq64.bin`（改后镜像，本地） | 21,552,187 | `9c88f3cc…e904988a` |
| `b1010_115a.bin`（stock 模块） | 20,324,448 | `faada7fe…f82937fd` |
| `b1010_115a.hq64.bin`（改后模块，本地） | 20,324,448 | `ea0c161d…ba3f579` |
| `D750_0115.dec`（stock 解密） | 21,552,187 | `1ec77111…7c749bdd` |
| `D750_0115.hq64.dec`（改后解密） | 21,552,187 | `79e59294…ca1c300` |

完整哈希见本地 `D750_0115.hq64.out/verify_report.json`；仓库不包含这些镜像。

## 5. 工具

```sh
# 只检查表
python bitrate/d750_bitrate_patch.py \
  --module D750_0115.dec.modules/b1010_115a.bin --check

# 生成改后模块
python bitrate/d750_bitrate_patch.py \
  --module D750_0115.dec.modules/b1010_115a.bin \
  --out b1010_115a.hq64.bin --json patch_report.json

# 单元测试（需要本地模块；没有时 4 个用例全部 skipped）
D750_MODULE=/path/to/b1010_115a.bin python bitrate/test_d750_bitrate_patch.py
```

重打包 / 重新加密 / 容器 CRC 不在本仓库，但在同作者的
[Nikon-Expeed-4-and-5-firmware-tool](https://github.com/LuoStickmin/Nikon-Expeed-4-and-5-firmware-tool)
仓库（`repack_firmware.py`）中；本仓库仍不提供密钥、解密器或改后镜像。

## 6. 风险与未验证项

1. **编码器/写卡/回放未验证。** 64 Mbps 对 1080p30 是 stock 24 Mbps 的约
   2.7 倍；相机可能在慢卡上提前停止、录出电脑能播但相机不能回放的文件，
   或因发热/编码器上限降码率。
2. **更新器接受度未验证。** 本工具与同作者的重打包工具只保证容器 CRC 自洽；
   D750 是包装 A、文件里没有签名头，但更新器是否另有型号/版本/隐藏校验未知，
   同版本（1.15 → 1.15）重刷策略也未知。改后镜像**不保证被相机接受**；上机
   前置条件见 [docs/hardware-test.md](../docs/hardware-test.md)。
3. **不要拿唯一一台工作机试。** 保留 stock 镜像；确认电量、使用已知良好的
   UHS-I 卡、先短录 10–30 秒，再检查码率与回放。
4. 本次只改 1080p 的 5 个 HQ 行；NQ 仍是 24/20 与 12/10，720p/480p 组未动。

## 7. 参考

- Nikon Hacker D810 1.14 补丁定义（`Video 1080 HQ 64mbps`）：
  <https://github.com/simeonpilgrim/nikon-firmware-tools>
- 高码率说明：
  <https://simeonpilgrim.com/blog/2014/02/23/high-bit-rate-recording-now-solved/>
- QEMU 回归见 [../docs/validation.md](../docs/validation.md) 与
  [../evidence/](../evidence/)。
