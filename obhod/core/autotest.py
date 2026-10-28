"""Автоподбор стратегии ByeDPI: запускаем ciadpi с каждой стратегией региона и открываем тестовые сайты через него.

Сайт считается открытым, если через SOCKS прошёл TLS и пришёл HTTP-ответ (любой код). Проверяем HTTPS,
поэтому подмена страницы провайдером не засчитывается за успех.
"""
import os
import subprocess
import time

from . import config as cfg
from .engine import CIADPI, NO_WINDOW
from . import i18n
from .i18n import t

CURL = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "curl.exe")
TEST_PORT = 1090


def probe(url, socks_port=None, timeout=8, doh=None):
    """doh — адрес DoH-сервера: имя резолвится через него, а не через DNS провайдера (как в рабочем режиме)."""
    args = [CURL, "-s", "-o", "NUL", "-w", "%{http_code}", "-m", str(timeout), "-A", "Mozilla/5.0"]
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
        log(t("test_direct", url, t("test_opened" if ok else "test_failed")))
        if not ok:
            blocked.append(url)
    return blocked


def run(region, log, urls=None, stop=lambda: False):
    """Перебирает стратегии; возвращает [(стратегия, сколько сайтов открылось)] по убыванию, лучшая первой."""
    urls = urls or region["test_urls"]
    doh = region.get("doh") if region.get("resolve_dpi_via_doh") else None
    if doh:
        log(t("test_doh", doh))
    results = []
    for strategy in region["strategies"]:
        if stop():
            break
        proc = subprocess.Popen([CIADPI, *cfg.ciadpi_args(strategy, TEST_PORT)], stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)
        try:
            time.sleep(0.5)
            if proc.poll() is not None:
                log(f"✗ {i18n.strategy(strategy['name'])}: {t('test_bad_args')}")
                continue
            ok = sum(probe(u, TEST_PORT, doh=doh) for u in urls)
            log(f"{'✓' if ok == len(urls) else '·'} {i18n.strategy(strategy['name'])}: {ok}/{len(urls)}")
            results.append((strategy, ok))
            if ok == len(urls):
                break  # все сайты открылись — дальше не ищем
        finally:
            proc.terminate()
            proc.wait(5)
    results.sort(key=lambda r: -r[1])
    return results
