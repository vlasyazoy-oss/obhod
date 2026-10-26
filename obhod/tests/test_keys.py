import base64
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import keys  # noqa: E402

# Тестовые ключи выдуманы: адреса из документационных диапазонов, UUID и пароли случайные.
UUID = "b831381d-6324-4d53-ad4f-8cda48b30811"


class ParseKey(unittest.TestCase):
    def test_vless_reality(self):
        k = keys.parse_key(f"vless://{UUID}@203.0.113.5:443?type=tcp&security=reality&pbk=PUBKEY&sid=ab12"
                           "&sni=www.microsoft.com&fp=chrome&flow=xtls-rprx-vision&encryption=none#Мой%20сервер")
        ob = k.outbound
        self.assertEqual(k.name, "Мой сервер")
        self.assertEqual((ob["type"], ob["server"], ob["server_port"], ob["uuid"]), ("vless", "203.0.113.5", 443, UUID))
        self.assertEqual(ob["flow"], "xtls-rprx-vision")
        self.assertEqual(ob["tls"]["reality"], {"enabled": True, "public_key": "PUBKEY", "short_id": "ab12"})
        self.assertEqual(ob["tls"]["server_name"], "www.microsoft.com")
        self.assertEqual(ob["tls"]["utls"]["fingerprint"], "chrome")
        self.assertNotIn("transport", ob)
        self.assertEqual(ob["tag"], "proxy")

    def test_vless_ws_tls(self):
        ob = keys.parse_key(f"vless://{UUID}@example.com:443?type=ws&security=tls&path=%2Fws&host=cdn.example.com").outbound
        self.assertEqual(ob["transport"], {"type": "ws", "path": "/ws", "headers": {"Host": "cdn.example.com"}})
        self.assertTrue(ob["tls"]["enabled"])

    def test_vless_without_tls(self):
        ob = keys.parse_key(f"vless://{UUID}@198.51.100.1:80?type=tcp&security=none").outbound
        self.assertNotIn("tls", ob)

    def test_reality_without_pbk_is_rejected(self):
        with self.assertRaises(keys.KeyParseError):
            keys.parse_key(f"vless://{UUID}@198.51.100.1:443?security=reality&sni=a.com")

    def test_unsupported_transport(self):
        with self.assertRaises(keys.KeyParseError):
            keys.parse_key(f"vless://{UUID}@198.51.100.1:443?type=xhttp&security=tls")

    def test_vmess(self):
        body = base64.b64encode(json.dumps({
            "v": "2", "ps": "vm", "add": "198.51.100.7", "port": "8443", "id": UUID, "aid": "0",
            "scy": "auto", "net": "grpc", "path": "svc", "tls": "tls", "sni": "s.example.com"}).encode()).decode()
        k = keys.parse_key("vmess://" + body)
        self.assertEqual(k.name, "vm")
        self.assertEqual(k.outbound["server_port"], 8443)
        self.assertEqual(k.outbound["transport"], {"type": "grpc", "service_name": "svc"})
        self.assertEqual(k.outbound["tls"]["server_name"], "s.example.com")

    def test_trojan_has_tls_by_default(self):
        ob = keys.parse_key("trojan://secret@example.org:443?sni=example.org#t").outbound
        self.assertEqual(ob["password"], "secret")
        self.assertTrue(ob["tls"]["enabled"])

    def test_ss_sip002_base64(self):
        ui = base64.urlsafe_b64encode(b"chacha20-ietf-poly1305:pass123").decode().rstrip("=")
        ob = keys.parse_key(f"ss://{ui}@198.51.100.2:8388#ss").outbound
        self.assertEqual((ob["method"], ob["password"], ob["server_port"]), ("chacha20-ietf-poly1305", "pass123", 8388))

    def test_ss_2022_plain_userinfo(self):
        ob = keys.parse_key("ss://2022-blake3-aes-128-gcm:YWJjZGVmZ2hpamtsbW5vcA%3D%3D@198.51.100.2:443").outbound
        self.assertEqual(ob["method"], "2022-blake3-aes-128-gcm")
        self.assertEqual(ob["password"], "YWJjZGVmZ2hpamtsbW5vcA==")

    def test_ss_legacy_whole_base64(self):
        whole = base64.b64encode(b"aes-256-gcm:pw@198.51.100.3:1234").decode()
        ob = keys.parse_key(f"ss://{whole}#old").outbound
        self.assertEqual((ob["server"], ob["server_port"], ob["password"]), ("198.51.100.3", 1234, "pw"))

    def test_hysteria2(self):
        ob = keys.parse_key("hy2://pw@203.0.113.9:443?sni=h.example.com&obfs=salamander&obfs-password=x&insecure=1").outbound
        self.assertEqual(ob["type"], "hysteria2")
        self.assertEqual(ob["obfs"], {"type": "salamander", "password": "x"})
        self.assertTrue(ob["tls"]["insecure"])

    def test_tuic(self):
        ob = keys.parse_key(f"tuic://{UUID}:pw@203.0.113.9:443?congestion_control=bbr&alpn=h3&sni=t.example.com").outbound
        self.assertEqual((ob["uuid"], ob["password"]), (UUID, "pw"))
        self.assertEqual(ob["tls"]["alpn"], ["h3"])

    def test_garbage(self):
        for bad in ("hello", "http://example.com", "vless://", "vless://uuid@host"):
            with self.assertRaises((keys.KeyParseError, ValueError)):
                keys.parse_key(bad)


class ParseMany(unittest.TestCase):
    def test_base64_subscription_with_a_bad_line(self):
        text = "\n".join([f"vless://{UUID}@198.51.100.1:443?security=tls#a", "junk://x", "trojan://p@h.example:443#b"])
        found, errors = keys.parse_many(base64.b64encode(text.encode()).decode())
        self.assertEqual([k.name for k in found], ["a", "b"])
        self.assertEqual(len(errors), 1)

    def test_singbox_json(self):
        data = {"outbounds": [{"type": "direct", "tag": "direct"},
                              {"type": "vless", "tag": "de-1", "server": "198.51.100.1", "server_port": 443, "uuid": UUID}]}
        found, _ = keys.parse_many(json.dumps(data))
        self.assertEqual(len(found), 1)
        self.assertEqual((found[0].name, found[0].outbound["tag"]), ("de-1", "proxy"))


if __name__ == "__main__":
    unittest.main()
