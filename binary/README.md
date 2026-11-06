# binary/qemu-system-arm

> [English](README.en.md) | 中文

Nikon `nikon-d750` overlay 的已构建 QEMU 二进制。

> **该文件约 96 MiB，不进入 Git 历史**，作为 GitHub Release 附件发布。
> 下载地址：
> <https://github.com/LuoStickmin/D750-QEMU/releases/latest/download/qemu-system-arm>

| 项目 | 值 |
| --- | --- |
| QEMU 版本 | 11.1.0 |
| 发布版本 | v0.1.1（含 `strict` 停止与 `return_ok` 校验） |
| 平台 | Linux x86-64（WSL2 Ubuntu 26.04） |
| 大小 | 100,594,216 字节 |
| SHA-256 | `28c1ac20675ae7c7df1f7f48b4e48ed15a62ccf5e678d3a257399578aafee1ae` |
| 许可 | GPLv2；见同目录 `COPYING` |

## 获取与运行

```bash
cd /path/to/D750-QEMU
curl -L -o binary/qemu-system-arm \
  https://github.com/LuoStickmin/D750-QEMU/releases/latest/download/qemu-system-arm
chmod +x binary/qemu-system-arm
./binary/qemu-system-arm -M help | grep nikon
```

应看到：

```
nikon-d750           Nikon D750 validation prototype (EXPEED 4, experimental)
```

启动一次 M0：

```bash
python3 tools/run.py --qemu binary/qemu-system-arm \
  --payload /path/to/b1010_115a.bin \
  --flash   /path/to/a1010_011100.bin
```

## 依赖

在构建它的同一 WSL 发行版里运行最稳妥（glib 2.88、pixman 0.46）。
在其他 Linux 上如果缺共享库，按 `docs/build.md` 重新构建即可；源码在
`qemu/`，构建脚本在 `tools/build.py`。

## 重建

```bash
python3 tools/build.py --source <QEMU 11.1.0 源码树> --jobs 4
```

或按 `docs/build.md` 从 tarball 构建。重建后的二进制 SHA-256 可能不同
（取决于编译器/时间戳），属正常现象。
