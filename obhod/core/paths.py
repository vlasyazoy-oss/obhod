"""Где что лежит. Из исходников — всё в папке проекта. Собранный exe (PyInstaller) пишет движки и настройки
в %LOCALAPPDATA%\\Obhod: рядом с exe (например, в «Загрузках») писать не стоит.
"""
import os
import sys

FROZEN = bool(getattr(sys, "frozen", False))
PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Файлы, вшитые в программу (regions.json): у exe они распакованы во временную папку _MEIPASS
RES = getattr(sys, "_MEIPASS", PROJECT)
HOME = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Obhod") if FROZEN else PROJECT
BIN = os.path.join(HOME, "bin")
DATA = os.path.join(HOME, "data")


def launch_command(*args):
    """(программа, аргументы) для запуска «Обхода» заново: автозапуск, перезапуск от администратора."""
    if FROZEN:
        return sys.executable, " ".join(args)
    exe = sys.executable
    pythonw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    return (pythonw if os.path.exists(pythonw) else exe), " ".join([f'"{os.path.join(PROJECT, "app.py")}"', *args])
