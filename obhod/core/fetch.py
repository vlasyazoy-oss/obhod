"""Скачивание движков с официальных релизов GitHub: sing-box и ByeDPI (ciadpi). Нужно при первом запуске exe."""
import io
import os
import urllib.request
import zipfile

from .paths import BIN
from .i18n import t

SING_BOX = "1.14.4"
BYEDPI = "0.17.3"

ASSETS = [
    (f"https://github.com/SagerNet/sing-box/releases/download/v{SING_BOX}/sing-box-{SING_BOX}-windows-amd64.zip",
     "sing-box.exe"),
    (f"https://github.com/hufrea/byedpi/releases/download/v{BYEDPI}/byedpi-{BYEDPI[2:]}-x86_64-w64.zip", "ciadpi.exe"),
]


class FetchError(RuntimeError):
    pass


def fetch(log=print, force=False):
    """Скачивает недостающие движки в BIN. log(текст) — прогресс для журнала."""
    os.makedirs(BIN, exist_ok=True)
    for url, wanted in ASSETS:
        target = os.path.join(BIN, wanted)
        if os.path.exists(target) and not force:
            continue
        log(t("fetch_get", url.rsplit("/", 1)[-1]))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "obhod"})
            with urllib.request.urlopen(req, timeout=180) as r:
                data = r.read()
        except OSError as e:
            raise FetchError(t("err_fetch", wanted, e, BIN)) from e
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            name = next((n for n in z.namelist() if os.path.basename(n).lower() == wanted), None)
            if not name:
                raise FetchError(t("err_not_in_archive", wanted))
            tmp = target + ".part"
            with open(tmp, "wb") as f:
                f.write(z.read(name))
            os.replace(tmp, target)
        log(t("fetch_done", wanted))
