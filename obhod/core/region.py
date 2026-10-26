"""Определение региона без сети: часовой пояс Windows, затем язык системы. По IP — только по нажатию."""
import ctypes
import subprocess
import urllib.request

from .engine import NO_WINDOW

TIMEZONES = {
    "Russian Standard Time": "ru", "Kaliningrad Standard Time": "ru", "Russia Time Zone 3": "ru",
    "Ekaterinburg Standard Time": "ru", "Omsk Standard Time": "ru", "N. Central Asia Standard Time": "ru",
    "North Asia Standard Time": "ru", "North Asia East Standard Time": "ru", "Yakutsk Standard Time": "ru",
    "Vladivostok Standard Time": "ru", "Magadan Standard Time": "ru", "Russia Time Zone 10": "ru",
    "Russia Time Zone 11": "ru", "Astrakhan Standard Time": "ru", "Saratov Standard Time": "ru",
    "Volgograd Standard Time": "ru", "Altai Standard Time": "ru", "Tomsk Standard Time": "ru",
    "Transbaikal Standard Time": "ru", "Sakhalin Standard Time": "ru",
    "Turkey Standard Time": "tr",
    "Iran Standard Time": "ir",
    "China Standard Time": "cn",
}
LANGS = {"ru": "ru", "tr": "tr", "fa": "ir", "zh": "cn"}


def _timezone():
    try:
        r = subprocess.run(["tzutil", "/g"], capture_output=True, timeout=5, creationflags=NO_WINDOW)
        return r.stdout.decode(errors="replace").strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _language():
    buf = ctypes.create_unicode_buffer(85)
    ctypes.windll.kernel32.GetUserDefaultLocaleName(buf, 85)
    return buf.value  # например ru-RU


def detect_offline():
    """(код региона, откуда узнали)"""
    tz = _timezone()
    if tz in TIMEZONES:
        return TIMEZONES[tz], f"часовой пояс {tz}"
    lang = _language()
    code = LANGS.get(lang.split("-")[0].lower())
    if code:
        return code, f"язык системы {lang}"
    return "other", "не удалось определить"


def detect_online(timeout=6):
    """По IP через cloudflare.com/cdn-cgi/trace. Только по явному нажатию пользователя."""
    with urllib.request.urlopen("https://www.cloudflare.com/cdn-cgi/trace", timeout=timeout) as r:
        trace = dict(line.split("=", 1) for line in r.read().decode().splitlines() if "=" in line)
    country = trace.get("loc", "").lower()
    return (country if country in ("ru", "tr", "ir", "cn") else "other"), f"IP-адрес, страна {country.upper() or '?'}"
