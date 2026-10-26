package org.obhod.app

import org.json.JSONArray
import org.json.JSONObject
import java.net.URLDecoder
import java.util.Base64

/** Разбор ключей (vless, vmess, trojan, ss, hysteria2, tuic) и подписок в outbound'ы sing-box. Порт core/keys.py. */
object Keys {
    class KeyParseError(message: String) : IllegalArgumentException(message)

    data class Key(val name: String, val uri: String, val outbound: JSONObject) {
        val protocol: String get() = outbound.getString("type")
    }

    private val SCHEMES = setOf("vless", "vmess", "trojan", "ss", "hy2", "hysteria2", "tuic")

    private fun unquote(s: String) = URLDecoder.decode(s.replace("+", "%2B"), "UTF-8")

    fun b64(s: String): String {
        val clean = s.trim().replace('-', '+').replace('_', '/')
        val padded = clean + "=".repeat((4 - clean.length % 4) % 4)
        return String(Base64.getDecoder().decode(padded), Charsets.UTF_8)
    }

    private fun query(q: String): Map<String, String> =
        q.split("&").filter { it.isNotEmpty() }.associate {
            val (k, v) = (it.split("=", limit = 2) + "").take(2)
            k to unquote(v)
        }

    private fun truthy(v: String?) = v?.lowercase() in setOf("1", "true", "yes")

    /** host:port, IPv6 в квадратных скобках. */
    private data class HostPort(val host: String, val port: Int)

    private fun hostPort(s: String): HostPort {
        val m = Regex("^\\[?([^\\[\\]]+?)]?:(\\d+)$").find(s) ?: throw KeyParseError("в ключе нет адреса или порта")
        val port = m.groupValues[2].toInt()
        if (port !in 1..65535) throw KeyParseError("в ключе нет порта")
        return HostPort(m.groupValues[1], port)
    }

    /** userinfo@host:port → (userinfo, host, port). */
    private fun authority(body: String): Triple<String, HostPort, String> {
        val at = body.lastIndexOf('@')
        val user = if (at >= 0) body.substring(0, at) else ""
        val rest = if (at >= 0) body.substring(at + 1) else body
        return Triple(user, hostPort(rest.trimEnd('/')), rest)
    }

    private fun tls(q: Map<String, String>, sniDefault: String, force: Boolean = false): JSONObject? {
        val security = q["security"] ?: if (force) "tls" else "none"
        if (security !in setOf("tls", "reality", "xtls")) return null
        val t = JSONObject().put("enabled", true).put("server_name", q["sni"] ?: q["peer"] ?: sniDefault)
        if (truthy(q["allowInsecure"] ?: q["insecure"])) t.put("insecure", true)
        q["alpn"]?.takeIf { it.isNotEmpty() }?.let { a -> t.put("alpn", JSONArray(a.split(",").filter { it.isNotEmpty() })) }
        val fp = q["fp"]
        if (!fp.isNullOrEmpty() || security == "reality") {
            t.put("utls", JSONObject().put("enabled", true).put("fingerprint", fp?.ifEmpty { null } ?: "chrome"))
        }
        if (security == "reality") {
            val pbk = q["pbk"]?.takeIf { it.isNotEmpty() } ?: throw KeyParseError("в Reality-ключе нет публичного ключа (pbk)")
            t.put("reality", JSONObject().put("enabled", true).put("public_key", pbk).put("short_id", q["sid"] ?: ""))
        }
        return t
    }

    private fun transport(net: String?, host: String?, path: String?, serviceName: String? = null): JSONObject? {
        return when ((net ?: "tcp").lowercase()) {
            "tcp", "raw", "" -> null
            "ws" -> JSONObject().put("type", "ws").put("path", path?.ifEmpty { null } ?: "/").apply {
                if (!host.isNullOrEmpty()) put("headers", JSONObject().put("Host", host))
            }
            "grpc" -> JSONObject().put("type", "grpc").put("service_name", serviceName?.ifEmpty { null } ?: path ?: "")
            "http", "h2" -> JSONObject().put("type", "http").put("path", path?.ifEmpty { null } ?: "/").apply {
                if (!host.isNullOrEmpty()) put("host", JSONArray(host.split(",").filter { it.isNotEmpty() }))
            }
            "httpupgrade" -> JSONObject().put("type", "httpupgrade").put("path", path?.ifEmpty { null } ?: "/").apply {
                if (!host.isNullOrEmpty()) put("host", host)
            }
            else -> throw KeyParseError("транспорт «$net» пока не поддерживается (sing-box его не умеет)")
        }
    }

    private fun vless(body: String, q: Map<String, String>): JSONObject {
        val (user, hp, _) = authority(body)
        val ob = JSONObject().put("type", "vless").put("server", hp.host).put("server_port", hp.port).put("uuid", unquote(user))
        q["flow"]?.takeIf { it.isNotEmpty() }?.let { ob.put("flow", it) }
        tls(q, hp.host)?.let { ob.put("tls", it) }
        transport(q["type"], q["host"], q["path"], q["serviceName"])?.let { ob.put("transport", it) }
        return ob.put("packet_encoding", "xudp")
    }

    private fun trojan(body: String, q: Map<String, String>): JSONObject {
        val (user, hp, _) = authority(body)
        val ob = JSONObject().put("type", "trojan").put("server", hp.host).put("server_port", hp.port).put("password", unquote(user))
        tls(q, hp.host, force = true)?.let { ob.put("tls", it) }
        transport(q["type"], q["host"], q["path"], q["serviceName"])?.let { ob.put("transport", it) }
        return ob
    }

    private fun vmess(body: String): Pair<JSONObject, String> {
        val d = try {
            JSONObject(b64(body))
        } catch (e: Exception) {
            throw KeyParseError("vmess-ключ не похож на base64 JSON")
        }
        val ob = JSONObject().put("type", "vmess").put("server", d.getString("add"))
            .put("server_port", d.get("port").toString().toInt()).put("uuid", d.getString("id"))
            .put("security", d.optString("scy").ifEmpty { "auto" })
            .put("alter_id", d.optString("aid").ifEmpty { "0" }.toInt())
        if (d.optString("tls") == "tls") {
            val q = mapOf("security" to "tls", "sni" to d.optString("sni").ifEmpty { d.optString("host") },
                "alpn" to d.optString("alpn"), "fp" to d.optString("fp")).filterValues { it.isNotEmpty() }
            tls(q, d.getString("add"))?.let { ob.put("tls", it) }
        }
        transport(d.optString("net"), d.optString("host"), d.optString("path"), d.optString("path"))?.let { ob.put("transport", it) }
        return ob to d.optString("ps")
    }

    private fun ss(bodyIn: String, q: Map<String, String>): JSONObject {
        if ("plugin" in q) throw KeyParseError("ss с плагином (obfs/v2ray-plugin) пока не поддерживается")
        val body = if ('@' !in bodyIn) b64(bodyIn) else bodyIn
        val at = body.lastIndexOf('@')
        val userinfo = body.substring(0, at)
        val creds = try {
            b64(userinfo).also { require(':' in it) }
        } catch (e: Exception) {
            unquote(userinfo)
        }
        val method = creds.substringBefore(':')
        val password = creds.substringAfter(':', "")
        if (method.isEmpty() || password.isEmpty()) throw KeyParseError("в ss-ключе нет метода или пароля")
        val hp = hostPort(body.substring(at + 1).trimEnd('/'))
        return JSONObject().put("type", "shadowsocks").put("server", hp.host).put("server_port", hp.port)
            .put("method", method).put("password", password)
    }

    private fun hy2(body: String, q: Map<String, String>): JSONObject {
        val (user, hp, _) = authority(body)
        val ob = JSONObject().put("type", "hysteria2").put("server", hp.host).put("server_port", hp.port)
            .put("password", unquote(user))
            .put("tls", JSONObject().put("enabled", true).put("server_name", q["sni"] ?: hp.host))
        if (truthy(q["insecure"])) ob.getJSONObject("tls").put("insecure", true)
        q["obfs"]?.takeIf { it.isNotEmpty() }?.let { ob.put("obfs", JSONObject().put("type", it).put("password", q["obfs-password"] ?: "")) }
        return ob
    }

    private fun tuic(body: String, q: Map<String, String>): JSONObject {
        val (user, hp, _) = authority(body)
        val tls = JSONObject().put("enabled", true).put("server_name", q["sni"] ?: hp.host)
            .put("alpn", JSONArray((q["alpn"] ?: "h3").split(",").filter { it.isNotEmpty() }))
        if (truthy(q["allow_insecure"] ?: q["insecure"])) tls.put("insecure", true)
        return JSONObject().put("type", "tuic").put("server", hp.host).put("server_port", hp.port)
            .put("uuid", unquote(user.substringBefore(':'))).put("password", unquote(user.substringAfter(':', "")))
            .put("congestion_control", q["congestion_control"] ?: "bbr")
            .put("udp_relay_mode", q["udp_relay_mode"] ?: "native")
            .put("tls", tls)
    }

    fun parseKey(uriIn: String): Key {
        val uri = uriIn.trim()
        val sep = uri.indexOf("://")
        val scheme = if (sep > 0) uri.substring(0, sep).lowercase() else ""
        if (scheme !in SCHEMES) throw KeyParseError("неизвестный формат ключа: ${uri.take(30)}…")
        val rest = uri.substring(sep + 3)
        val main = rest.substringBefore('#')
        var name = unquote(rest.substringAfter('#', ""))
        val ob = if (scheme == "vmess") {
            val (o, ps) = vmess(main)
            if (name.isEmpty()) name = ps
            o
        } else {
            val body = main.substringBefore('?')
            val q = query(main.substringAfter('?', ""))
            if (body.isEmpty()) throw KeyParseError("в ключе нет адреса сервера")
            when (scheme) {
                "ss" -> ss(body, q)
                "vless" -> vless(body, q)
                "trojan" -> trojan(body, q)
                "tuic" -> tuic(body, q)
                else -> hy2(body, q)
            }
        }
        ob.put("tag", "proxy")
        return Key(name.ifEmpty { "${ob.getString("type")} ${ob.getString("server")}" }, uri, ob)
    }

    /** Ключи из текста: по одному в строке, base64-подписка или JSON sing-box. */
    fun parseMany(textIn: String): Pair<List<Key>, List<String>> {
        var text = textIn.trim()
        if (text.startsWith("{")) return fromSingBoxJson(text) to emptyList()
        if ("://" !in text) {
            text = try {
                b64(text)
            } catch (e: Exception) {
                return emptyList<Key>() to listOf("текст не похож ни на ключ, ни на подписку")
            }
        }
        val keys = mutableListOf<Key>()
        val errors = mutableListOf<String>()
        for (raw in text.lines()) {
            val line = raw.trim()
            if (line.isEmpty() || line.startsWith("#")) continue
            try {
                keys += parseKey(line)
            } catch (e: Exception) {
                errors += "${line.take(40)}…: ${e.message}"
            }
        }
        return keys to errors
    }

    private fun fromSingBoxJson(text: String): List<Key> {
        val outbounds = JSONObject(text).optJSONArray("outbounds") ?: return emptyList()
        val types = setOf("vless", "vmess", "trojan", "shadowsocks", "hysteria2", "tuic", "wireguard")
        return (0 until outbounds.length()).map { outbounds.getJSONObject(it) }
            .filter { it.optString("type") in types }
            .map { ob -> Key(ob.optString("tag", ob.getString("type")), "", JSONObject(ob.toString()).put("tag", "proxy")) }
    }
}
