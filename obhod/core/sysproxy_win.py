"""Системный прокси Windows: HKCU\\...\\Internet Settings, прав администратора не нужно."""
import ctypes
import winreg

KEY = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
FIELDS = {"ProxyEnable": winreg.REG_DWORD, "ProxyServer": winreg.REG_SZ, "ProxyOverride": winreg.REG_SZ}
BYPASS = "localhost;127.*;10.*;172.16.*;172.17.*;172.18.*;172.19.*;172.2*;172.30.*;172.31.*;192.168.*;<local>"


def read():
    out = {}
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY) as k:
        for name in FIELDS:
            try:
                out[name] = winreg.QueryValueEx(k, name)[0]
            except FileNotFoundError:
                out[name] = None
    return out


def write(values):
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


def proxied(port):
    return {"ProxyEnable": 1, "ProxyServer": f"127.0.0.1:{port}", "ProxyOverride": BYPASS}
