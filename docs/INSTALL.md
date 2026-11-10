# 安装与使用

## 准备

- Android 14 / API 34；目前只验证过 Samsung SM-F926U 和官方夸克 TV 2.9.1702。
- 使用官方夸克 TV 并确认能够正常登录与播放。
- 电脑安装 Python 3.10+ 和 Android platform-tools。执行 `adb version` 与 `python --version` 确认可用。
- 解压完整发布包。APK 与配套 DEX 必须来自同一发布包，保持 `scripts/`、`docs/`、`releases/` 目录结构。

本助手没有桌面启动图标，安装后从无障碍设置查找。无需 Root，也不用卸载官方夸克。

## ADB 连接

USB 连接时，在设备上接受该电脑的 USB 调试授权，执行 `adb devices` 确认状态为 `device`。

无线连接时，电脑与盒子应处于可互通的局域网。开启“开发者选项 → 无线调试”：

```text
adb pair DEVICE_IP:PAIRING_PORT
```

按提示输入设备上显示的配对码。关闭配对弹窗，使用无线调试**主页面**的另一个端口连接：

```text
adb connect DEVICE_IP:CONNECTION_PORT
adb devices
```

`DEVICE_IP`、`PAIRING_PORT` 和 `CONNECTION_PORT` 是占位符，请替换成设备当前显示的信息。重新开启无线调试后连接端口可能改变；已完成的配对通常仍然有效。

## 首次使用

以下命令均在发布包根目录执行。ADB 不在 PATH 时，每条命令加 `--adb "ADB可执行文件完整路径"`；多设备时加 `--serial "设备序列号或连接地址"`。

```bash
python scripts/device.py install
python scripts/device.py open-settings
```

在设备上手动找到“已安装的应用/服务 → 夸克焦点延迟助手”并开启。对于侧载 APK，如果开关被系统限制，请到“应用信息 → 右上角菜单 → 允许受限制的设置”，再返回手动开启。

```bash
python scripts/device.py start --delay 3
python scripts/device.py status
```

启动工具会校验发布文件 SHA-256、向 `/data/local/tmp` 推送配套 DEX、随机生成 32 字节认证密钥，最后启动 ADB shell 进程并检查 Binder 注册成功。临时密钥文件用完即从电脑临时目录删除，手机端配置文件权限为 `600`。

若 `status` 显示无障碍 `OFF`，请手动开启；脚本不会自动授予权限。

## 验证效果

进入夸克 TV 播放视频，用**实体遥控器**依次测试：暂停 → 继续播放 → 等待控制栏收起及蓝层消失 → 再暂停。确认导航、快进、选集和返回符合你的使用习惯。

默认延迟为 3 秒，从最后一次导航按键或窗口、焦点变化开始；控制栏收起可能让计时重新开始。不保证从点击播放起恰好 3 秒消失。调整延迟：

```bash
python scripts/device.py set-delay --delay 3
```

支持 1～15 秒。`set-delay` 会保存到应用私有配置中；下一次执行 `start` 会使用该命令的 `--delay` 参数，省略时为 3 秒。

## 重启、停用与卸载

电脑断开或重启不会主动结束已在手机运行的配套进程。手机重启或系统清理配套进程后，重新连接 ADB 并执行：

```bash
python scripts/device.py start --delay 3
```

本版本没有开机自启或自行恢复 ADB 身份的能力。

停止配套进程：`python scripts/device.py stop`。完整停用还需在系统设置中手动关闭该助手的无障碍开关。

卸载：`python scripts/device.py uninstall`。该命令只卸载 `local.quark.focushelper` 并删除本工具的配套文件，保留官方夸克客户端与其数据。

## 常见问题

### 安装后找不到图标

这是仅含无障碍服务的应用，没有桌面 Activity。到系统无障碍设置中查找“夸克焦点延迟助手”。

### 只安装 APK，蓝层还在

必须同时开启无障碍服务并运行配套进程。执行 `status` 检查两项状态。手机重启后要重新执行 `start`。

### 安装时提示签名冲突

不能用不同证书签名的 APK 直接覆盖已安装助手。官方 v0.0.1 与此前的同证书内部测试版可以覆盖安装；自行编译或第三方签名版本请先卸载**独立助手**再装，随后重新开启其无障碍服务。无需卸载官方夸克 TV。

### ADB 无法连接

核对无线调试主页面的连接端口，配对端口不能用于 `adb connect`。核对设备授权、防火墙、局域网互通，并先使 `adb devices` 正常显示 `device`。

### 配套进程未认证，或者 Android 版本不兼容

v0.0.1 的系统反射接口仅针对 Android 14。`adb root` 会改变 shell UID，本工具要求标准 UID 2000。也请核对 DEX 和 APK 是同一版本，并尝试重新 `start` 生成新认证配置。

### 需要诊断日志

```text
adb shell cat /data/local/tmp/quark-mode-agent.log
adb logcat -d -v brief QuarkFocusHelper:I *:S
```

多设备连接时，在 `adb` 后增加 `-s DEVICE_SERIAL`；部分 shell 需要将 `*:S` 写为 `'*:S'`。只分享上述过滤后的日志，并自行检查是否夹杂设备或个人信息。不要读取、上传或公开 `/data/local/tmp/quark-mode-config.txt`。

### 用电脑模拟按键测试正常，实体遥控器表现不同

`adb shell input keyevent` 和实体遥控器在无障碍输入过滤上的路径可能不同，请始终用实体遥控器确认最终效果。
