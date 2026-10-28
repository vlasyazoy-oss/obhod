"""Скачивание подписок с проверкой сертификата.

Проверка идёт через хранилище сертификатов системы (truststore), как у браузера: корневые сертификаты
корпоративных фильтров и антивирусов, которым доверяет Windows, признаются и здесь. Если сертификат всё равно
не подтверждён (самоподписанный у сервера), бросается CertError с отпечатком — приложение спрашивает
пользователя и может «закрепить» отпечаток для этого сервера (pinned).
"""
import hashlib
import http.client
import socket
import ssl
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from .i18n import t
from .version import VERSION

HEADERS = {"User-Agent": f"obhod/{VERSION}"}


class CertError(ValueError):
    """Сертификат сервера подписки не подтверждён. fingerprint — SHA-256 сертификата сервера (или "")."""

    def __init__(self, url, host, port, fingerprint, reason):
        super().__init__(f"сертификат {host} не подтверждён: {reason}")
        self.url, self.host, self.port, self.fingerprint, self.reason = url, host, port, fingerprint, reason


def trusted_context():
    """SSL-контекст на хранилище системы. Без truststore — обычный контекст Python (тоже читает хранилище Windows,
    но не видит часть сертификатов, которые раздаёт компания через групповые политики)."""
    try:
        import truststore
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        return ssl.create_default_context()


def _unverified_context():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def fingerprint(der):
    return ":".join(f"{b:02X}" for b in hashlib.sha256(der).digest())


def server_fingerprint(host, port=443, timeout=10):
    """Отпечаток сертификата, который сервер показывает на самом деле (без проверки)."""
    with socket.create_connection((host, port), timeout=timeout) as raw:
        with _unverified_context().wrap_socket(raw, server_hostname=host) as tls:
            return fingerprint(tls.getpeercert(binary_form=True))


def download(url, timeout=15, pinned=None):
    """(тело, заголовки). pinned — отпечаток, которому пользователь разрешил доверять для этого сервера."""
    if pinned and url.lower().startswith("https://"):
        return _download_pinned(url, timeout, pinned)
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=trusted_context()) as r:
            return r.read(), r.headers
    except urllib.error.URLError as e:
        if not isinstance(e.reason, ssl.SSLCertVerificationError):
            raise
        u = urlsplit(url)
        port = u.port or 443
        try:
            fp = server_fingerprint(u.hostname, port, timeout)
        except OSError:
            fp = ""
        raise CertError(url, u.hostname, port, fp, e.reason.verify_message or str(e.reason)) from e


def _download_pinned(url, timeout, pinned):
    """Соединение без проверки цепочки, но с проверкой отпечатка ДО отправки запроса: подменённый сертификат
    (другой отпечаток) не пройдёт. Перенаправления не выполняем — у адреса перенаправления свой сертификат."""
    u = urlsplit(url)
    port = u.port or 443
    conn = http.client.HTTPSConnection(u.hostname, port, timeout=timeout, context=_unverified_context())
    try:
        conn.connect()
        actual = fingerprint(conn.sock.getpeercert(binary_form=True))
        if actual != pinned:
            raise CertError(url, u.hostname, port, actual, t("err_cert_changed"))
        path = (u.path or "/") + (f"?{u.query}" if u.query else "")
        conn.request("GET", path, headers={**HEADERS, "Host": u.netloc})
        r = conn.getresponse()
        if 300 <= r.status < 400:
            raise ValueError(t("err_sub_redirect", r.getheader("Location")))
        if r.status >= 400:
            raise ValueError(t("err_sub_status", r.status, r.reason))
        return r.read(), r.headers
    finally:
        conn.close()
