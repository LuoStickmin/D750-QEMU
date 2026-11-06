# Changelog

## v0.1.1 — 2026-11-06

修复 v0.1.0 评审中发现的证据与可用性问题；行为变化只涉及 `strict` 模式、
`halt` 记录格式和 `tools/run.py` 的汇总/退出码。

### 修复

- **`strict=on` 现在真的会停**：第一条未建模访问记为 `d750-strict:`
  （地址/宽度/方向/PC），随后停止本次运行；不再把未映射访问变成 guest abort。
  旧行为会让异常向量落到低内存 NOP 滑梯并滑进 halt 窗口，看起来像一次成功
  的 M0。
- **halt 状态校验**：`d750-halt:` 记录新增 `return_ok=` 与 `mode=`；只有
  SVC 模式、`LR=0xFF0`、`SP=RAM 顶` 才算正常返回。`run.py` 对
  `return_ok=false` 返回退出码 6。
- **`tools/run.py`**：记录 `payload_sha256` / `flash_sha256` / `*_size`；
  汇总 `status`；解析 `d750-strict:` 并写入 `session.json.strict`；`--strict`
  停止时退出码 7。旧的 v0.1.0 二进制输出仍可解析（无 `return_ok` 视为未知）。
- **构建后自检路径**：`Setup-D750.ps1` 与 `docs/build.md` 使用
  `.build/src/qemu-<版本>/build/`，与实际产物一致。
- **`bitrate/README.md` 重写**：原文件是双重编码的乱码（42/103 行不可读），
  按英文版重建，并补充“CRC/打包验证依赖未发布工具”的可复现边界。
- **文档一致性**：M0 实测时间统一为证据文件里的 0.39 s（原写 0.18 s）；
  `MANIFEST`/`PRODUCT` 的 bitrate 测试标注“需 `D750_MODULE`，否则 4 skipped”；
  清理英文文档里未翻译的中文片段；补充中文 README 目录。
- **许可**：`bitrate/*.py` 与 `analysis/tiff_scan.py` 补 SPDX 头。

### 新增

- `tools/manifest.py`：重新生成/校验 `SHA256SUMS` 与 `MANIFEST.json.files`。
- `.github/workflows/ci.yml`：Ubuntu + Windows 上跑主机侧测试、bitrate 测试
  （无模块时跳过）和清单校验。
- `CHANGELOG.md`。

### 兼容性

- 机器选项与命令行不变；M0 的寄存器结果与 v0.1.0 一致。
- 新的 Linux 二进制作为 v0.1.1 Release 附件发布，`binary/qemu-system-arm.sha256`
  与 `MANIFEST.json.binary` 同步更新。

## v0.1.0 — 2026-11-05

首个公开快照：`nikon-d750` QEMU 验证原型（M0）、LCD dump 管线、1080p
64/60 Mbps 改表工具、双语文档与 M0 证据。
