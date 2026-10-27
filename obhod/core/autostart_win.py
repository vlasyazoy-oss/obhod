"""Автозапуск вместе с Windows: значение в HKCU\\...\\Run (прав администратора не нужно).

Запускается pythonw.exe app.py или собранный Obhod.exe с флагом --tray: приложение стартует свёрнутым в трей.
"""
import winreg

from .paths import launch_command

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
NAME = "Obhod"


def command():
    exe, args = launch_command("--tray")
    return f'"{exe}" {args}'


def current():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            return winreg.QueryValueEx(k, NAME)[0]
    except FileNotFoundError:
        return None


def is_enabled():
    return current() is not None


def enable():
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, NAME, 0, winreg.REG_SZ, command())


def disable():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, NAME)
    except FileNotFoundError:
        pass


def refresh():
    """Папку с программой перенесли — обновить путь в автозапуске, если он включён."""
    if is_enabled() and current() != command():
        enable()
