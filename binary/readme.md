# binary/qemu-system-arm (预编译二进制)

Nikon `nikon-d750` overlay 的已构建 QEMU 二进制（仅限 Linux x86-64，WSL 环境）。

> ⚠️ **注意**：由于该文件体积较大（约 96 MiB），已超过 GitHub 建议的单文件大小，直接提交会导致仓库 `clone` 极慢。本仓库已通过 `.gitignore` 默认忽略此文件。
> 请前往本仓库的 **[Releases](https://github.com/你的用户名/你的仓库名/releases)** 页面，下载最新的 `qemu-system-arm` 压缩包，并解压至此目录。

## 预期校验和

如果你下载了正确的预编译版本，其属性应如下：

| 项目 | 值 |
| --- | --- |
| QEMU 版本 | 11.1.0 |
| 平台 | Linux x86-64（WSL2 Ubuntu 26.04） |
| 大小 | 100,591,008 字节 |
| SHA-256 | `7b84c339a1f6cfe7381d27b9c91c45816ecb0e2ca727329bc2e6acb55353b4c5` |
| 许可 | GPLv2；见同目录 `COPYING`（或上游 QEMU 源码树） |

## 运行

只能在 Linux/WSL 里执行（Windows 侧 stock QEMU 没有该 machine）：

```bash
./binary/qemu-system-arm -M help | grep nikon
```

应看到：

```text
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
在其他 Linux 上如果缺共享库，按 `docs/build.md` 重新构建即可；源码在 `qemu/`，构建脚本在 `tools/build.py`。

## 重建（无需下载 Release）

如果你想在本地自己编译，而不是下载预编译附件：

```bash
python3 tools/build.py --source <QEMU 11.1.0 源码树> --jobs 4
```

或按 `docs/build.md` 从 tarball 构建。重建后的二进制 SHA-256 可能不同（取决于编译器/时间戳），属正常现象。
