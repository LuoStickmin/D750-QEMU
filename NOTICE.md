# Notice

## 独立研究声明

本项目是独立的固件研究/学习工程，不是 Nikon 或 WonderLantern 的官方发布，
也未获其背书。Nikon、D750、EXPEED 是其各自权利人的商标，仅用于标识研究对象。
项目不主张对 Nikon 固件、固件中的代码/资源或任何相机私有数据的权利。

## 不包含固件

本仓库**不包含**任何 Nikon 固件、解密后的程序、相机 dump、密钥、字体/图标、
校准数据或相机 UI 截图。`analysis/d750-0115.json` 只包含长度、SHA-256、
文件偏移和地址常量，不包含镜像字节。工具不会下载固件。

使用本项目需要你自己合法持有的、已解密的 D750 模块；工具以只读方式打开它们。
不要在 issue、PR、release 或共享构建缓存里附加固件或其派生数据。

## 风险

刷机、重打包、绕过签名不在本项目范围内。任何对相机的修改都可能导致变砖、
数据丢失或需要付费维修；本项目不提供恢复方案，也不对后果负责。

## 许可

- `qemu/` 下的 overlay、`tools/`、`tests/`、`docs/`：**GPL-2.0-or-later**。
- 上游 QEMU 保留其逐文件许可；QEMU 整体为 GPLv2。
- 参考项目：
  - <https://github.com/WonderLantern/z7-qemu>
  - <https://github.com/WonderLantern/z9-qemu>
  - <https://github.com/WonderLantern/nikon-fw-key-tool>

本项目的 GPL 许可不授予任何 Nikon 固件或第三方私有材料的权利。
