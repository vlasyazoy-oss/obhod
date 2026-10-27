"""macOS-версия: всё, что можно проверить вне Mac, плюс живые проверки, которые работают и на Mac.

Маршрутизация Mac-версии (обход DPI силами sing-box) проверяется настоящим sing-box и живой сетью —
на Windows это sing-box.exe, на Mac — sing-box из bin/. Остальное (networksetup, LaunchAgent, ps) —
на заготовленных ответах системы.
"""
import io
import json
import os
import plistlib
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import autostart_mac, autotest, config as cfg, fetch, region as reg, sysproxy_mac  # noqa: E402
from core.engine import NO_WINDOW, SING_BOX, missing_bins, orphan_pids  # noqa: E402

REGIONS = cfg.load_regions()
SB = cfg.SINGBOX_STRATEGIES[0]["singbox"]


class SingBoxDpiConfig(unittest.TestCase):
    def test_no_byedpi_outbound_and_fragment_before_direct(self):
        c = cfg.build(REGIONS["tr"], "dpi", singbox_dpi=SB)
        self.assertNotIn("dpi", [o["tag"] for o in c["outbounds"]], "на Mac ByeDPI нет")
        rules = c["route"]["rules"]
        i = next(i for i, r in enumerate(rules) if r.get("action") == "route-options")
        self.assertTrue(rules[i]["tls_record_fragment"])
        self.assertEqual(rules[i + 1].get("outbound"), "direct", "после фрагментации — выход напрямую")
        resolve = next(i for i, r in enumerate(rules) if r.get("action") == "resolve")
        self.assertLess(resolve, i, "в Турции адрес — через DoH, до фрагментации")

    def test_hybrid_and_dpi_all(self):
        proxy = {"type": "trojan", "server": "198.51.100.1", "server_port": 443, "password": "p",
                 "tls": {"enabled": True, "server_name": "a.example"}}
        c = cfg.build(REGIONS["ru"], "hybrid", proxy, singbox_dpi=SB)
        self.assertIn("proxy", [o["tag"] for o in c["outbounds"]])
        c = cfg.build(REGIONS["ru"], "dpi", singbox_dpi=SB, dpi_all=True)
        self.assertIn({"network": "tcp", "action": "route-options", **SB}, c["route"]["rules"])

    def test_platform_strategy_lists(self):
        self.assertEqual(cfg.strategies(REGIONS["tr"], mac=True), cfg.SINGBOX_STRATEGIES)
        self.assertEqual(cfg.strategies(REGIONS["tr"], mac=False), REGIONS["tr"]["strategies"])
        self.assertEqual(cfg.strategies(REGIONS["cn"], mac=True), [], "в Китае обход DPI не помогает")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@unittest.skipIf(missing_bins(), "нет sing-box в bin/")
class SingBoxDpiLive(unittest.TestCase):
    def test_singbox_accepts_every_mac_config(self):
        for code, region in REGIONS.items():
            for strategy in cfg.SINGBOX_STRATEGIES:
                for mode in ("dpi", "hybrid"):
                    if not region["dpi_supported"]:
                        continue
                    ob = {"type": "trojan", "server": "198.51.100.1", "server_port": 443, "password": "p"}
                    c = cfg.build(region, mode, ob, singbox_dpi=strategy["singbox"])
                    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
                        json.dump(c, f)
                    try:
                        r = subprocess.run([SING_BOX, "check", "-c", f.name], capture_output=True, creationflags=NO_WINDOW)
                        with self.subTest(region=code, mode=mode, strategy=strategy["id"]):
                            self.assertEqual(r.returncode, 0, (r.stderr or r.stdout).decode(errors="replace"))
                    finally:
                        os.unlink(f.name)

    def test_blocked_sites_open_through_mac_routing(self):
        """Та же маршрутизация, что запустит Mac-версия: sing-box без ByeDPI открывает тестовые сайты региона."""
        code, _ = reg.detect_offline()
        region = REGIONS[code]
        if not region["dpi_supported"] or not region["test_urls"]:
            self.skipTest(f"регион {code}: обход DPI не применяется")
        port = free_port()
        c = cfg.build(region, "dpi", mixed_port=port, singbox_dpi=SB, log_level="warn")
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(c, f)
        p = subprocess.Popen([SING_BOX, "run", "-c", f.name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=NO_WINDOW)
        try:
            time.sleep(1.5)
            for url in region["test_urls"]:
                with self.subTest(url=url):
                    self.assertTrue(autotest.probe(url, port, timeout=15), f"{url} не открылся через sing-box")
        finally:
            p.terminate()
            p.wait(5)
            os.unlink(f.name)

    def test_mac_autotest_picks_record_fragment(self):
        code, _ = reg.detect_offline()
        region = REGIONS[code]
        if not region["dpi_supported"] or not region["test_urls"]:
            self.skipTest(f"регион {code}: обход DPI не применяется")
        lines = []
        results = autotest.run(region, lines.append, mac=True)
        self.assertTrue(results and results[0][1] > 0, lines)
        self.assertEqual(results[0][0]["id"], "sb-tlsrec", lines)


class NetworkSetup(unittest.TestCase):
    """Ответы networksetup записаны в том виде, в каком их печатает macOS."""

    LIST = ("An asterisk (*) denotes that a network service is disabled.\n"
            "Wi-Fi\n*Bluetooth PAN\nThunderbolt Bridge\n")
    PROXY_OFF = "Enabled: No\nServer: \nPort: 0\nAuthenticated Proxy Enabled: 0\n"
    PROXY_ON = "Enabled: Yes\nServer: 10.0.0.5\nPort: 3128\nAuthenticated Proxy Enabled: 0\n"

    def fake(self, failing=()):
        calls = []

        def run(args):
            calls.append(args)
            if args[0] == "-listallnetworkservices":
                return 0, self.LIST
            if args[0] == "-getwebproxy":
                return 0, self.PROXY_ON if args[1] == "Wi-Fi" else self.PROXY_OFF
            if args[0] == "-getsecurewebproxy":
                return 0, self.PROXY_OFF
            if args[0] == "-getproxybypassdomains":
                return 0, "*.local\n169.254/16\n" if args[1] == "Wi-Fi" else "There aren't any bypass domains set on Thunderbolt Bridge.\n"
            return (1, "You must run this tool as root.") if args[0] in failing else (0, "")
        return run, calls

    def test_services_skip_header_and_disabled(self):
        run, _ = self.fake()
        self.assertEqual(sysproxy_mac.services(run), ["Wi-Fi", "Thunderbolt Bridge"])

    def test_read_parses_current_state(self):
        run, _ = self.fake()
        state = sysproxy_mac.read(run)
        self.assertEqual(state["Wi-Fi"]["webproxy"], {"enabled": True, "server": "10.0.0.5", "port": 3128})
        self.assertFalse(state["Wi-Fi"]["securewebproxy"]["enabled"])
        self.assertEqual(state["Wi-Fi"]["bypass"], ["*.local", "169.254/16"])
        self.assertEqual(state["Thunderbolt Bridge"]["bypass"], [])

    def test_enable_then_restore_commands(self):
        run, calls = self.fake()
        before = sysproxy_mac.read(run)
        on = sysproxy_mac.commands(sysproxy_mac.proxied(2080, run))
        self.assertIn(["-setwebproxy", "Wi-Fi", "127.0.0.1", "2080"], on)
        self.assertIn(["-setsecurewebproxystate", "Thunderbolt Bridge", "on"], on)
        back = sysproxy_mac.commands(before)
        self.assertIn(["-setwebproxy", "Wi-Fi", "10.0.0.5", "3128"], back, "прежний прокси возвращается")
        self.assertIn(["-setsecurewebproxystate", "Wi-Fi", "off"], back)
        self.assertIn(["-setproxybypassdomains", "Thunderbolt Bridge", "Empty"], back, "пустой список — словом Empty")

    def test_write_asks_for_password_only_for_refused_commands(self):
        run, _ = self.fake(failing={"-setwebproxy"})
        elevated = []
        sysproxy_mac.write(sysproxy_mac.proxied(2080, run), run, elevate=elevated.extend)
        self.assertTrue(elevated and all(c[0] == "-setwebproxy" for c in elevated))
        run, _ = self.fake()
        elevated = []
        sysproxy_mac.write(sysproxy_mac.proxied(2080, run), run, elevate=elevated.extend)
        self.assertEqual(elevated, [], "если хватило прав, пароль не спрашиваем")


class LaunchAgent(unittest.TestCase):
    def test_enable_disable_and_refresh(self):
        with tempfile.TemporaryDirectory() as d:
            old = autostart_mac.AGENTS
            autostart_mac.AGENTS = d
            try:
                self.assertFalse(autostart_mac.is_enabled())
                autostart_mac.enable()
                with open(autostart_mac.plist_path(), "rb") as f:
                    pl = plistlib.load(f)
                self.assertEqual(pl["Label"], "org.obhod.app")
                self.assertTrue(pl["RunAtLoad"])
                self.assertEqual(pl["ProgramArguments"][-1], "--tray")
                self.assertEqual(autostart_mac.current(), autostart_mac.command())
                with open(autostart_mac.plist_path(), "wb") as f:  # программу перенесли
                    plistlib.dump(autostart_mac.plist(["/old/place/Obhod", "--tray"]), f)
                autostart_mac.refresh()
                self.assertEqual(autostart_mac.current(), autostart_mac.command())
                autostart_mac.disable()
                self.assertFalse(autostart_mac.is_enabled())
            finally:
                autostart_mac.AGENTS = old


class Region(unittest.TestCase):
    def test_iana_names(self):
        self.assertEqual(reg.iana_from_link("/var/db/timezone/zoneinfo/Europe/Istanbul"), "Europe/Istanbul")
        self.assertEqual(reg.from_timezone("Europe/Istanbul"), "tr")
        self.assertEqual(reg.from_timezone("Asia/Novosibirsk"), "ru")
        self.assertEqual(reg.from_timezone("Asia/Tehran"), "ir")
        self.assertEqual(reg.from_timezone("Asia/Shanghai"), "cn")
        self.assertEqual(reg.from_timezone("Turkey Standard Time"), "tr", "имена Windows по-прежнему работают")
        self.assertIsNone(reg.from_timezone("Europe/Berlin"))


class Orphans(unittest.TestCase):
    def test_ps_output_matches_only_our_paths(self):
        ours = {"/Users/me/Library/Application Support/Obhod/bin/sing-box"}
        out = ("  101 /sbin/launchd\n"
               "  202 /Users/me/Library/Application Support/Obhod/bin/sing-box\n"
               "  303 /Applications/OtherVPN.app/Contents/MacOS/sing-box\n")
        if os.name == "nt":  # os.path.abspath на Windows приписал бы диск — сравниваем как есть
            ours = {os.path.abspath(p) for p in ours}
        self.assertEqual(orphan_pids(out, ours), [202])


class Downloads(unittest.TestCase):
    def test_asset_urls(self):
        self.assertTrue(fetch.assets(mac=True, machine="arm64")[0][0].endswith("darwin-arm64.tar.gz"))
        self.assertTrue(fetch.assets(mac=True, machine="x86_64")[0][0].endswith("darwin-amd64.tar.gz"))
        self.assertEqual([w for _, w in fetch.assets(mac=True)], ["sing-box"], "на Mac ByeDPI не скачиваем")

    def test_extract_from_tar_gz_with_folder(self):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as t:
            data = b"#!/bin/sh\n"
            info = tarfile.TarInfo("sing-box-1.14.4-darwin-arm64/sing-box")
            info.size = len(data)
            t.addfile(info, io.BytesIO(data))
        self.assertEqual(fetch.extract(buf.getvalue(), "x.tar.gz", "sing-box"), b"#!/bin/sh\n")

    def test_mac_release_files_exist_on_github(self):
        for machine in ("arm64", "x86_64"):
            url = fetch.assets(mac=True, machine=machine)[0][0]
            req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "obhod-test"})
            with urllib.request.urlopen(req, timeout=30) as r:
                self.assertEqual(r.status, 200, url)


if __name__ == "__main__":
    unittest.main()
