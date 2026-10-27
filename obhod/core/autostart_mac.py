"""Автозапуск при входе в macOS: LaunchAgent ~/Library/LaunchAgents/org.obhod.app.plist (прав администратора не нужно).

macOS читает агентов из этой папки при входе пользователя; запускается «Обход» с флагом --tray
(на Mac трея пока нет — окно сразу сворачивается в Dock).
"""
import os
import plistlib

from .paths import launch_argv

NAME = "org.obhod.app"
AGENTS = os.path.expanduser("~/Library/LaunchAgents")


def plist_path():
    return os.path.join(AGENTS, NAME + ".plist")


def plist(argv):
    return {"Label": NAME, "ProgramArguments": argv, "RunAtLoad": True, "ProcessType": "Interactive"}


def command():
    return " ".join(launch_argv("--tray"))


def current():
    try:
        with open(plist_path(), "rb") as f:
            return " ".join(plistlib.load(f)["ProgramArguments"])
    except (OSError, KeyError, plistlib.InvalidFileException):
        return None


def is_enabled():
    return os.path.exists(plist_path())


def enable():
    os.makedirs(AGENTS, exist_ok=True)
    with open(plist_path(), "wb") as f:
        plistlib.dump(plist(launch_argv("--tray")), f)


def disable():
    try:
        os.remove(plist_path())
    except FileNotFoundError:
        pass


def refresh():
    """Программу перенесли (например, в «Программы») — обновить путь в агенте, если он включён."""
    if is_enabled() and current() != command():
        enable()
