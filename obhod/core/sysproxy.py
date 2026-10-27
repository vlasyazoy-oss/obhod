"""Системный прокси с резервной копией прежних значений: Windows (реестр) или macOS (networksetup).

Копия лежит в data/proxy_backup.json, пока прокси включён. Если приложение упало, при следующем
запуске restore() вернёт настройки, и пользователь не останется без интернета.
"""
import json
import os

from .engine import DATA
from .osinfo import MAC

if MAC:
    from . import sysproxy_mac as backend
else:
    from . import sysproxy_win as backend

BACKUP = os.path.join(DATA, "proxy_backup.json")


def enable(port):
    os.makedirs(DATA, exist_ok=True)
    if not os.path.exists(BACKUP):
        with open(BACKUP, "w", encoding="utf-8") as f:
            json.dump(backend.read(), f)
    backend.write(backend.proxied(port))


def restore():
    """Вернуть настройки из копии. True, если было что возвращать."""
    if not os.path.exists(BACKUP):
        return False
    with open(BACKUP, encoding="utf-8") as f:
        backend.write(json.load(f))
    os.remove(BACKUP)
    return True
