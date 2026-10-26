"""Готовит сборку Android-версии. Всё скачивается с официальных сайтов, системная Java не трогается.

    py scripts/setup_android.py            # инструменты + движки
    py scripts/setup_android.py --engines  # только движки (sing-box, ByeDPI, hev-socks5-tunnel)

Инструменты (≈0,8 ГБ) ставятся в %LOCALAPPDATA%\\Android:
  jdk-21     Eclipse Temurin 21 (adoptium.net)
  Sdk        Android SDK: cmdline-tools, platform-tools, platforms;android-35, build-tools;35.0.0 (dl.google.com).
             Установка через sdkmanager принимает лицензию Android SDK — запускайте, только если вы с ней согласны.
  gradle-8.10.2  Gradle (services.gradle.org)
Движки кладутся в android/app/src/main/jniLibs/<abi>/lib*.so и android/app/libs/.
"""
import io
import os
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "android", "app")
TOOLS = os.path.join(os.environ["LOCALAPPDATA"], "Android")
JDK = os.path.join(TOOLS, "jdk-21")
SDK = os.path.join(TOOLS, "Sdk")
GRADLE = os.path.join(TOOLS, "gradle-8.10.2")

SING_BOX = "1.14.4"
BYEDPI = "0.17.3"
HEV = "2.19.3"
ABIS = {"arm64-v8a": ("arm64", "aarch64"), "x86_64": ("amd64", "x86_64")}  # android-abi: (sing-box, byedpi)


def get(url):
    print(f"скачиваю {url}")
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "obhod-setup"}), timeout=600) as r:
        return r.read()


def member(archive_bytes, name, kind):
    if kind == "zip":
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as z:
            return next(z.read(n) for n in z.namelist() if os.path.basename(n) == name)
    with tarfile.open(fileobj=io.BytesIO(archive_bytes)) as t:
        m = next(m for m in t.getmembers() if os.path.basename(m.name) == name and m.isfile())
        return t.extractfile(m).read()


def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    print(f"  -> {os.path.relpath(path, ROOT) if path.startswith(ROOT) else path}")


def engines():
    for abi, (sb, bd) in ABIS.items():
        libs = os.path.join(APP, "src", "main", "jniLibs", abi)
        tgz = get(f"https://github.com/SagerNet/sing-box/releases/download/v{SING_BOX}/sing-box-{SING_BOX}-android-{sb}.tar.gz")
        save(os.path.join(libs, "libsingbox.so"), member(tgz, "sing-box", "tar"))
        tgz = get(f"https://github.com/hufrea/byedpi/releases/download/v{BYEDPI}/byedpi-{BYEDPI[2:]}-{bd}.tar.gz")
        with tarfile.open(fileobj=io.BytesIO(tgz)) as t:
            m = next(m for m in t.getmembers() if m.isfile() and os.path.basename(m.name).startswith("ciadpi"))
            save(os.path.join(libs, "libbyedpi.so"), t.extractfile(m).read())
    save(os.path.join(APP, "libs", "hev-socks5-tunnel.aar"),
         get(f"https://github.com/heiher/hev-socks5-tunnel/releases/download/{HEV}/hev-socks5-tunnel.aar"))


def unzip_to(data, dest, strip_top=True):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for info in z.infolist():
            parts = info.filename.split("/")
            rel = "/".join(parts[1:]) if strip_top else info.filename
            if not rel or info.is_dir():
                continue
            out = os.path.join(dest, rel)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, "wb") as f:
                f.write(z.read(info))


def tools():
    if not os.path.exists(os.path.join(JDK, "bin", "java.exe")):
        unzip_to(get("https://api.adoptium.net/v3/binary/latest/21/ga/windows/x64/jdk/hotspot/normal/eclipse"), JDK)
    sdkmanager = os.path.join(SDK, "cmdline-tools", "latest", "bin", "sdkmanager.bat")
    if not os.path.exists(sdkmanager):
        unzip_to(get("https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip"),
                 os.path.join(SDK, "cmdline-tools", "latest"))
    env = dict(os.environ, JAVA_HOME=JDK, ANDROID_HOME=SDK)
    packages = ["platform-tools", "platforms;android-35", "build-tools;35.0.0"]
    # «y» на каждый вопрос — это принятие лицензий Android SDK (см. docstring)
    subprocess.run([sdkmanager, "--sdk_root=" + SDK, *packages], input=b"y\n" * 20, env=env, check=True)
    if not os.path.exists(os.path.join(GRADLE, "bin", "gradle.bat")):
        unzip_to(get("https://services.gradle.org/distributions/gradle-8.10.2-bin.zip"), GRADLE)
    with open(os.path.join(ROOT, "android", "local.properties"), "w", encoding="utf-8") as f:
        f.write("sdk.dir=" + SDK.replace("\\", "\\\\") + "\n")
    print(f"\nГотово. Сборка:\n  set JAVA_HOME={JDK}\n  cd android\n  {GRADLE}\\bin\\gradle.bat assembleDebug")


if __name__ == "__main__":
    engines()
    if "--engines" not in sys.argv:
        tools()
