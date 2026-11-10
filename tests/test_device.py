"""Exercise release integrity and device-control boundaries without a real Android device."""
import contextlib
import hashlib
import importlib.util
import io
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("device", ROOT / "scripts/device.py")
device = importlib.util.module_from_spec(spec)
spec.loader.exec_module(device)


class FakeAdb:
    def __init__(self, sdk="34", register=True, multiple=False):
        self.sdk = sdk
        self.register = register
        self.multiple = multiple
        self.calls = []
        self.config_path = None

    def __call__(self, command, **kwargs):
        arguments = command[1:]
        if arguments[:1] == ["-s"]:
            arguments = arguments[2:]
        self.calls.append(arguments)
        if arguments == ["devices"]:
            text = "List of devices attached\ntest-device\tdevice\n"
            if self.multiple:
                text += "other-device\tdevice\n"
        elif arguments[0] == "shell":
            shell = shlex.split(arguments[1])
            if shell == ["id", "-u"]:
                text = "2000"
            elif shell[:2] == ["pm", "path"]:
                text = "package:/data/app/test/base.apk"
            elif shell == ["getprop", "ro.build.version.sdk"]:
                text = self.sdk
            elif shell[:2] == ["am", "broadcast"]:
                text = "Broadcast completed: result=0"
            elif shell[:1] == ["cat"]:
                text = "Helper Binder registered; app UID=10123" if self.register else "registration retry"
            elif shell[:1] == ["pidof"]:
                text = "12345"
            elif shell[:3] == ["settings", "get", "secure"]:
                text = device.PACKAGE + "/.FocusService"
            else:
                text = ""
        elif arguments[0] == "push":
            if arguments[-1] == device.REMOTE_CONFIG:
                self.config_path = Path(arguments[1])
                assert self.config_path.exists()
            text = "1 file pushed"
        elif arguments[0] in ("install", "uninstall"):
            text = "Success"
        else:
            text = ""
        return subprocess.CompletedProcess(command, 0, stdout=text, stderr="")


class DeviceControlTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.artifacts = Path(self.temporary.name)
        for name in ("QuarkFocusHelper-v0.0.1.apk", "quark-binder-agent.dex"):
            (self.artifacts / name).write_bytes(b"test artifact " + name.encode())
        self.write_checksums()

    def write_checksums(self):
        lines = [hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
                 for p in self.artifacts.iterdir() if p.suffix in (".apk", ".dex")]
        (self.artifacts / "SHA256SUMS.txt").write_text("".join(lines), encoding="utf-8")

    def invoke(self, fake, action, *extra):
        argv = ["device.py", action, "--artifacts", str(self.artifacts), *extra]
        output = io.StringIO()
        with patch.object(sys, "argv", argv), patch.object(device.subprocess, "run", side_effect=fake), \
                patch.object(device.time, "sleep"), contextlib.redirect_stdout(output):
            device.main()
        return output.getvalue()

    def test_start_uses_fresh_secret_removes_temp_and_never_grants_accessibility(self):
        fake = FakeAdb()
        output = self.invoke(fake, "start")
        broadcast = next(shlex.split(c[1]) for c in fake.calls
                         if c[0] == "shell" and c[1].startswith("am broadcast "))
        token = broadcast[broadcast.index("token") + 1]
        self.assertRegex(token, r"^[a-f0-9]{64}$")
        self.assertNotIn(token, output)
        self.assertFalse(fake.config_path.exists())
        self.assertIn("Companion authenticated", output)
        self.assertTrue(broadcast[-1] == "3000")
        for call in fake.calls:
            self.assertNotIn("settings put", " ".join(call))
            self.assertNotIn("settings delete", " ".join(call))

    def test_tampered_apk_is_rejected_before_install(self):
        (self.artifacts / "QuarkFocusHelper-v0.0.1.apk").write_bytes(b"modified")
        fake = FakeAdb()
        with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
            self.invoke(fake, "install")
        self.assertFalse(any(call[0] == "install" for call in fake.calls))

    def test_other_android_version_does_not_start_or_modify_configuration(self):
        fake = FakeAdb(sdk="35")
        with self.assertRaisesRegex(RuntimeError, "Only Android 14"):
            self.invoke(fake, "start")
        self.assertFalse(any(c[0] == "push" for c in fake.calls))
        self.assertFalse(any("am broadcast" in " ".join(c) for c in fake.calls))

    def test_failed_binder_registration_is_reported(self):
        fake = FakeAdb(register=False)
        with self.assertRaisesRegex(RuntimeError, "did not authenticate"):
            self.invoke(fake, "start")
        self.assertFalse(fake.config_path.exists())

    def test_multiple_connected_devices_require_selection(self):
        fake = FakeAdb(multiple=True)
        with self.assertRaisesRegex(RuntimeError, "exactly one"):
            self.invoke(fake, "start")
        self.assertEqual(fake.calls, [["devices"]])

    def test_uninstall_targets_only_helper_and_its_companion(self):
        fake = FakeAdb()
        self.invoke(fake, "uninstall")
        self.assertIn(["uninstall", device.PACKAGE], fake.calls)
        self.assertFalse(any("com.quark.yun.tv" in " ".join(c) for c in fake.calls))
        self.assertFalse(any("settings put" in " ".join(c) for c in fake.calls))


if __name__ == "__main__":
    unittest.main()
