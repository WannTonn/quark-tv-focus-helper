# 从源码构建

## 环境

- Python 3.10+，仅使用标准库。
- 完整 JDK 17 或更高版本，必须带 `jdk.compiler`；单独 JRE 不够。
- 首次构建需要联网下载工具，后续可使用已经通过校验的工具缓存。

本项目直接编译自有 Java 源码并打包资源，不需要原版夸克 APK，也不需要反编译夸克。Apktool 在此只负责将自有清单、资源和生成的 DEX 打成 APK。

## 开发构建

```bash
python scripts/build.py
```

Java 不在 PATH 时：

```text
python scripts/build.py --java "JDK目录/bin/java"
```

Windows 可指定 `java.exe`。构建工具默认缓存到 `.tools/`；可以使用 `--tools-dir "工具缓存目录"`。工具文件名、版本、下载地址及 SHA-256 固定在 `tools.lock.json`，已有文件和新下载文件都会校验。下载的 Android SDK 只提取编译需要的 `android.jar`。

默认输出：

```text
build/dist/QuarkFocusHelper-v0.0.1.apk
build/dist/quark-binder-agent.dex
build/dist/SHA256SUMS.txt
```

构建时自动创建临时工作目录并清理，不复用旧 `.class`。Android 资源表不压缩，并由签名工具对齐、签名和校验。未指定私有证书时使用签名工具提供的开发证书，**只适合本地测试**。

开发构建可配合以下命令测试：

```bash
python scripts/device.py install --artifacts build/dist
python scripts/device.py start --artifacts build/dist --delay 3
```

## 自己的发行签名

请使用自己保管的 keystore，通过环境变量提供密码，不将私钥或密码提交到仓库。脚本接受 `QFH_STORE_PASSWORD`；如果密钥密码不同，还需设置 `QFH_KEY_PASSWORD`。

PowerShell 示例会交互读取密码，不把它写入命令历史：

```powershell
$securePassword = Read-Host 'Keystore password' -AsSecureString
$credential = [PSCredential]::new('signing', $securePassword)
$env:QFH_STORE_PASSWORD = $credential.GetNetworkCredential().Password
try {
    python scripts/build.py --keystore '私有目录/release.p12' --alias '你的别名'
} finally {
    Remove-Item Env:QFH_STORE_PASSWORD
    $credential = $null
    $securePassword = $null
}
```

签名工具运行时会收到密码参数；不要在不可信电脑上构建，也不要上传进程信息或构建调试记录。构建脚本不会回显包含密码的命令或签名阶段输出。

官方 v0.0.1 发行证书延续此前内部测试证书，支持同证书覆盖安装。仓库不附带这份证书私钥。自己的构建使用自己的证书，因此不能直接覆盖官方签名的助手。

## 版本与发布

修改 `version.json` 的版本名和单调递增的 `code`。v0.0.1 的 `code=5` 是为了兼容已有内部测试版，并非版本名笔误。当前 `minSdk=34`、`targetSdk=34`。

发版时应完成：源码构建、APK 签名/对齐检查、包名与权限检查、实体遥控器回归，并为 APK 和配套 DEX 生成 SHA-256。将源码归档、使用说明、安装工具及相同版本的 APK/DEX 一起提供。不要将 `.tools/`、`build/`、私有签名文件、设备认证文件或网盘 APK 放入源码归档。

本次 v0.0.1 是用户已确认可用实现的首次开源封装；重建包尚未重新安装到设备，不能把静态检查表述为新 APK 的实机回归。

## 上游工具

设备工具的离线检查可通过 `python -m unittest discover -s tests -v` 运行，覆盖发布文件被修改、多设备歧义、系统版本限制、Binder 注册失败和不自动授予无障碍权限等情况。这些检查模拟 ADB 返回结果，不连接真实设备，不能代替实体遥控器回归。

| 工具 | 版本 | 上游 |
| --- | --- | --- |
| Apktool | 2.12.1 | https://github.com/iBotPeaches/Apktool |
| D8 / R8（r8lib） | 9.5.29 | https://r8.googlesource.com/r8/ |
| uber-apk-signer | 1.3.0 | https://github.com/patrickfav/uber-apk-signer |
| Android SDK Platform | API 34 / revision 2 / extension 7 | https://developer.android.com/tools |

这些工具及 SDK 受各自许可证/条款约束，不作为本仓库源码的一部分分发。
