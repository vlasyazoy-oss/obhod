"""Где что лежит. Из исходников — всё в папке проекта. Собранная программа (PyInstaller) пишет движки
и настройки в папку пользователя: %LOCALAPPDATA%\\Obhod на Windows, ~/Library/Application Support/Obhod
на macOS. Рядом с exe или внутри .app писать не стоит.
"""
import os
import sys

from .osinfo import MAC

FROZEN = bool(getattr(sys, "frozen", False))
PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Файлы, вшитые в программу (regions.json): у собранной программы они распакованы во временную папку _MEIPASS
RES = getattr(sys, "_MEIPASS", PROJECT)


def _user_home():
    if MAC:
        return os.path.expanduser("~/Library/Application Support/Obhod")
    return os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Obhod")


HOME = _user_home() if FROZEN else PROJECT
BIN = os.path.join(HOME, "bin")
DATA = os.path.join(HOME, "data")


def launch_argv(*args):
    """Команда для запуска «Обхода» заново (автозапуск, перезапуск от администратора) — списком аргументов."""
    if FROZEN:
        return [sys.executable, *args]
    exe = sys.executable
    pythonw = os.path.join(os.path.dirname(exe), "pythonw.exe")  # Windows: без консольного окна
    return [pythonw if os.path.exists(pythonw) else exe, os.path.join(PROJECT, "app.py"), *args]


def launch_command(*args):
    """(программа, аргументы одной строкой) — так ждут ShellExecute и реестр Windows."""
    argv = launch_argv(*args)
    return argv[0], " ".join(f'"{a}"' if " " in a or a.endswith(".py") else a for a in argv[1:])
