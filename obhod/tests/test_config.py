import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import config as cfg  # noqa: E402
from core.osinfo import EXE  # noqa: E402

PROXY = {"type": "trojan", "tag": "x", "server": "198.51.100.1", "server_port": 443, "password": "p",
         "tls": {"enabled": True, "server_name": "a.example"}}
REGIONS = cfg.load_regions()


def outbound(conf, tag):
    return next(o for o in conf["outbounds"] if o["tag"] == tag)


def routed_to(conf, tag):
    return [r for r in conf["route"]["rules"] if r.get("outbound") == tag]


class Regions(unittest.TestCase):
    def test_every_region_is_complete(self):
        for code, r in REGIONS.items():
            for field in ("name", "dpi_supported", "domestic_suffixes", "dpi_domains", "proxy_domains",
                          "test_urls", "strategies"):
                self.assertIn(field, r, f"{code}: нет {field}")
            if r["dpi_supported"]:
                self.assertTrue(r["strategies"], f"{code}: нет стратегий")
                self.assertTrue(r["test_urls"], f"{code}: нет тестовых сайтов")
            ids = [s["id"] for s in r["strategies"]]
            self.assertEqual(len(ids), len(set(ids)), f"{code}: повторяются id стратегий")

    def test_fake_splits_at_the_start(self):
        # ByeDPI под Windows обрывает соединение, если fake режет не в начале (--fake -1, --fake 1+s)
        for code, r in REGIONS.items():
            for s in r["strategies"]:
                args = s["args"]
                for i, a in enumerate(args):
                    if a == "--fake":
                        self.assertEqual(args[i + 1], "1", f"{code}/{s['id']}")

    def test_default_modes(self):
        self.assertEqual(cfg.default_mode(REGIONS["ru"], has_key=False), "dpi")
        self.assertEqual(cfg.default_mode(REGIONS["ru"], has_key=True), "hybrid")
        self.assertEqual(cfg.default_mode(REGIONS["cn"], has_key=False), "vpn")


class Build(unittest.TestCase):
    def test_dpi_mode_needs_no_key(self):
        conf = cfg.build(REGIONS["ru"], "dpi")
        self.assertEqual(conf["route"]["final"], "direct")
        self.assertEqual(outbound(conf, "dpi")["server_port"], 1080)
        self.assertIn("youtube.com", routed_to(conf, "dpi")[0]["domain_suffix"])
        self.assertFalse(any(o["tag"] == "proxy" for o in conf["outbounds"]))

    def test_quic_to_dpi_sites_is_rejected(self):
        conf = cfg.build(REGIONS["ru"], "dpi")
        self.assertTrue(any(r.get("action") == "reject" and r.get("network") == "udp" for r in conf["route"]["rules"]))

    def test_vpn_and_hybrid_need_a_key(self):
        for mode in ("vpn", "hybrid"):
            with self.assertRaises(cfg.ConfigError):
                cfg.build(REGIONS["ru"], mode)

    def test_china_refuses_dpi(self):
        with self.assertRaises(cfg.ConfigError) as e:
            cfg.build(REGIONS["cn"], "dpi")
        self.assertIn("ключ", str(e.exception))

    def test_vpn_mode(self):
        conf = cfg.build(REGIONS["cn"], "vpn", PROXY)
        self.assertEqual(conf["route"]["final"], "proxy")
        self.assertEqual(outbound(conf, "proxy")["server"], "198.51.100.1")
        self.assertIn("baidu.com", routed_to(conf, "direct")[-1]["domain_suffix"])
        self.assertEqual(conf["dns"]["final"], "proxy-dns")

    def test_hybrid_routes_three_ways(self):
        conf = cfg.build(REGIONS["ru"], "hybrid", PROXY)
        self.assertEqual(conf["route"]["final"], "direct")
        self.assertIn("chatgpt.com", routed_to(conf, "proxy")[0]["domain_suffix"])
        self.assertIn("discord.com", routed_to(conf, "dpi")[0]["domain_suffix"])

    def test_proxy_rule_comes_before_dpi_rule(self):
        conf = cfg.build(REGIONS["ir"], "hybrid", PROXY)
        rules = conf["route"]["rules"]
        first_proxy = next(i for i, r in enumerate(rules) if r.get("outbound") == "proxy")
        first_dpi = next(i for i, r in enumerate(rules) if r.get("outbound") == "dpi")
        self.assertLess(first_proxy, first_dpi)

    def test_tls_fragment_only_where_region_wants_it(self):
        self.assertTrue(outbound(cfg.build(REGIONS["ru"], "vpn", PROXY), "proxy")["tls"].get("fragment"))
        self.assertNotIn("fragment", outbound(cfg.build(REGIONS["tr"], "vpn", PROXY), "proxy")["tls"])
        self.assertNotIn("fragment", PROXY["tls"], "исходный outbound не должен меняться")

    def test_no_fragment_on_reality(self):
        reality = {**PROXY, "type": "vless", "tls": {"enabled": True, "reality": {"enabled": True}}}
        self.assertNotIn("fragment", outbound(cfg.build(REGIONS["ru"], "vpn", reality), "proxy")["tls"])

    def test_turkey_resolves_dpi_sites_via_doh(self):
        conf = cfg.build(REGIONS["tr"], "dpi")
        self.assertTrue(any(r.get("action") == "resolve" for r in conf["route"]["rules"]))

    def test_tun_mode(self):
        conf = cfg.build(REGIONS["ru"], "dpi", tun=True)
        self.assertEqual([i["type"] for i in conf["inbounds"]], ["mixed", "tun"])
        rules = conf["route"]["rules"]
        self.assertTrue(any(r.get("action") == "hijack-dns" for r in rules))
        self.assertIn({"process_name": ["ciadpi" + EXE], "outbound": "direct"}, rules, "ciadpi не должен уходить в TUN по кругу")
        tun = conf["inbounds"][1]
        self.assertTrue(all(":" not in a for a in tun["address"]), "без IPv6 на TUN: в сетях без IPv6 соединения рвались")
        self.assertEqual(conf["dns"].get("strategy"), "ipv4_only")
        self.assertNotIn("strategy", cfg.build(REGIONS["ru"], "dpi")["dns"], "без TUN DNS не трогаем")

    def test_dpi_all_sends_tcp_to_dpi(self):
        conf = cfg.build(REGIONS["ru"], "dpi", dpi_all=True)
        self.assertIn({"network": "tcp", "outbound": "dpi"}, conf["route"]["rules"])

    def test_ciadpi_args(self):
        s = REGIONS["ru"]["strategies"][0]
        self.assertEqual(cfg.ciadpi_args(s, 1090)[:4], ["--ip", "127.0.0.1", "--port", "1090"])
        self.assertNotIn("--conn-ip", cfg.ciadpi_args(s, 1090))

    def test_ciadpi_binds_to_network_card_in_tun_mode(self):
        s = REGIONS["ru"]["strategies"][0]
        args = cfg.ciadpi_args(s, 1080, "192.168.1.66")
        self.assertEqual(args[4:6], ["--conn-ip", "192.168.1.66"])
        self.assertEqual(args[6:], s["args"], "привязка не должна ломать параметры стратегии")


if __name__ == "__main__":
    unittest.main()
