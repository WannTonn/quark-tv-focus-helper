#!/usr/bin/env python3
"""Build the original helper sources and Binder companion (Python 3.10+, JDK 17+)."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(arguments, sensitive=False):
    result = subprocess.run([str(a) for a in arguments], stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    if sensitive:
        # Signer output may contain local paths. Never echo the signing command/password.
        if result.returncode:
            raise RuntimeError("Signing failed. Check the private keystore, alias and environment passwords.")
    else:
        print(result.stdout, end="", flush=True)
        if result.returncode:
            raise RuntimeError(f"Build tool failed (exit {result.returncode}).")
    return result.stdout


def toolchain(directory):
    directory.mkdir(parents=True, exist_ok=True)
    locked = json.loads((ROOT / "tools.lock.json").read_text(encoding="utf-8"))
    for name, entry in locked.items():
        target = directory / name
        if target.exists():
            if sha256(target) != entry["sha256"]:
                raise RuntimeError(f"Tool checksum mismatch: {name}")
            continue
        print(f"Downloading {name} from its upstream release...", flush=True)
        with tempfile.TemporaryDirectory(prefix="quark-tool-") as temp:
            download = Path(temp) / "download"
            request = urllib.request.Request(entry["url"], headers={"User-Agent": "QuarkFocusHelper-build/0.0.1"})
            with urllib.request.urlopen(request, timeout=60) as response, download.open("wb") as output:
                shutil.copyfileobj(response, output)
            expected = entry.get("archiveSha256", entry["sha256"])
            if sha256(download) != expected:
                raise RuntimeError(f"Download checksum mismatch: {name}")
            if "member" in entry:
                with ZipFile(download) as archive:
                    target.write_bytes(archive.read(entry["member"]))
            else:
                shutil.copyfile(download, target)
            if sha256(target) != entry["sha256"]:
                raise RuntimeError(f"Extracted tool checksum mismatch: {name}")
    return {name: directory / name for name in locked}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--java", default="java", help="JDK 17+ java executable")
    parser.add_argument("--tools-dir", type=Path, default=ROOT / ".tools")
    parser.add_argument("--keystore", type=Path, help="Private release signing keystore; never committed")
    parser.add_argument("--alias", help="Private keystore alias")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    if bool(args.keystore) != bool(args.alias):
        parser.error("--keystore and --alias must be supplied together")
    if args.keystore and not os.environ.get("QFH_STORE_PASSWORD"):
        parser.error("Set QFH_STORE_PASSWORD in your environment for release signing")
    version = json.loads((ROOT / "version.json").read_text(encoding="utf-8"))
    java = [args.java, "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-Dstderr.encoding=UTF-8"]
    tools = toolchain(args.tools_dir.resolve())
    out = (args.out or ROOT / "build" / "dist").resolve()
    out.mkdir(parents=True, exist_ok=True)
    # A fresh temporary project prevents stale anonymous classes from entering the APK.
    (ROOT / "build").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="compile-", dir=ROOT / "build") as temporary:
        stage = Path(temporary)
        project = stage / "project"
        project.mkdir()
        shutil.copyfile(ROOT / "app/src/main/AndroidManifest.xml", project / "AndroidManifest.xml")
        shutil.copytree(ROOT / "app/src/main/res", project / "res")
        metadata = f"""version: 2.12.1
apkFileName: QuarkFocusHelper.apk
usesFramework:
  ids:
  - 1
sdkInfo:
  minSdkVersion: {version['minSdk']}
  targetSdkVersion: {version['targetSdk']}
versionInfo:
  versionCode: {version['code']}
  versionName: '{version['name']}'
doNotCompress:
- arsc
"""
        (project / "apktool.yml").write_text(metadata, encoding="utf-8")
        for module in ("app", "companion"):
            classes = stage / (module + "-classes")
            dex = stage / (module + "-dex")
            classes.mkdir()
            dex.mkdir()
            sources = sorted((ROOT / module / "src/main/java").rglob("*.java"))
            run([*java, ROOT / "scripts/CompileSources.java", tools["android34.jar"], classes, *sources])
            run([*java, "-cp", tools["r8.jar"], "com.android.tools.r8.D8", "--release",
                 "--min-api", str(version["minSdk"]), "--lib", tools["android34.jar"],
                 "--output", dex, *sorted(classes.rglob("*.class"))])
        shutil.copyfile(stage / "app-dex/classes.dex", project / "classes.dex")
        unsigned = stage / "QuarkFocusHelper-unsigned.apk"
        run([*java, "-jar", tools["apktool.jar"], "b", project, "-o", unsigned])
        signed = stage / "signed"
        command = [*java, "-jar", tools["uber-apk-signer.jar"], "-a", unsigned, "-o", signed]
        if args.keystore:
            command += ["--ks", args.keystore.resolve(), "--ksAlias", args.alias,
                        "--ksPass", os.environ["QFH_STORE_PASSWORD"], "--ksKeyPass",
                        os.environ.get("QFH_KEY_PASSWORD", os.environ["QFH_STORE_PASSWORD"])]
        run(command, sensitive=bool(args.keystore))
        candidates = list(signed.glob("*-signed.apk"))
        if len(candidates) != 1:
            raise RuntimeError("Expected one signed APK")
        apk = out / f"QuarkFocusHelper-v{version['name']}.apk"
        shutil.copyfile(candidates[0], apk)
        companion = out / "quark-binder-agent.dex"
        shutil.copyfile(stage / "companion-dex/classes.dex", companion)
        run([*java, "-jar", tools["uber-apk-signer.jar"], "-a", apk, "--onlyVerify"])
        (out / "SHA256SUMS.txt").write_text(
            "".join(f"{sha256(path)}  {path.name}\n" for path in (apk, companion)), encoding="utf-8")
        print(f"Built v{version['name']}: {apk.name} and {companion.name}")
        if not args.keystore:
            print("Development signature only. Use a private keystore for your own published releases.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Build failed: {error}", file=sys.stderr)
        sys.exit(1)
