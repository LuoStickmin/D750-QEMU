# Notice

> [English](NOTICE.en.md) | 中文

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

## 法律与合规

- 本文不是法律意见；固件修改、校验绕过、DMCA §1201、EU 2009/24/EC 的
  适用因司法辖区而异，请自行确认合法性。
- 本项目仅用于**自己合法拥有的设备**与本地获取的固件上的互操作性/研究；
  不提供盗版、付费功能绕过或技术保护措施规避教程。
- 软件按“现状”提供，不提供任何明示或默示担保；维护者不对使用后果负责。
- 如果权利人提出有依据的请求，维护者会移除相关内容并保留记录。
- 贡献边界与 DCO 见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 第三方与参考

- Nikon Hacker 的补丁数据库/工具仅作为参考链接，**不在本仓库再分发**：
  <https://github.com/simeonpilgrim/nikon-firmware-tools>
- WonderLantern 的 QEMU 项目与密钥工具仅作为架构/方法参考：
  <https://github.com/WonderLantern/z7-qemu>、
  <https://github.com/WonderLantern/z9-qemu>、
  <https://github.com/WonderLantern/nikon-fw-key-tool>
- Nikon、D750、EXPEED 是其各自权利人的商标，仅用于标识研究对象。

## 许可

- `qemu/` 下的 overlay、`tools/`、`tests/`、`docs/`、`bitrate/`：**GPL-2.0-or-later**。
- 上游 QEMU 保留其逐文件许可；QEMU 整体为 GPLv2。

本项目的 GPL 许可不授予任何 Nikon 固件或第三方私有材料的权利。
