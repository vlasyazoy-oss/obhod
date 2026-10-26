"""Проверка режима TUN снаружи: идёт ли трафик системы через Обход. Прав администратора не нужно.

    py scripts/check_tun.py           # версия из исходников (журнал в data/)
    py scripts/check_tun.py --exe     # собранный Obhod.exe (журнал в %LOCALAPPDATA%\Obhod\data)
"""
import json
import os
import re
import socket
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from core.autotest import CURL  # noqa: E402
from core.engine import LOG_FILE, NO_WINDOW  # noqa: E402

DATA = os.path.join(ROOT, "data")
if "--exe" in sys.argv:
    DATA = os.path.join(os.environ["LOCALAPPDATA"], "Obhod", "data")
    LOG_FILE = os.path.join(DATA, "obhod.log")

ok_all = True


def check(name, ok, detail=""):
    global ok_all
    ok_all &= bool(ok)
    print(f"{'✓' if ok else '✗'} {name}" + (f": {detail}" if detail else ""))


def ps(command):
    r = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, creationflags=NO_WINDOW)
    return r.stdout.decode("utf-8", "replace").strip()


def main():
    adapter = ps("(Get-NetAdapter -Name obhod -ErrorAction SilentlyContinue).Status")
    check("адаптер TUN «obhod» есть и включён", adapter == "Up", adapter or "нет адаптера")

    routes = ps("Get-NetRoute -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object InterfaceAlias -eq 'obhod' "
                "| Select-Object -ExpandProperty DestinationPrefix")
    check("маршруты всего интернета ведут в TUN", "0.0.0.0/1" in routes or "0.0.0.0/0" in routes,
          ", ".join(routes.split()) or "маршрутов нет")

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("1.1.1.1", 53))
        src = s.getsockname()[0]
    check("обычный сокет программы уходит в TUN", src.startswith("172.19."), f"исходный адрес {src}")

    try:
        ips = sorted({a[4][0] for a in socket.getaddrinfo("discord.com", 443, socket.AF_INET)})
    except OSError as e:
        ips = [f"ошибка: {e}"]
    blockpage = [ip for ip in ips if ip.startswith("195.175.254.")]  # заглушка Türk Telekom из наших тестов
    check("системный DNS отдаёт настоящий адрес discord.com", ips and not blockpage, ", ".join(ips))

    for url in ("https://discord.com/", "https://www.roblox.com/", "https://example.com/"):
        r = subprocess.run([CURL, "-s", "-o", "NUL", "-w", "%{http_code}", "-m", "15", "--noproxy", "*", url],
                           capture_output=True, creationflags=NO_WINDOW)
        code = r.stdout.decode().strip()
        check(f"{url} открывается без всяких прокси", r.returncode == 0 and code not in ("", "000"), code)

    try:
        with open(LOG_FILE, encoding="utf-8", errors="replace") as f:
            log = f.read()[-200_000:]
    except OSError:
        log = ""
    check("в журнале sing-box есть соединения из TUN", re.search(r"inbound/tun\[tun-in\]", log),
          "нужен уровень журнала info или debug")
    bound = re.findall(r"мимо TUN через ([\d.]+)", log)
    check("ByeDPI привязан к сетевой карте, мимо TUN", bound, bound[-1] if bound else "строки нет в журнале")

    try:
        with open(os.path.join(DATA, "config.json"), encoding="utf-8") as f:
            conf = json.load(f)
        check("в конфиге включён TUN", any(i["type"] == "tun" for i in conf["inbounds"]))
    except OSError:
        check("в конфиге включён TUN", False, "нет data/config.json")

    print("\nИТОГ:", "весь трафик системы идёт через Обход" if ok_all else "есть проблемы, смотрите ✗ выше")


if __name__ == "__main__":
    main()
