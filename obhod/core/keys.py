"""Разбор ключей (vless, vmess, trojan, ss, hysteria2, tuic) и подписок в outbound'ы sing-box."""
import base64
import binascii
import json
from dataclasses import dataclass, field
from urllib.parse import parse_qs, unquote, urlsplit

from . import subscription

SCHEMES = ("vless", "vmess", "trojan", "ss", "hy2", "hysteria2", "tuic")


class KeyParseError(ValueError):
    """Ключ не разобран или не поддерживается."""


@dataclass
class Key:
    name: str
    uri: str
    outbound: dict = field(repr=False)

    @property
    def protocol(self):
        return self.outbound["type"]

    @property
    def server(self):
        return f'{self.outbound["server"]}:{self.outbound["server_port"]}'


def _b64(s):
    s = s.strip().replace("-", "+").replace("_", "/")
    return base64.b64decode(s + "=" * (-len(s) % 4)).decode("utf-8")


def _q(query):
    return {k: v[0] for k, v in parse_qs(query, keep_blank_values=True).items()}


def _truthy(v):
    return str(v).lower() in ("1", "true", "yes")


def _port(u):
    try:
        port = u.port
    except ValueError:
        port = None
    if not port:
        raise KeyParseError("в ключе нет порта")
    return port


def _tls(q, sni_default, force=False):
    security = q.get("security", "tls" if force else "none")
    if security not in ("tls", "reality", "xtls"):
        return None
    tls = {"enabled": True, "server_name": q.get("sni") or q.get("peer") or sni_default}
    if _truthy(q.get("allowInsecure", q.get("insecure", "0"))):
        tls["insecure"] = True
    if q.get("alpn"):
        tls["alpn"] = [a for a in unquote(q["alpn"]).split(",") if a]
    fp = q.get("fp")
    if fp or security == "reality":
        tls["utls"] = {"enabled": True, "fingerprint": fp or "chrome"}
    if security == "reality":
        if not q.get("pbk"):
            raise KeyParseError("в Reality-ключе нет публичного ключа (pbk)")
        tls["reality"] = {"enabled": True, "public_key": q["pbk"], "short_id": q.get("sid", "")}
    return tls


def _transport(net, host, path, service_name=""):
    net = (net or "tcp").lower()
    if net in ("tcp", "raw", ""):
        return None
    if net == "ws":
        t = {"type": "ws", "path": path or "/"}
        if host:
            t["headers"] = {"Host": host}
        return t
    if net == "grpc":
        return {"type": "grpc", "service_name": service_name or path or ""}
    if net in ("http", "h2"):
        t = {"type": "http", "path": path or "/"}
        if host:
            t["host"] = [h for h in host.split(",") if h]
        return t
    if net == "httpupgrade":
        t = {"type": "httpupgrade", "path": path or "/"}
        if host:
            t["host"] = host
        return t
    raise KeyParseError(f"транспорт «{net}» пока не поддерживается (sing-box его не умеет)")


def _vless(u, q):
    ob = {"type": "vless", "server": u.hostname, "server_port": _port(u), "uuid": unquote(u.username or "")}
    if q.get("flow"):
        ob["flow"] = q["flow"]
    tls = _tls(q, u.hostname)
    if tls:
        ob["tls"] = tls
    tr = _transport(q.get("type"), q.get("host"), unquote(q.get("path", "")), q.get("serviceName", ""))
    if tr:
        ob["transport"] = tr
    ob["packet_encoding"] = "xudp"
    return ob


def _trojan(u, q):
    ob = {"type": "trojan", "server": u.hostname, "server_port": _port(u), "password": unquote(u.username or "")}
    tls = _tls(q, u.hostname, force=True)
    if tls:
        ob["tls"] = tls
    tr = _transport(q.get("type"), q.get("host"), unquote(q.get("path", "")), q.get("serviceName", ""))
    if tr:
        ob["transport"] = tr
    return ob


def _vmess(body):
    try:
        d = json.loads(_b64(body))
    except (ValueError, binascii.Error) as e:
        raise KeyParseError("vmess-ключ не похож на base64 JSON") from e
    ob = {
        "type": "vmess",
        "server": d["add"],
        "server_port": int(d["port"]),
        "uuid": d["id"],
        "security": d.get("scy") or "auto",
        "alter_id": int(d.get("aid") or 0),
    }
    if d.get("tls") == "tls":
        q = {"security": "tls", "sni": d.get("sni") or d.get("host"), "alpn": d.get("alpn", ""), "fp": d.get("fp", "")}
        ob["tls"] = _tls({k: v for k, v in q.items() if v}, d["add"])
    tr = _transport(d.get("net"), d.get("host"), d.get("path", ""), d.get("path", ""))
    if tr:
        ob["transport"] = tr
    return ob, d.get("ps", "")


def _ss(rest, q):
    # SIP002: ss://base64(method:password)@host:port  или  ss://method:password@host:port (2022-шифры)
    # Старый формат: ss://base64(method:password@host:port)
    if "plugin" in q:
        raise KeyParseError("ss с плагином (obfs/v2ray-plugin) пока не поддерживается")
    if "@" not in rest:
        rest = _b64(rest)
    userinfo, _, hostport = rest.rpartition("@")
    try:
        creds = _b64(userinfo)
        if ":" not in creds:
            raise ValueError
    except (ValueError, binascii.Error, UnicodeDecodeError):
        creds = unquote(userinfo)
    method, _, password = creds.partition(":")
    u = urlsplit("//" + hostport)
    if not method or not password:
        raise KeyParseError("в ss-ключе нет метода или пароля")
    return {"type": "shadowsocks", "server": u.hostname, "server_port": _port(u), "method": method, "password": password}


def _hy2(u, q):
    ob = {
        "type": "hysteria2",
        "server": u.hostname,
        "server_port": _port(u),
        "password": unquote(u.username or "") + (":" + unquote(u.password) if u.password else ""),
        "tls": {"enabled": True, "server_name": q.get("sni") or u.hostname},
    }
    if _truthy(q.get("insecure", "0")):
        ob["tls"]["insecure"] = True
    if q.get("obfs"):
        ob["obfs"] = {"type": q["obfs"], "password": q.get("obfs-password", "")}
    return ob


def _tuic(u, q):
    return {
        "type": "tuic",
        "server": u.hostname,
        "server_port": _port(u),
        "uuid": unquote(u.username or ""),
        "password": unquote(u.password or ""),
        "congestion_control": q.get("congestion_control", "bbr"),
        "udp_relay_mode": q.get("udp_relay_mode", "native"),
        "tls": {
            "enabled": True,
            "server_name": q.get("sni") or u.hostname,
            "alpn": [a for a in unquote(q.get("alpn", "h3")).split(",") if a],
            **({"insecure": True} if _truthy(q.get("allow_insecure", q.get("insecure", "0"))) else {}),
        },
    }


def parse_key(uri):
    uri = uri.strip()
    scheme, sep, rest = uri.partition("://")
    scheme = scheme.lower()
    if not sep or scheme not in SCHEMES:
        raise KeyParseError(f"неизвестный формат ключа: {uri[:30]}…")
    rest, _, frag = rest.partition("#")
    name = unquote(frag)
    if scheme == "vmess":
        ob, ps = _vmess(rest)
        name = name or ps
    else:
        body, _, query = rest.partition("?")
        q = _q(query)
        if scheme == "ss":
            ob = _ss(body, q)
        else:
            u = urlsplit(f"{scheme}://{body}")
            if not u.hostname:
                raise KeyParseError("в ключе нет адреса сервера")
            ob = {"vless": _vless, "trojan": _trojan, "hy2": _hy2, "hysteria2": _hy2, "tuic": _tuic}[scheme](u, q)
    ob["tag"] = "proxy"
    return Key(name=name or f'{ob["type"]} {ob["server"]}', uri=uri, outbound=ob)


def parse_many(text):
    """Ключи из текста: по одному в строке, либо base64-подписка, либо JSON sing-box. Возвращает (ключи, ошибки)."""
    text = text.strip()
    if text.startswith("{"):
        return _from_singbox_json(text), []
    if "://" not in text:
        try:
            text = _b64(text)
        except (ValueError, binascii.Error, UnicodeDecodeError):
            return [], ["текст не похож ни на ключ, ни на подписку"]
    keys, errors = [], []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            keys.append(parse_key(line))
        except (KeyParseError, KeyError, ValueError) as e:
            errors.append(f"{line[:40]}…: {e}")
    return keys, errors


def _from_singbox_json(text):
    data = json.loads(text)
    keys = []
    for ob in data.get("outbounds", []):
        if ob.get("type") in ("vless", "vmess", "trojan", "shadowsocks", "hysteria2", "tuic", "wireguard"):
            name = ob.get("tag", ob["type"])
            ob = dict(ob, tag="proxy")
            keys.append(Key(name=name, uri="", outbound=ob))
    return keys


def fetch_subscription(url, timeout=15, pinned=None):
    """Скачивает подписку. Возвращает (ключи, ошибки, userinfo).

    Сертификат проверяется по хранилищу системы; не подтвердился — subscription.CertError с отпечатком.
    pinned — отпечаток, которому пользователь уже разрешил доверять для этого сервера.
    """
    raw, headers = subscription.download(url, timeout, pinned)
    body = raw.decode("utf-8", "replace")
    info = headers.get("subscription-userinfo", "") or ""
    keys, errors = parse_many(body)
    userinfo = dict(p.strip().split("=", 1) for p in info.split(";") if "=" in p)
    return keys, errors, userinfo
