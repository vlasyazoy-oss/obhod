"""Проверки с настоящими движками. Пропускаются, если bin/ пуст (py scripts/fetch_bins.py)."""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import autotest, config as cfg, keys  # noqa: E402
from core.osinfo import MAC  # noqa: E402
from core.engine import CIADPI, NO_WINDOW, SING_BOX, missing_bins  # noqa: E402

REGIONS = cfg.load_regions()
SAMPLE_KEYS = [
    "vless://b831381d-6324-4d53-ad4f-8cda48b30811@203.0.113.5:443?type=tcp&security=reality&pbk=jNXHt1yRo0vDuchQlIP6Z0ZvjT3KtzVI-T4E7RoLJS0&sid=ab12&sni=www.microsoft.com&fp=chrome&flow=xtls-rprx-vision#r",
    "vless://b831381d-6324-4d53-ad4f-8cda48b30811@cdn.example.com:443?type=ws&security=tls&path=%2Fws&host=cdn.example.com#ws",
    "trojan://secret@example.org:443?sni=example.org&type=grpc&serviceName=g#t",
    "ss://2022-blake3-aes-128-gcm:YWJjZGVmZ2hpamtsbW5vcA%3D%3D@198.51.100.2:443#ss",
    "hy2://pw@203.0.113.9:443?sni=h.example.com&obfs=salamander&obfs-password=x#h",
    "tuic://b831381d-6324-4d53-ad4f-8cda48b30811:pw@203.0.113.9:443?congestion_control=bbr&alpn=h3#u",
]


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def sing_box_check(conf):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(conf, f)
    try:
        r = subprocess.run([SING_BOX, "check", "-c", f.name], capture_output=True, creationflags=NO_WINDOW)
        return r.returncode, (r.stderr or r.stdout).decode("utf-8", "replace")
    finally:
        os.unlink(f.name)


def wait_port(port, timeout=8):
    end = time.time() + timeout
    while time.time() < end:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.2)
    return False


@unittest.skipIf(missing_bins(), "нет движков в bin/")
class SingBoxAcceptsConfigs(unittest.TestCase):
    def test_every_region_mode_and_key_type(self):
        for code, region in REGIONS.items():
            for mode in cfg.MODES:
                for tun in (False, True):
                    for uri in SAMPLE_KEYS if mode != "dpi" else [None]:
                        if mode != "vpn" and not region["dpi_supported"]:
                            continue
                        ob = keys.parse_key(uri).outbound if uri else None
                        conf = cfg.build(region, mode, ob, tun=tun)
                        with self.subTest(region=code, mode=mode, tun=tun, key=(uri or "")[:12]):
                            rc, out = sing_box_check(conf)
                            self.assertEqual(rc, 0, out)


@unittest.skipIf(missing_bins(), "нет движков в bin/")
class EndToEnd(unittest.TestCase):
    """Клиентский конфиг «Обхода» в режиме VPN → локальный тестовый shadowsocks-сервер на sing-box → интернет."""

    def setUp(self):
        self.procs = []
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        for p in self.procs:
            p.terminate()
            p.wait(5)

    def _run(self, conf, name):
        path = os.path.join(self.tmp, name + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(conf, f)
        p = subprocess.Popen([SING_BOX, "run", "-c", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=NO_WINDOW)
        self.procs.append(p)
        return p

    def test_vpn_mode_through_local_shadowsocks_server(self):
        server_port, client_port = free_port(), free_port()
        password = "YWJjZGVmZ2hpamtsbW5vcA=="  # ровно 16 байт в base64, как требует 2022-blake3-aes-128-gcm
        self._run({
            "log": {"level": "warn"},
            "inbounds": [{"type": "shadowsocks", "listen": "127.0.0.1", "listen_port": server_port,
                          "method": "2022-blake3-aes-128-gcm", "password": password}],
            "outbounds": [{"type": "direct"}],
        }, "server")
        key = keys.parse_key(f"ss://2022-blake3-aes-128-gcm:{password}@127.0.0.1:{server_port}#local")
        conf = cfg.build(REGIONS["other"], "vpn", key.outbound, mixed_port=client_port)
        # локальный тестовый сервер на 127.0.0.1: правило «приватные IP напрямую» здесь не мешает,
        # потому что до сервера ходит сам outbound, а не пользовательский трафик
        self._run(conf, "client")
        self.assertTrue(wait_port(server_port) and wait_port(client_port), "sing-box не поднялся")
        r = subprocess.run([autotest.CURL, "-s", "-m", "15", "-x", f"socks5h://127.0.0.1:{client_port}",
                            "https://www.cloudflare.com/cdn-cgi/trace"], capture_output=True, creationflags=NO_WINDOW)
        self.assertEqual(r.returncode, 0, r.stderr.decode(errors="replace"))
        self.assertIn(b"h=www.cloudflare.com", r.stdout)


    @unittest.skipIf(MAC, "ByeDPI на macOS не используется: обход DPI делает sing-box (tests/test_macos.py)")
    def test_dpi_mode_sends_listed_sites_to_byedpi_and_the_rest_direct(self):
        dpi_port, mixed_port = free_port(), free_port()
        strategy = REGIONS["ru"]["strategies"][0]
        dpi = subprocess.Popen([CIADPI, *cfg.ciadpi_args(strategy, dpi_port)], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)
        self.procs.append(dpi)
        conf = cfg.build(REGIONS["ru"], "dpi", mixed_port=mixed_port, dpi_port=dpi_port, log_level="debug")
        path = os.path.join(self.tmp, "dpi.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(conf, f)
        log_path = os.path.join(self.tmp, "dpi.log")
        log = open(log_path, "wb")
        self.addCleanup(log.close)
        self.procs.append(subprocess.Popen([SING_BOX, "run", "-c", path], stdout=log, stderr=subprocess.STDOUT,
                                           creationflags=NO_WINDOW))
        self.assertTrue(wait_port(dpi_port) and wait_port(mixed_port), "движки не поднялись")
        for url in ("https://www.youtube.com/", "https://example.com/"):
            r = subprocess.run([autotest.CURL, "-s", "-o", "NUL", "-m", "15", "-x", f"socks5h://127.0.0.1:{mixed_port}", url],
                               capture_output=True, creationflags=NO_WINDOW)
            self.assertEqual(r.returncode, 0, f"{url}: {r.stderr.decode(errors='replace')}")
        time.sleep(0.5)
        with open(log_path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        self.assertRegex(text, r"outbound/socks\[dpi\]: outbound connection to www\.youtube\.com:443")
        self.assertRegex(text, r"outbound/direct\[direct\]: outbound connection to example\.com:443")


@unittest.skipIf(MAC, "ByeDPI на macOS не используется: обход DPI делает sing-box (tests/test_macos.py)")
@unittest.skipIf(missing_bins(), "нет движков в bin/")
class NoOrphans(unittest.TestCase):
    """Быстрые переподключения подряд раньше оставляли «осиротевший» sing-box на порту со старой стратегией."""

    def test_concurrent_starts_leave_nothing_behind(self):
        import threading
        from core.engine import Engine, Log, kill_orphans
        mixed, dpi = free_port(), free_port()
        region = REGIONS["tr"]
        engine = Engine(Log())
        errors = []

        def connect(strategy):
            try:
                engine.start(cfg.build(region, "dpi", mixed_port=mixed, dpi_port=dpi), strategy, dpi)
            except Exception as e:  # второй запуск может честно не успеть — важно, чтобы не осталось сирот
                errors.append(e)
        threads = [threading.Thread(target=connect, args=(s,)) for s in region["strategies"][:3]]
        for t in threads:
            t.start()
        for t in threads:
            t.join(30)
        self.assertTrue(engine.running, f"после гонки движок должен работать: {errors}")
        engine.stop()
        self.assertEqual(kill_orphans(), 0, "после остановки не должно оставаться наших процессов")
        with socket.socket() as s:
            s.bind(("127.0.0.1", mixed))  # порт свободен

    def test_kill_orphans_touches_only_our_binaries(self):
        import shutil
        from core.engine import kill_orphans
        port = free_port()
        ours = subprocess.Popen([CIADPI, "--ip", "127.0.0.1", "--port", str(port)], creationflags=NO_WINDOW)
        foreign_dir = tempfile.mkdtemp()
        foreign_exe = os.path.join(foreign_dir, "ciadpi.exe")
        shutil.copy(CIADPI, foreign_exe)
        foreign = subprocess.Popen([foreign_exe, "--ip", "127.0.0.1", "--port", str(free_port())], creationflags=NO_WINDOW)
        try:
            time.sleep(0.5)
            self.assertEqual(kill_orphans(), 1)
            ours.wait(5)
            self.assertIsNone(foreign.poll(), "чужой ciadpi из другой папки трогать нельзя")
        finally:
            for p in (ours, foreign):
                if p.poll() is None:
                    p.kill()
                    p.wait(5)
            shutil.rmtree(foreign_dir, ignore_errors=True)


@unittest.skipIf(MAC, "ByeDPI на macOS не используется: обход DPI делает sing-box (tests/test_macos.py)")
@unittest.skipIf(missing_bins(), "нет движков в bin/")
class ByeDpiStarts(unittest.TestCase):
    def test_bound_to_network_card_still_proxies(self):
        from core.engine import physical_ip
        ip = physical_ip()
        if ip is None:
            self.skipTest("сейчас включён TUN: маршрут по умолчанию ведёт в него, адреса сетевой карты не видно")
        port = free_port()
        strategy = REGIONS["ru"]["strategies"][0]
        p = subprocess.Popen([CIADPI, *cfg.ciadpi_args(strategy, port, ip)], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)
        try:
            self.assertTrue(wait_port(port, 4))
            self.assertTrue(autotest.probe("https://www.cloudflare.com/cdn-cgi/trace", port, timeout=10))
        finally:
            p.terminate()
            p.wait(5)

    def test_every_strategy_is_accepted_and_proxies(self):
        for code, region in REGIONS.items():
            for strategy in region["strategies"]:
                port = free_port()
                p = subprocess.Popen([CIADPI, *cfg.ciadpi_args(strategy, port)], stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)
                try:
                    with self.subTest(region=code, strategy=strategy["id"]):
                        self.assertTrue(wait_port(port, 4), f"ciadpi не слушает: {p.poll()}")
                        ok = autotest.probe("https://www.cloudflare.com/cdn-cgi/trace", port, timeout=10)
                        self.assertTrue(ok, "через ByeDPI не открылся cloudflare.com")
                finally:
                    p.terminate()
                    p.wait(5)


if __name__ == "__main__":
    unittest.main()
