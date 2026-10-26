"""Профили регионов и сборка конфига sing-box под режим: обход DPI, VPN по ключу или гибрид."""
import copy
import json
import os

from .paths import RES
MODES = {"dpi": "Обход DPI", "vpn": "VPN по ключу", "hybrid": "Гибрид"}


class ConfigError(ValueError):
    """Режим нельзя включить с текущими настройками; текст показывается пользователю."""


def load_regions(path=os.path.join(RES, "core", "regions.json")):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def default_mode(region, has_key):
    if not region["dpi_supported"]:
        return "vpn"
    return "hybrid" if has_key else "dpi"


def build(region, mode, proxy_outbound=None, *, mixed_port=2080, dpi_port=1080, tun=False,
          dpi_all=False, log_level="info"):
    """Системный прокси sing-box не ставит: это делает core.sysproxy, чтобы его можно было снять даже после сбоя."""
    if mode not in MODES:
        raise ConfigError(f"неизвестный режим {mode}")
    uses_proxy = mode in ("vpn", "hybrid")
    uses_dpi = mode in ("dpi", "hybrid")
    if uses_proxy and not proxy_outbound:
        raise ConfigError("Для этого режима нужен ключ: вставьте ссылку vless://, hy2://, trojan://, ss:// или подписку.")
    if uses_dpi and not region["dpi_supported"]:
        raise ConfigError(region.get("dpi_note") or "В этом регионе обход DPI не работает, нужен ключ.")

    doh = region.get("doh")
    dns_servers = [{"type": "local", "tag": "local"}]
    if doh:
        dns_servers.insert(0, {"type": "https", "tag": "doh", "server": doh})
    if uses_proxy:
        dns_servers.append({"type": "https", "tag": "proxy-dns", "server": "1.1.1.1", "detour": "proxy"})
    direct_resolver = "doh" if doh else "local"
    dns = {"servers": dns_servers, "final": "proxy-dns" if mode == "vpn" else direct_resolver}
    if region["domestic_suffixes"] and mode == "vpn":
        dns["rules"] = [{"domain_suffix": region["domestic_suffixes"], "server": direct_resolver}]

    inbounds = [{"type": "mixed", "tag": "mixed-in", "listen": "127.0.0.1", "listen_port": mixed_port}]
    if tun:
        # Только IPv4, как «Маршрут IPv6: отключить» у Hiddify. С IPv6-адресом на TUN Windows считает IPv6 доступным,
        # программы подключаются по IPv6, TUN соединение принимает, а у сети пользователя IPv6 часто нет —
        # соединение рвётся, и на IPv4 программа уже не переходит (так ломался example.com).
        inbounds.append({
            "type": "tun", "tag": "tun-in", "interface_name": "obhod",
            "address": ["172.19.0.1/30"],
            "auto_route": True, "strict_route": True, "stack": "mixed",
        })
        dns["strategy"] = "ipv4_only"  # перехваченный DNS не отдаёт AAAA: программы сразу идут по IPv4

    outbounds = [{"type": "direct", "tag": "direct"}]
    if uses_dpi:
        outbounds.append({"type": "socks", "tag": "dpi", "server": "127.0.0.1", "server_port": dpi_port, "version": "5"})
    if uses_proxy:
        ob = copy.deepcopy(proxy_outbound)
        ob["tag"] = "proxy"
        tls = ob.get("tls")
        if region.get("proxy_tls_fragment") and tls and not tls.get("reality"):
            tls["fragment"] = True
        outbounds.append(ob)

    rules = [{"action": "sniff"}]
    if tun:
        rules.append({"protocol": "dns", "action": "hijack-dns"})
        rules.append({"process_name": ["ciadpi.exe"], "outbound": "direct"})
    rules.append({"ip_is_private": True, "outbound": "direct"})
    if region["domestic_suffixes"] and mode != "dpi":
        rules.append({"domain_suffix": region["domestic_suffixes"], "outbound": "direct"})
    if mode == "hybrid" and region["proxy_domains"]:
        rules.append({"domain_suffix": region["proxy_domains"], "outbound": "proxy"})
    if uses_dpi:
        dpi_match = {} if dpi_all else {"domain_suffix": region["dpi_domains"]}
        if dpi_all and region["domestic_suffixes"]:
            rules.append({"domain_suffix": region["domestic_suffixes"], "outbound": "direct"})
        if dpi_all or region["dpi_domains"]:
            # QUIC к этим сайтам режем, чтобы браузер ушёл на TCP, где работает обход
            rules.append({**dpi_match, "network": "udp", "port": 443, "action": "reject"})
            if region.get("resolve_dpi_via_doh") and doh:
                rules.append({**dpi_match, "action": "resolve", "server": "doh"})
            rules.append({**dpi_match, "outbound": "dpi"} if dpi_match else {"network": "tcp", "outbound": "dpi"})

    final = {"dpi": "direct", "vpn": "proxy", "hybrid": "direct"}[mode]
    return {
        "log": {"level": log_level, "timestamp": True},
        "dns": dns,
        "inbounds": inbounds,
        "outbounds": outbounds,
        "route": {
            "rules": rules,
            "final": final,
            "auto_detect_interface": True,
            "default_domain_resolver": {"server": direct_resolver},
        },
    }


def ciadpi_args(strategy, port=1080, conn_ip=None):
    """conn_ip — адрес сетевой карты, к которому ByeDPI привязывает исходящие соединения (нужно в режиме TUN)."""
    bind = ["--conn-ip", conn_ip] if conn_ip else []
    return ["--ip", "127.0.0.1", "--port", str(port), *bind, *strategy["args"]]
