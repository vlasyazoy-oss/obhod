"""Определение региона без сети: часовой пояс, затем язык системы. По IP — только по нажатию.

Windows отдаёт свои имена поясов (tzutil), macOS — имена IANA (Europe/Istanbul) через /etc/localtime.
"""
import ctypes
import locale
import os
import subprocess
import urllib.request

from .engine import NO_WINDOW
from .osinfo import MAC

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
# Те же страны в именах IANA (macOS, Linux, Android)
IANA = {
    "Europe/Istanbul": "tr", "Asia/Istanbul": "tr", "Turkey": "tr",
    "Asia/Tehran": "ir", "Iran": "ir",
    "Asia/Shanghai": "cn", "Asia/Urumqi": "cn", "Asia/Chongqing": "cn", "Asia/Harbin": "cn", "PRC": "cn",
    **{z: "ru" for z in (
        "Europe/Moscow", "Europe/Kaliningrad", "Europe/Samara", "Europe/Volgograd", "Europe/Saratov",
        "Europe/Ulyanovsk", "Europe/Astrakhan", "Europe/Kirov", "Asia/Yekaterinburg", "Asia/Omsk",
        "Asia/Novosibirsk", "Asia/Barnaul", "Asia/Tomsk", "Asia/Novokuznetsk", "Asia/Krasnoyarsk", "Asia/Irkutsk",
        "Asia/Chita", "Asia/Yakutsk", "Asia/Khandyga", "Asia/Vladivostok", "Asia/Ust-Nera", "Asia/Magadan",
        "Asia/Sakhalin", "Asia/Srednekolymsk", "Asia/Kamchatka", "Asia/Anadyr", "W-SU")},
}
LANGS = {"ru": "ru", "tr": "tr", "fa": "ir", "zh": "cn"}


def iana_from_link(target):
    """/var/db/timezone/zoneinfo/Europe/Istanbul → Europe/Istanbul"""
    return target.split("zoneinfo/", 1)[1] if "zoneinfo/" in target else ""


def _timezone():
    if MAC:
        try:
            return iana_from_link(os.readlink("/etc/localtime"))
        except OSError:
            return ""
    try:
        r = subprocess.run(["tzutil", "/g"], capture_output=True, timeout=5, creationflags=NO_WINDOW)
        return r.stdout.decode(errors="replace").strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _language():
    if MAC:
        try:
            r = subprocess.run(["defaults", "read", "-g", "AppleLocale"], capture_output=True, text=True, timeout=5)
            if r.stdout.strip():
                return r.stdout.strip().replace("_", "-")  # ru_RU → ru-RU
        except (OSError, subprocess.SubprocessError):
            pass
        return (locale.getlocale()[0] or "").replace("_", "-")
    buf = ctypes.create_unicode_buffer(85)
    ctypes.windll.kernel32.GetUserDefaultLocaleName(buf, 85)
    return buf.value  # например ru-RU


def from_timezone(tz):
    return TIMEZONES.get(tz) or IANA.get(tz)


def detect_offline():
    """(код региона, откуда узнали)"""
    tz = _timezone()
    code = from_timezone(tz)
    if code:
        return code, f"часовой пояс {tz}"
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
