"""Запуск и остановка движков: ciadpi (ByeDPI) и sing-box. Логи — в кольцевой буфер и файл с ограничением размера."""
import collections
import ctypes
import json
import os
import re
import socket
import subprocess
import threading
import time

from . import config as cfg

from .paths import BIN, DATA
SING_BOX = os.path.join(BIN, "sing-box.exe")
CIADPI = os.path.join(BIN, "ciadpi.exe")
LOG_FILE = os.path.join(DATA, "obhod.log")
LOG_LIMIT = 1_000_000  # байт; у Zapret логи разрастались до 1 ГБ
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class EngineError(RuntimeError):
    pass


TUN_NET = "172.19."  # адрес TUN из config.build


def physical_ip():
    """IPv4 сетевой карты с маршрутом по умолчанию. Вызывать, пока TUN не поднят: иначе ответом будет сам TUN."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("1.1.1.1", 53))  # UDP connect ничего не отправляет, только выбирает маршрут
        ip = s.getsockname()[0]
    return None if ip.startswith(TUN_NET) else ip


def missing_bins():
    return [os.path.basename(p) for p in (SING_BOX, CIADPI) if not os.path.exists(p)]


class Log:
    def __init__(self, on_line=None):
        self.lines = collections.deque(maxlen=2000)
        self.on_line = on_line
        self._lock = threading.Lock()
        os.makedirs(DATA, exist_ok=True)

    def write(self, source, text):
        line = f"{time.strftime('%H:%M:%S')} [{source}] {text.rstrip()}"
        with self._lock:
            self.lines.append(line)
            try:
                if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > LOG_LIMIT:
                    os.replace(LOG_FILE, LOG_FILE + ".1")
                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except OSError:
                pass
        if self.on_line:
            self.on_line(line)


ANSI = re.compile(r"\x1b\[[0-9;]*m")  # цветовые коды в выводе sing-box


def _pump(proc, source, log):
    for raw in iter(proc.stdout.readline, b""):
        log.write(source, ANSI.sub("", raw.decode("utf-8", "replace")))


def _spawn(args, source, log):
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                            creationflags=NO_WINDOW, cwd=DATA)
    threading.Thread(target=_pump, args=(proc, source, log), daemon=True).start()
    return proc


def check_config(conf):
    path = os.path.join(DATA, "config.json")
    os.makedirs(DATA, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(conf, f, ensure_ascii=False, indent=2)
    r = subprocess.run([SING_BOX, "check", "-c", path], capture_output=True, creationflags=NO_WINDOW)
    if r.returncode != 0:
        raise EngineError("sing-box отклонил конфиг: " + (r.stderr or r.stdout).decode("utf-8", "replace").strip())
    return path


class Engine:
    def __init__(self, log):
        self.log = log
        self.procs = {}
        self._lock = threading.RLock()  # RLock: start() внутри вызывает stop()

    @property
    def running(self):
        return any(p.poll() is None for p in self.procs.values())

    def start(self, conf, strategy=None, dpi_port=1080):
        # Запуск и остановка только по очереди: два одновременных переподключения теряли процессы друг друга,
        # и «осиротевший» sing-box держал порт со старой стратегией
        with self._lock:
            self._start(conf, strategy, dpi_port)

    def _start(self, conf, strategy, dpi_port):
        if missing_bins():
            raise EngineError("нет движков: " + ", ".join(missing_bins()) + ". Запустите scripts/fetch_bins.py")
        was_tun = self.stop()
        killed = kill_orphans()
        if killed:
            self.log.write("obhod", f"закрыл оставшиеся от прошлого запуска движки: {killed}")
            time.sleep(0.3)
        path = check_config(conf)
        if any(o["tag"] == "dpi" for o in conf["outbounds"]):
            if not strategy:
                raise EngineError("не выбрана стратегия обхода DPI")
            conn_ip = None
            if any(i["type"] == "tun" for i in conf["inbounds"]):
                # Соединения ByeDPI не должны попасть в TUN: sing-box пересобрал бы TCP-поток, и разрезы,
                # фейки с низким TTL и OOB потерялись бы. Привязка к адресу сетевой карты выводит их мимо TUN
                # (в Windows по умолчанию строгая модель хоста: пакет уходит через карту своего адреса).
                if was_tun:
                    time.sleep(0.5)  # дать старому TUN исчезнуть из таблицы маршрутов
                conn_ip = physical_ip()
                if not conn_ip:
                    raise EngineError("не нашёл адрес сетевой карты для ByeDPI — TUN с обходом DPI не запустить")
            self.log.write("obhod", f"ByeDPI: {strategy['name']} ({' '.join(strategy['args'])})"
                           + (f", мимо TUN через {conn_ip}" if conn_ip else ""))
            self.procs["ciadpi"] = _spawn([CIADPI, *cfg.ciadpi_args(strategy, dpi_port, conn_ip)], "byedpi", self.log)
        self.procs["sing-box"] = _spawn([SING_BOX, "run", "-c", path], "sing-box", self.log)
        time.sleep(1.0)
        dead = [n for n, p in self.procs.items() if p.poll() is not None]
        if dead:
            self.stop()
            raise EngineError(f"движок завершился сразу после запуска: {', '.join(dead)} (подробности в журнале)")

    def stop(self):
        """Останавливает движки. True, если работал sing-box (с TUN его адаптер исчезает вместе с процессом)."""
        with self._lock:
            was_running = bool(self.procs.get("sing-box")) and self.procs["sing-box"].poll() is None
            for name in ("sing-box", "ciadpi"):
                p = self.procs.pop(name, None)
                if p and p.poll() is None:
                    p.terminate()
                    try:
                        p.wait(5)
                    except subprocess.TimeoutExpired:
                        p.kill()
            return was_running


def kill_orphans():
    """Закрывает наши sing-box и ciadpi, которые остались без хозяина (сбой, гонка). Ищет по точному пути к файлу
    в нашей папке bin, поэтому sing-box других программ не трогает. Возвращает число закрытых процессов."""
    k32 = ctypes.windll.kernel32
    ours = {os.path.normcase(os.path.abspath(p)) for p in (SING_BOX, CIADPI)}
    pids = (ctypes.c_uint32 * 4096)()
    size = ctypes.c_uint32()
    if not ctypes.windll.psapi.EnumProcesses(pids, ctypes.sizeof(pids), ctypes.byref(size)):
        return 0
    killed = 0
    for pid in pids[: size.value // 4]:
        if not pid or pid == os.getpid():
            continue
        h = k32.OpenProcess(0x1000 | 0x0001, False, pid)  # QUERY_LIMITED_INFORMATION | TERMINATE
        if not h:
            continue
        try:
            buf = ctypes.create_unicode_buffer(1024)
            n = ctypes.c_uint32(len(buf))
            if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)) and os.path.normcase(buf.value) in ours:
                if k32.TerminateProcess(h, 1):
                    killed += 1
        finally:
            k32.CloseHandle(h)
    return killed
