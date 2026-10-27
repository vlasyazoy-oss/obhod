"""Скачивание подписок: проверка сертификата по хранилищу системы, отпечаток для самоподписанных, закрепление."""
import base64
import http.server
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import keys, subscription  # noqa: E402
from core.subscription import CertError  # noqa: E402

UUID = "b831381d-6324-4d53-ad4f-8cda48b30811"
SUB = "\n".join([f"vless://{UUID}@198.51.100.1:443?security=tls#a", "trojan://p@h.example:443#b"])
OPENSSL = shutil.which("openssl")


def make_cert(directory, cn="localhost"):
    key, cert = os.path.join(directory, "key.pem"), os.path.join(directory, "cert.pem")
    subprocess.run([OPENSSL, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", key, "-out", cert,
                    "-days", "1", "-subj", f"/CN={cn}"], check=True, capture_output=True)
    return cert, key


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = base64.b64encode(SUB.encode())
        self.send_response(200)
        self.send_header("subscription-userinfo", "upload=1; download=2; total=3")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@unittest.skipUnless(OPENSSL, "нет openssl для самоподписанного сертификата")
class SelfSignedServer(unittest.TestCase):
    """Сервер подписки с самоподписанным сертификатом прямо в тесте — без сети."""

    def start(self, cert, key):
        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert, key)
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        return f"https://localhost:{server.server_address[1]}/sub/token"

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_rejected_with_fingerprint_then_pinned_works(self):
        url = self.start(*make_cert(self.dir))
        with self.assertRaises(CertError) as cm:
            keys.fetch_subscription(url, timeout=10)
        e = cm.exception
        self.assertEqual(e.host, "localhost")
        self.assertRegex(e.fingerprint, r"^([0-9A-F]{2}:){31}[0-9A-F]{2}$")
        self.assertTrue(e.reason)
        found, errors, info = keys.fetch_subscription(url, timeout=10, pinned=e.fingerprint)
        self.assertEqual([k.name for k in found], ["a", "b"])
        self.assertEqual((errors, info["total"]), ([], "3"))

    def test_pin_does_not_accept_a_different_certificate(self):
        """Закреплённый отпечаток — не «доверять всему»: подменённый сертификат снова отклоняется."""
        url = self.start(*make_cert(self.dir))
        first = subscription.server_fingerprint("localhost", int(url.split(":")[2].split("/")[0]))
        other_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, other_dir, True)
        url2 = self.start(*make_cert(other_dir))
        with self.assertRaises(CertError) as cm:
            keys.fetch_subscription(url2, timeout=10, pinned=first)
        self.assertIn("изменился", cm.exception.reason)
        self.assertNotEqual(cm.exception.fingerprint, first)


class LiveBadSsl(unittest.TestCase):
    """Публичные тестовые сайты badssl.com с заведомо плохими сертификатами."""

    def check(self, host):
        try:
            subscription.download(f"https://{host}/", timeout=15)
        except CertError as e:
            return e
        except OSError as e:
            self.skipTest(f"{host} недоступен: {e}")
        self.fail(f"{host}: плохой сертификат принят")

    def test_self_signed(self):
        e = self.check("self-signed.badssl.com")
        self.assertEqual(e.fingerprint, subscription.server_fingerprint("self-signed.badssl.com"))
        body, _ = subscription.download("https://self-signed.badssl.com/", timeout=15, pinned=e.fingerprint)
        self.assertIn(b"badssl", body, "после закрепления отпечатка страница скачивается")

    def test_untrusted_root_like_a_corporate_filter(self):
        self.assertTrue(self.check("untrusted-root.badssl.com").fingerprint)

    def test_expired(self):
        self.assertIn("expired", self.check("expired.badssl.com").reason)

    def test_normal_site_passes_via_system_store(self):
        try:
            body, _ = subscription.download("https://example.com/", timeout=15)
        except OSError as e:
            self.skipTest(f"example.com недоступен: {e}")
        self.assertIn(b"Example Domain", body)


class Context(unittest.TestCase):
    def test_uses_system_trust_store(self):
        ctx = subscription.trusted_context()
        try:
            import truststore
        except ImportError:
            self.skipTest("truststore не установлен")
        self.assertIsInstance(ctx, truststore.SSLContext)


if __name__ == "__main__":
    unittest.main()
