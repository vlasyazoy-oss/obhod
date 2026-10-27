"""Автоподбор стратегии обхода DPI: перебираем стратегии и открываем тестовые сайты через каждую.

Windows: на каждую стратегию запускается ciadpi (ByeDPI). macOS: временный sing-box с фрагментацией из
config.SINGBOX_STRATEGIES. Сайт считается открытым, если прошёл TLS и пришёл HTTP-ответ (любой код);
проверяем HTTPS, поэтому подмена страницы провайдером не засчитывается за успех.
"""
import json
import os
import subprocess
import tempfile
import time

from . import config as cfg
from .engine import CIADPI, NO_WINDOW, SING_BOX
from .osinfo import CURL, MAC, NULL

TEST_PORT = 1090


def probe(url, socks_port=None, timeout=8, doh=None):
    """doh — адрес DoH-сервера: имя резолвится через него, а не через DNS провайдера (как в рабочем режиме)."""
    args = [CURL, "-s", "-o", NULL, "-w", "%{http_code}", "-m", str(timeout), "-A", "Mozilla/5.0"]
    if doh:
        args += ["--doh-url", f"https://{doh}/dns-query"]
    if socks_port:
        args += ["--socks5" if doh else "--socks5-hostname", f"127.0.0.1:{socks_port}"]
    r = subprocess.run(args + [url], capture_output=True, creationflags=NO_WINDOW)
    code = r.stdout.decode().strip()
    return r.returncode == 0 and code not in ("", "000")


def baseline(region, log):
    """Что открывается напрямую, без обхода."""
    blocked = []
    for url in region["test_urls"]:
        ok = probe(url)
        log(f"напрямую {url}: {'открылся' if ok else 'не открылся'}")
        if not ok:
            blocked.append(url)
    return blocked


def _start_byedpi(region, strategy):
    return subprocess.Popen([CIADPI, *cfg.ciadpi_args(strategy, TEST_PORT)], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, creationflags=NO_WINDOW), None


def _start_singbox(region, strategy):
    """sing-box сам резолвит имена (через DoH региона) и режет ClientHello — curl отдаёт ему имя сайта."""
    conf = cfg.build(region, "dpi", mixed_port=TEST_PORT, singbox_dpi=strategy["singbox"], log_level="warn")
    fd, path = tempfile.mkstemp(suffix=".json", prefix="obhod-test-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(conf, f)
    proc = subprocess.Popen([SING_BOX, "run", "-c", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=NO_WINDOW)
    return proc, path


def run(region, log, urls=None, stop=lambda: False, mac=MAC):
    """Перебирает стратегии; возвращает [(стратегия, сколько сайтов открылось)] по убыванию, лучшая первой."""
    urls = urls or region["test_urls"]
    # ByeDPI сам резолвит через DNS провайдера, поэтому curl резолвит через DoH; sing-box делает это сам
    doh = region.get("doh") if region.get("resolve_dpi_via_doh") and not mac else None
    if doh:
        log(f"имена резолвлю через DoH {doh}: DNS провайдера в этом регионе подменяет адреса")
    start = _start_singbox if mac else _start_byedpi
    results = []
    for strategy in cfg.strategies(region, mac):
        if stop():
            break
        proc, tmp = start(region, strategy)
        try:
            time.sleep(1.0 if mac else 0.5)
            if proc.poll() is not None:
                log(f"✗ {strategy['name']}: движок не принял параметры")
                continue
            ok = sum(probe(u, TEST_PORT, doh=doh) for u in urls)
            log(f"{'✓' if ok == len(urls) else '·'} {strategy['name']}: {ok}/{len(urls)}")
            results.append((strategy, ok))
            if ok == len(urls):
                break  # все сайты открылись — дальше не ищем
        finally:
            proc.terminate()
            proc.wait(5)
            if tmp:
                os.remove(tmp)
    results.sort(key=lambda r: -r[1])
    return results
