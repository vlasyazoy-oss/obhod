package org.obhod.app

import org.json.JSONArray
import org.json.JSONObject

/**
 * Профили регионов и конфиг sing-box под режим. Порт core/config.py с поправками на Android:
 * TUN держит hev-socks5-tunnel и отдаёт весь трафик (включая DNS) в mixed-inbound sing-box;
 * само приложение исключено из VPN, поэтому sing-box и ByeDPI ходят в сеть напрямую, без петли.
 */
object Config {
    /** code — для перевода на экране: need_key, dpi_unsupported. */
    class ConfigError(message: String, val code: String = "") : IllegalArgumentException(message)

    val MODES = linkedMapOf("dpi" to "Обход DPI", "vpn" to "VPN по ключу", "hybrid" to "Гибрид")

    const val MIXED_PORT = 2080
    const val DPI_PORT = 1080
    const val TUN_DNS = "172.19.0.2" // DNS-сервер, который VPN объявляет системе; запросы к нему перехватывает sing-box

    fun defaultMode(region: JSONObject, hasKey: Boolean): String = when {
        !region.getBoolean("dpi_supported") -> "vpn"
        hasKey -> "hybrid"
        else -> "dpi"
    }

    private fun strings(region: JSONObject, field: String): JSONArray = region.optJSONArray(field) ?: JSONArray()

    fun build(region: JSONObject, mode: String, proxyOutbound: JSONObject?, dpiAll: Boolean = false,
              logLevel: String = "info"): JSONObject {
        if (mode !in MODES) throw ConfigError("неизвестный режим $mode")
        val usesProxy = mode == "vpn" || mode == "hybrid"
        val usesDpi = mode == "dpi" || mode == "hybrid"
        if (usesProxy && proxyOutbound == null) {
            throw ConfigError("Для этого режима нужен ключ: вставьте ссылку vless://, hy2://, trojan://, ss:// или подписку.", "need_key")
        }
        if (usesDpi && !region.getBoolean("dpi_supported")) {
            throw ConfigError(region.optString("dpi_note").ifEmpty { "В этом регионе обход DPI не работает, нужен ключ." }, "dpi_unsupported")
        }
        val domestic = strings(region, "domestic_suffixes")
        val dpiDomains = strings(region, "dpi_domains")
        val proxyDomains = strings(region, "proxy_domains")
        val doh = region.optString("doh").takeIf { it.isNotEmpty() && it != "null" }

        // В Android у отдельного бинарника sing-box нет системного резолвера (/etc/resolv.conf), поэтому «local» — обычный UDP
        val servers = JSONArray()
        if (doh != null) servers.put(JSONObject().put("type", "https").put("tag", "doh").put("server", doh))
        servers.put(JSONObject().put("type", "udp").put("tag", "local").put("server", doh ?: "1.1.1.1"))
        if (usesProxy) {
            servers.put(JSONObject().put("type", "https").put("tag", "proxy-dns").put("server", "1.1.1.1").put("detour", "proxy"))
        }
        val directResolver = if (doh != null) "doh" else "local"
        val dns = JSONObject().put("servers", servers).put("final", if (mode == "vpn") "proxy-dns" else directResolver)
        if (domestic.length() > 0 && mode == "vpn") {
            dns.put("rules", JSONArray().put(JSONObject().put("domain_suffix", domestic).put("server", directResolver)))
        }

        val outbounds = JSONArray().put(JSONObject().put("type", "direct").put("tag", "direct"))
        if (usesDpi) {
            outbounds.put(JSONObject().put("type", "socks").put("tag", "dpi").put("server", "127.0.0.1")
                .put("server_port", DPI_PORT).put("version", "5"))
        }
        if (usesProxy) {
            val ob = JSONObject(proxyOutbound.toString()).put("tag", "proxy")
            val tls = ob.optJSONObject("tls")
            if (region.optBoolean("proxy_tls_fragment") && tls != null && !tls.has("reality")) tls.put("fragment", true)
            outbounds.put(ob)
        }

        val rules = JSONArray()
            .put(JSONObject().put("action", "sniff"))
            .put(JSONObject().put("protocol", "dns").put("action", "hijack-dns"))
            .put(JSONObject().put("ip_is_private", true).put("outbound", "direct"))
        if (domestic.length() > 0 && mode != "dpi") rules.put(JSONObject().put("domain_suffix", domestic).put("outbound", "direct"))
        if (mode == "hybrid" && proxyDomains.length() > 0) {
            rules.put(JSONObject().put("domain_suffix", proxyDomains).put("outbound", "proxy"))
        }
        if (usesDpi && (dpiAll || dpiDomains.length() > 0)) {
            if (dpiAll && domestic.length() > 0) rules.put(JSONObject().put("domain_suffix", domestic).put("outbound", "direct"))
            fun match() = if (dpiAll) JSONObject() else JSONObject().put("domain_suffix", dpiDomains)
            // QUIC к этим сайтам режем, чтобы браузер ушёл на TCP, где работает обход
            rules.put(match().put("network", "udp").put("port", 443).put("action", "reject"))
            if (region.optBoolean("resolve_dpi_via_doh") && doh != null) rules.put(match().put("action", "resolve").put("server", "doh"))
            rules.put(if (dpiAll) JSONObject().put("network", "tcp").put("outbound", "dpi") else match().put("outbound", "dpi"))
        }

        val inbound = JSONObject().put("type", "mixed").put("tag", "mixed-in").put("listen", "127.0.0.1").put("listen_port", MIXED_PORT)
        return JSONObject()
            .put("log", JSONObject().put("level", logLevel).put("timestamp", true))
            .put("dns", dns)
            .put("inbounds", JSONArray().put(inbound))
            .put("outbounds", outbounds)
            .put("route", JSONObject()
                .put("rules", rules)
                .put("final", mapOf("dpi" to "direct", "vpn" to "proxy", "hybrid" to "direct").getValue(mode))
                .put("default_domain_resolver", JSONObject().put("server", directResolver)))
    }

    fun byedpiArgs(strategy: JSONObject, port: Int = DPI_PORT): List<String> {
        val args = strategy.getJSONArray("args")
        return listOf("--ip", "127.0.0.1", "--port", port.toString()) + (0 until args.length()).map { args.getString(it) }
    }

    /** Конфиг hev-socks5-tunnel: TUN → SOCKS5 sing-box, UDP тоже (через UDP ASSOCIATE). */
    fun tunnelYaml(mtu: Int = 8500) = """
        |tunnel:
        |  mtu: $mtu
        |  ipv4: 172.19.0.1
        |socks5:
        |  address: 127.0.0.1
        |  port: $MIXED_PORT
        |  udp: 'udp'
        |misc:
        |  task-stack-size: 81920
        |""".trimMargin()
}
