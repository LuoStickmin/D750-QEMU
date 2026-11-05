> [English](README.en.md) | 中文

# analysis/

本目录只保留**可公开的事实性产物**，不包含固件、密钥、解密镜像或改后镜像。

| 文件 | 内容 |
| --- | --- |
| `d750-0115.json` | `fwscan` 对真实镜像的 profile 核对结果：大小、SHA-256、向量/字面量、MMU 站点、指针分布。 |
| `lcd-testcard.png` | `nikon-d750` LCD dump 管线的合成测试卡（主机写入，不是固件 UI）。 |
| `tiff-feasibility.md` / `.en.md` | D750 菜单加入 TIF 的可行性分析：只读静态结论与证据。 |
| `tiff_scan.py` | 上述分析的只读扫描器；`--module` 可指定本地模块。 |

## 未公开的探索性材料

以下内容**不进入公共仓库**，保留在本地 `.local/private-analysis/`，原因是
版权、隐私或可复现性：

- Nikon Hacker 的补丁数据库（`nikon_patches.c`、`nikon_patches.h`、
  `nikon_patch_main.c`）及其解析脚本——第三方 GPL 代码，且包含大量补丁字节；
- 固件 ASCII 字符串 dump（`strings_movie.txt`）——含固件文本，可能涉及版权；
- 一次性探索脚本（`scan_bitrate_*.py`、`dump_*.py`、`search_bitrate.py` 等）
  ——硬编码了本机路径，且已被结论/工具取代。

需要复现某一步时，按文档里的偏移/哈希重新写一个最小脚本即可；不要把固件、
密钥或第三方补丁表提交到 issue/PR。

## 边界

- 本目录没有固件二进制，也没有可用于刷机的镜像；
- 所有偏移/哈希都是事实性信息，不构成对 Nikon 代码/资源的再分发；
- 见 [../CONTRIBUTING.md](../CONTRIBUTING.md) 与 [../NOTICE.md](../NOTICE.md)。
