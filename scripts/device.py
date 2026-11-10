#!/usr/bin/env python3
"""Install and control the Quark focus helper. Accessibility is always enabled manually."""
import argparse
import hashlib
from pathlib import Path
import re
import secrets
import shlex
import subprocess
import sys
import tempfile
import time

PACKAGE = "local.quark.focushelper"
RECEIVER = PACKAGE + "/" + PACKAGE + ".ConfigReceiver"
REMOTE_CONFIG = "/data/local/tmp/quark-mode-config.txt"
REMOTE_DEX = "/data/local/tmp/quark-binder-agent.dex"
STOP_COMMAND = 'for p in $(pidof quark_mode); do kill "$p"; done'
ROOT = Path(__file__).resolve().parents[1]


def artifact(directory, pattern):
    paths = list(directory.glob(pattern))
    if len(paths) != 1:
        raise RuntimeError(f"Expected one {pattern} in {directory}; use --artifacts.")
    path = paths[0]
    checksums = directory / "SHA256SUMS.txt"
    if not checksums.is_file():
        raise RuntimeError("Missing SHA256SUMS.txt alongside release artifacts.")
    entries = {}
    for line in checksums.read_text(encoding="utf-8").splitlines():
        digest, name = line.split(maxsplit=1)
        entries[name.lstrip("*")] = digest
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if entries.get(path.name) != digest:
        raise RuntimeError(f"Release checksum mismatch: {path.name}")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["install", "start", "stop", "status", "set-delay", "open-settings", "uninstall"])
    parser.add_argument("--adb", default="adb", help="ADB executable from Android platform-tools")
    parser.add_argument("--serial", help="Connected USB serial or wireless debugging IP:port")
    parser.add_argument("--artifacts", type=Path, default=ROOT / "releases/v0.0.1")
    parser.add_argument("--delay", type=int, default=3, choices=range(1, 16), metavar="1..15")
    args = parser.parse_args()

    def adb(*arguments, check=True):
        command = [args.adb]
        if args.serial:
            command += ["-s", args.serial]
        result = subprocess.run(command + list(arguments), capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=45)
        if check and result.returncode:
            # Never echo shell commands: configuration arguments include a local secret.
            raise RuntimeError("ADB command failed. Check adb devices, pairing/connection and device authorization.")
        return result.stdout.strip()

    def shell(*arguments, check=True):
        return adb("shell", shlex.join(arguments), check=check)

    def configure(token):
        if not re.fullmatch(r"[a-fA-F0-9]{64}", token):
            raise RuntimeError("No valid companion configuration. Run start first.")
        result = shell("am", "broadcast", "--include-stopped-packages", "--receiver-foreground",
                       "-n", RECEIVER, "--es", "token", token, "--ei", "delay_ms", str(args.delay * 1000))
        if "Broadcast completed" not in result:
            raise RuntimeError("Helper configuration broadcast was not completed.")

    if not args.serial:
        devices = adb("devices").splitlines()
        serials = [line.split()[0] for line in devices if len(line.split()) > 1 and line.split()[1] == "device"]
        if len(serials) != 1:
            raise RuntimeError("Connect exactly one authorized device, or specify --serial.")
        args.serial = serials[0]
    if shell("id", "-u") != "2000":
        raise RuntimeError("This companion requires standard ADB shell UID 2000 (not adb root).")

    if args.action in ("stop", "uninstall"):
        adb("shell", STOP_COMMAND)
        if args.action == "uninstall":
            result = adb("uninstall", PACKAGE)
            if "Success" not in result:
                raise RuntimeError("Helper uninstall did not report success.")
            shell("rm", "-f", REMOTE_CONFIG, REMOTE_DEX, "/data/local/tmp/quark-mode-agent.log")
            print("Helper uninstalled. Official Quark and its data are unchanged.")
        else:
            print("ADB companion stopped. For complete deactivation, also switch off this helper in Accessibility settings.")
        return
    if args.action == "install":
        apk = artifact(args.artifacts.resolve(), "*.apk")
        result = adb("install", "-r", str(apk))
        if "Success" not in result:
            raise RuntimeError("APK install did not report success.")
        print("Helper installed. Manually enable it in Accessibility settings, then run start.")
        return
    installed = shell("pm", "path", PACKAGE, check=False)
    if "package:" not in installed:
        raise RuntimeError("Helper is not installed. Run install first.")
    if args.action == "open-settings":
        shell("am", "start", "-a", "android.settings.ACCESSIBILITY_SETTINGS")
        print("Open Installed apps/services and enable the helper yourself.")
        return
    if args.action == "set-delay":
        configure(shell("cat", REMOTE_CONFIG))
        print(f"Delay updated: {args.delay} seconds. No reinstall required.")
        return
    if args.action == "start":
        sdk = int(shell("getprop", "ro.build.version.sdk"))
        if sdk != 34:
            raise RuntimeError("Only Android 14 / API 34 is currently supported by this companion.")
        dex = artifact(args.artifacts.resolve(), "*.dex")
        token = secrets.token_hex(32)
        adb("shell", STOP_COMMAND)
        adb("push", str(dex), REMOTE_DEX)
        with tempfile.TemporaryDirectory(prefix="quark-focus-") as temp:
            config = Path(temp) / "config.txt"
            config.write_text(token + "\n", encoding="ascii")
            adb("push", str(config), REMOTE_CONFIG)
        shell("chmod", "600", REMOTE_CONFIG)
        configure(token)
        command = ("nohup env CLASSPATH=" + REMOTE_DEX + " app_process /system/bin "
                   "--nice-name=quark_mode BinderModeAgent " + REMOTE_CONFIG +
                   " </dev/null >/data/local/tmp/quark-mode-agent.log 2>&1 &")
        adb("shell", command)
        registered = False
        for _ in range(12):
            time.sleep(0.5)
            log = shell("cat", "/data/local/tmp/quark-mode-agent.log", check=False)
            if "Helper Binder registered" in log:
                registered = True
                break
        if not registered:
            raise RuntimeError("Companion did not authenticate. Read docs/INSTALL.md troubleshooting.")
        print(f"Companion authenticated; delay={args.delay}s. PC can disconnect. Restart companion after a phone reboot.")
    pid = shell("pidof", "quark_mode", check=False)
    enabled = shell("settings", "get", "secure", "enabled_accessibility_services")
    service_on = PACKAGE + "/" in enabled
    print("ADB companion: " + ("running" if pid else "stopped"))
    print("Accessibility helper: " + ("enabled" if service_on else "OFF; enable manually in system settings"))


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
