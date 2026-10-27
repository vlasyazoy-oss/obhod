"""Скачивание движков с официальных релизов GitHub. Windows: sing-box и ByeDPI (ciadpi). macOS: только sing-box
(обход DPI делает он сам; у ByeDPI нет сборки под macOS)."""
import io
import os
import platform
import stat
import tarfile
import urllib.request
import zipfile

from .osinfo import MAC
from .paths import BIN

SING_BOX = "1.14.4"
BYEDPI = "0.17.3"


class FetchError(RuntimeError):
    pass


def mac_arch(machine=None):
    """arm64 — Apple Silicon (M1 и новее), amd64 — Intel."""
    return "arm64" if (machine or platform.machine()).lower() in ("arm64", "aarch64") else "amd64"


def assets(mac=MAC, machine=None):
    """[(url, имя файла в архиве и в bin/)]"""
    if mac:
        a = mac_arch(machine)
        return [(f"https://github.com/SagerNet/sing-box/releases/download/v{SING_BOX}/sing-box-{SING_BOX}-darwin-{a}.tar.gz",
                 "sing-box")]
    return [
        (f"https://github.com/SagerNet/sing-box/releases/download/v{SING_BOX}/sing-box-{SING_BOX}-windows-amd64.zip",
         "sing-box.exe"),
        (f"https://github.com/hufrea/byedpi/releases/download/v{BYEDPI}/byedpi-{BYEDPI[2:]}-x86_64-w64.zip", "ciadpi.exe"),
    ]


def extract(data, url, wanted):
    """Достаёт файл wanted из zip или tar.gz по имени (без учёта папки внутри архива)."""
    if url.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            name = next((n for n in z.namelist() if os.path.basename(n).lower() == wanted), None)
            if name:
                return z.read(name)
    else:
        with tarfile.open(fileobj=io.BytesIO(data)) as t:
            member = next((m for m in t.getmembers() if m.isfile() and os.path.basename(m.name) == wanted), None)
            if member:
                return t.extractfile(member).read()
    raise FetchError(f"в архиве нет {wanted}")


def fetch(log=print, force=False):
    """Скачивает недостающие движки в BIN. log(текст) — прогресс для журнала."""
    os.makedirs(BIN, exist_ok=True)
    for url, wanted in assets():
        target = os.path.join(BIN, wanted)
        if os.path.exists(target) and not force:
            continue
        log(f"скачиваю {url.rsplit('/', 1)[-1]}…")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "obhod"})
            with urllib.request.urlopen(req, timeout=180) as r:
                data = r.read()
        except OSError as e:
            raise FetchError(f"не удалось скачать {wanted}: {e}. Если GitHub заблокирован, подключите обход "
                             f"другим способом или положите файл в {BIN} вручную") from e
        tmp = target + ".part"
        with open(tmp, "wb") as f:
            f.write(extract(data, url, wanted))
        if not url.endswith(".zip"):
            os.chmod(tmp, os.stat(tmp).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)  # право на запуск
        os.replace(tmp, target)
        log(f"готово: {wanted}")
