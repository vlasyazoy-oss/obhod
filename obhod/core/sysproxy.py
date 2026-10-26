"""Системный прокси Windows (HKCU, без прав администратора) с резервной копией прежних значений.

Копия лежит в data/proxy_backup.json, пока прокси включён. Если приложение упало, при следующем
запуске restore() вернёт настройки, и пользователь не останется без интернета.
"""
import ctypes
import json
import os
import winreg

from .engine import DATA

KEY = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
BACKUP = os.path.join(DATA, "proxy_backup.json")
FIELDS = {"ProxyEnable": winreg.REG_DWORD, "ProxyServer": winreg.REG_SZ, "ProxyOverride": winreg.REG_SZ}
BYPASS = "localhost;127.*;10.*;172.16.*;172.17.*;172.18.*;172.19.*;172.2*;172.30.*;172.31.*;192.168.*;<local>"


def _read():
    out = {}
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY) as k:
        for name in FIELDS:
            try:
                out[name] = winreg.QueryValueEx(k, name)[0]
            except FileNotFoundError:
                out[name] = None
    return out


def _write(values):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY, 0, winreg.KEY_SET_VALUE) as k:
        for name, value in values.items():
            if value is None:
                try:
                    winreg.DeleteValue(k, name)
                except FileNotFoundError:
                    pass
            else:
                winreg.SetValueEx(k, name, 0, FIELDS[name], value)
    wininet = ctypes.windll.wininet
    wininet.InternetSetOptionW(None, 39, None, 0)  # INTERNET_OPTION_SETTINGS_CHANGED
    wininet.InternetSetOptionW(None, 37, None, 0)  # INTERNET_OPTION_REFRESH


def enable(port):
    os.makedirs(DATA, exist_ok=True)
    if not os.path.exists(BACKUP):
        with open(BACKUP, "w", encoding="utf-8") as f:
            json.dump(_read(), f)
    _write({"ProxyEnable": 1, "ProxyServer": f"127.0.0.1:{port}", "ProxyOverride": BYPASS})


def restore():
    """Вернуть настройки из копии. True, если было что возвращать."""
    if not os.path.exists(BACKUP):
        return False
    with open(BACKUP, encoding="utf-8") as f:
        _write(json.load(f))
    os.remove(BACKUP)
    return True
