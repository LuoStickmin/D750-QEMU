# 构建与已安装 QEMU 的核对

> [English](build.en.md) | 中文

## 1. 本机现状（已核对）

| 项目 | 值 |
| --- | --- |
| 安装路径 | `C:\Program Files\qemu` |
| 版本 | `11.1.0`（VERSION 文件；文件版本 2026-08-11） |
| 系统模拟器 | `qemu-system-arm.exe`、`qemu-system-aarch64.exe`（另有 `w` 变体） |
| `-M help` | 只有上游 ARM 机器，**没有** `nikon-*` |
| 结论 | 这是一个 **stock 构建**，不能在运行时加载新 machine |

QEMU 的 machine 类型在编译期通过 `type_init()` 注册；`-M` 只接受已经编进
二进制里的名字。因此“用已安装的 QEMU 直接跑 D750”不成立，必须把
`hw/arm/nikon-d750-lab.c` 编进一个 `qemu-system-arm`。

安装的二进制仍然有用：`tools/probe.py` 已对它的 `-M virt -S -gdb` 做过
真实 RSP 联调（读寄存器、读内存、硬件断点、continue、CPSR 解析均通过），
所以协议层不是纸上实现。

## 2. 依赖

共同：Python 3.12+、Ninja、pkg-config、GLib、Pixman、zlib、FDT 开发包、
一个 C 编译器。

Linux（Ubuntu 24.04 一类）：

```sh
sudo apt-get update
sudo apt-get install build-essential ninja-build pkg-config \
    libglib2.0-dev libpixman-1-dev zlib1g-dev libfdt-dev
```

Windows（MSYS2 UCRT64，路径与 z7-qemu 相同）：

```sh
pacman -S --needed make diffutils mingw-w64-ucrt-x86_64-gcc \
  mingw-w64-ucrt-x86_64-glib2 mingw-w64-ucrt-x86_64-pixman \
  mingw-w64-ucrt-x86_64-pkgconf mingw-w64-ucrt-x86_64-python \
  mingw-w64-ucrt-x86_64-ninja mingw-w64-ucrt-x86_64-meson \
  mingw-w64-ucrt-x86_64-dtc mingw-w64-ucrt-x86_64-zlib
```

Windows 需要允许创建符号链接（开发者模式或相应权限），否则 QEMU 的
meson 配置会失败。

## 3. 构建

```powershell
python tools/build.py --msys-root C:\msys64 --jobs 4
```

Linux：

```sh
python tools/build.py --jobs 4
```

脚本会：

1. 下载 `https://download.qemu.org/qemu-11.1.0.tar.xz`（或使用 `--archive` /
   `--source`）；
2. 解包到 `.build/src/`，带完成标记，避免半解包；
3. 调用 `qemu/prepare_source.py` 安装 overlay；
4. `./configure --target-list=arm-softmmu --disable-werror --disable-docs --disable-tools`
   + `ninja -C build`（关掉 docs/tools 是为了不依赖 PyPI 上的 sphinx 与 qemu.qmp）；
5. 找到 `build/qemu-system-arm[.exe]`，把 SHA-256、overlay 摘要、configure
   参数写入 `.local/build-manifest.json`。

离线：

```powershell
python tools/build.py --archive D:\downloads\qemu-11.1.0.tar.xz
python tools/build.py --source D:\src\qemu-11.1.0
```

只装 overlay、不编译（用于检查补丁是否幂等）：

```powershell
python tools/build.py --source D:\src\qemu-11.1.0 --overlay-only
```

## 4. 构建后自检

```powershell
& .build\build\qemu-system-arm.exe -M help | Select-String nikon
```

应看到：

```
nikon-d750           Nikon D750 validation prototype (EXPEED 4, experimental)
```

再确认机器能起来（没有 payload 会明确报错，这是预期）：

```powershell
& .build\build\qemu-system-arm.exe -M nikon-d750 -display none -monitor none
# nikon-d750: a decrypted main payload is required; pass -kernel FILE ...
```

## 5. 版本兼容

- **11.1.0**：首选目标。chardev 前端类型是 `CharFrontend`。
- **10.2.4**：`prepare_source.py` 会把源码里的 `CharFrontend` 换成
  `CharBackend`，其余 API 与 z7-qemu 的目标版本一致。
- 其他版本：prepare 会拒绝；确认 API 后再加进 `SUPPORTED`，不要静默尝试。

## 6. 故障排查

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `no VERSION` / `unexpected tree` | `--source` 指错 | 指向含 `VERSION`、`hw/arm/` 的 QEMU 根目录 |
| configure 找不到 glib/pixman | MSYS2 包不全或 PATH 不对 | 在 UCRT64 shell 里 `pkg-config --modversion glib-2.0` |
| `ninja: command not found` | 未装 ninja 或在错误 shell | 用 `--msys-root`，不要用 PowerShell 直接跑 configure |
| 符号链接权限错误 | Windows 未开开发者模式 | 开启后重试，或改用 WSL |
| `machine 'nikon-d750' not found` | 用了安装版 QEMU | 用 `.build/src/qemu-<版本>/build/qemu-system-arm` |
| 下载 404 | 版本号/镜像不可用 | 预先下载 tarball，用 `--archive` |

## 7. 本环境验证记录（2026-11-05）

实际构建并运行通过，环境与细节如下。

| 项目 | 值 |
| --- | --- |
| 环境 | WSL2 Ubuntu 26.04.1 LTS |
| 编译器 | gcc 15.2.0 |
| 依赖 | glib 2.88.0、pixman 0.46.4、zlib 1.3.1、ninja 1.13 |
| Python | 3.14.4 |
| QEMU | 11.1.0（tarball SHA-256 `6ee1d1a6…08fa858`） |
| 构建命令 | `python3 tools/build.py --work-dir ~/d750-build --jobs 12` |
| 产物 | `~/d750-build/src/qemu-11.1.0/build/qemu-system-arm`（96 MB，含调试符号） |

注意事项：

1. `--work-dir` 放 WSL 的 `$HOME` 下；默认用户对 `/root` 没有写权限。
2. PyPI 不可达时，configure 会尝试安装 `qemu.qmp` 并打印重试失败，但会继续；
   `--disable-docs --disable-tools` 已避开 sphinx 与 qemu.qmp 的硬依赖。
3. 首次编译暴露并修复了两个真实 API 细节：
   - `qdev_prop_set_uint32()` 需要 `hw/core/qdev-properties.h`；
   - `memory_region_init_ram()` 的 owner 必须是 `DeviceState` 或 `NULL`，
     传 `MachineState` 会触发 `DEVICE: Object ... is not an instance of type device`。
4. `-M help` 中确认出现：

   ```
   nikon-d750           Nikon D750 validation prototype (EXPEED 4, experimental)
   ```

5. 运行 `tools/run.py` 的结果见 [validation](validation.md) 的 M0：
   0.18 s、退出码 0、`qemu.log` 记录 halt 时的 `r0/r1/sp/lr`。

Windows 侧仍没有 MSYS2 构建产物；本仓库交付的是可复现的源码 + WSL 构建路径。
`C:\Program Files\qemu` 的 stock 二进制依旧不能加载这个 machine。
