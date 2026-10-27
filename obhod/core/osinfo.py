"""Платформа и то, что от неё зависит: имена файлов, шрифты, нулевое устройство, curl.

Windows — основная платформа. macOS: обход DPI делает сам sing-box (у ByeDPI нет сборки под macOS),
трея и TUN пока нет.
"""
import os
import sys

MAC = sys.platform == "darwin"
WINDOWS = os.name == "nt"

EXE = ".exe" if WINDOWS else ""
NULL = "NUL" if WINDOWS else os.devnull
CURL = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "curl.exe") if WINDOWS else "/usr/bin/curl"

# Шрифты интерфейса: Segoe UI есть только в Windows; на Mac — системный Helvetica Neue и Menlo для журнала
UI_FONT = "Helvetica Neue" if MAC else "Segoe UI"
MONO_FONT = "Menlo" if MAC else "Consolas"


def font(size, bold=False):
    if MAC:
        return (UI_FONT, size + 2, "bold") if bold else (UI_FONT, size + 2)  # в Tk на Mac те же пункты мельче
    return ("Segoe UI Semibold", size) if bold else (UI_FONT, size)


def mono(size):
    return (MONO_FONT, size + 2 if MAC else size)
