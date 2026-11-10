# 夸克焦点延迟助手

**保留夸克 TV 官方客户端，清除特定设备上持续覆盖视频的蓝色全屏焦点高亮，并保留遥控器暂停、继续和导航。**

版本：**v0.0.1** · 许可证：[MIT](LICENSE) · 无 Root · 无联网权限

## 用途

在部分由三星手机改装的电视盒子上，夸克 TV 播放视频时，即使控制栏已经收起，画面仍可能覆盖一层蓝色。本项目针对实测设备上的 Android 默认全屏焦点高亮问题，提供独立的无障碍助手与 ADB 配套进程。

助手在夸克 TV 前台监听导航与确认键，在需要时先恢复焦点，再让原按键继续传递；最后一次相关按键、窗口变化或焦点变化后，默认等待 **3 秒**，尝试清除全屏焦点高亮。这样可以兼顾正常观看与遥控器暂停、继续操作。

> 3 秒从最后一次相关事件开始计算。控制栏收起时的焦点变化也会重新计时，因此从“点击播放”到蓝层消失的总时间可能超过 3 秒。

## 实测环境

| 项目 | 已验证配置 |
| --- | --- |
| 设备 | Samsung SM-F926U（Galaxy Z Fold3）改装盒子 |
| 系统 | Android 14 / API 34 |
| 播放器 | 官方夸克 TV 2.9.1702 |
| 输入 | 实体遥控器导航键、确认键 |
| 效果 | 用户已确认蓝层消失，暂停、继续正常 |

v0.0.1 的最低安装版本为 Android 14。配套进程使用系统隐藏接口，目前仅支持 Android 14；其他系统和夸克版本需要单独适配。本项目只处理 `com.quark.yun.tv` 位于前台时的全屏焦点问题，不能保证解决其他原因造成的画面偏色或遮罩。

## 下载与安装

使用发布包中的以下文件，并保持目录结构：

```text
quark-tv-focus-helper-v0.0.1/
├── README.md
├── docs/INSTALL.md
├── scripts/device.py
└── releases/v0.0.1/
    ├── QuarkFocusHelper-v0.0.1.apk
    ├── quark-binder-agent.dex
    └── SHA256SUMS.txt
```

电脑需要 Python 3.10+ 和 [Android platform-tools（ADB）](https://developer.android.com/tools/releases/platform-tools)。以下命令在解压后的项目根目录执行；如果 ADB 不在 PATH，增加 `--adb "完整路径/adb.exe"`。

1. 开启设备 USB 调试或无线调试，并完成 ADB 授权、配对与连接。无线调试的配对端口与连接端口不同。
2. 安装独立助手：`python scripts/device.py install`。
3. 在设备的“设置 → 无障碍 → 已安装的应用/服务”中，**手动开启“夸克焦点延迟助手”**。也可执行 `python scripts/device.py open-settings` 打开设置。
4. 启动配套进程：`python scripts/device.py start`。
5. 回到官方夸克 TV，用实体遥控器测试暂停、继续播放，等待控制栏收起和蓝层消失。

**仅安装 APK 不足以清除蓝层，还需要运行 ADB 配套进程。** 助手没有桌面启动图标，请到无障碍设置中查找。首次安装后，部分系统要求先在应用信息右上角菜单中“允许受限制的设置”，再手动开启无障碍。

**成功启动后可断开电脑。设备重启后配套进程会停止，需要重新连接 ADB 并执行 `start`；重启电脑本身不需要重新启动手机上的进程。**

完整说明、无线配对和常见问题见 [安装与使用](docs/INSTALL.md)。

## 常用命令

```bash
# 检查配套进程及无障碍开关
python scripts/device.py status

# 修改延迟为 3 秒，支持 1～15 秒，无需重装
python scripts/device.py set-delay --delay 3

# 手机重启后，重新启动；不指定时默认使用 3 秒
python scripts/device.py start --delay 3

# 多台设备连接时指定 ADB 序列号或连接地址
python scripts/device.py status --serial DEVICE_SERIAL

# 停止配套进程；彻底停用时再手动关闭无障碍开关
python scripts/device.py stop

# 卸载独立助手及配套文件，保留官方夸克与其数据
python scripts/device.py uninstall
```

## 原理与权限

无障碍服务读取当前窗口的包名、焦点、控件边界，并接收导航/确认键事件。它在处理后返回 `false`，让系统继续传递原始按键。需要清除高亮时，助手通过经过认证的 Binder 调用 ADB shell 进程，检查夸克是否处于前台，再切换当前显示器的触摸模式并清除全屏焦点。

- 无 Root，无第三方登录，无广告，无统计 SDK；APK 不申请互联网或存储权限。
- 保留官方夸克 APK、签名和播放授权，不修改视频和云端文件。
- 运行时随机生成认证密钥，不在源码和发布包中内置共享密钥。
- 无障碍授权由用户在系统设置中完成，脚本不自动打开或修改该授权。
- 调试日志包含按键码、焦点状态、耗时和进程 UID，不记录控件文本、账号或视频内容。

详见 [架构说明](docs/ARCHITECTURE.md) 和 [隐私说明](docs/PRIVACY.md)。这是独立社区工具，与夸克、三星或 Google 没有隶属或合作关系。

## 源码与构建

```text
app/src/main/                  无障碍助手源码和 Android 资源
companion/src/main/java/        ADB shell Binder 配套进程
scripts/build.py               校验工具哈希、编译、打包与签名
scripts/device.py              安装、启动、检查和停用
tools.lock.json                固定构建工具下载地址与 SHA-256
version.json                   APK 版本和 API 配置
docs/                          安装、构建、隐私与架构说明
```

本项目直接编译 Java 源码并打包 Android 资源，不依赖 Gradle。需要 Python 3.10+、JDK 17+。详见 [构建说明](docs/BUILD.md)。

```bash
python scripts/build.py
```

默认输出到 `build/dist/`，使用开发签名；自己的公开发布请使用私有签名证书。发布签名私钥不包含在仓库中。

v0.0.1 使用 `versionName=0.0.1`、`versionCode=5`，可以覆盖此前使用同一签名的内部测试版。行为沿用用户实测通过的实现，默认延迟为 3 秒；本次发布重建完成了编译、签名与包内容检查，未在设备上重新安装或重复实机验证。

## 反馈与贡献

提交问题前请参照 [贡献说明](CONTRIBUTING.md)，提供系统、夸克版本、实体遥控器表现和必要的脱敏日志。不要上传配对码、认证密钥、登录二维码或网盘内容。

发布历史见 [CHANGELOG.md](CHANGELOG.md)，v0.0.1 说明见 [发行说明](docs/RELEASE-v0.0.1.md)。本仓库按 [MIT 许可证](LICENSE) 开源。
