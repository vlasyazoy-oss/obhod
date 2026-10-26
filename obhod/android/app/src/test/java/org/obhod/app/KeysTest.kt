package org.obhod.app

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.Base64

// Те же случаи, что в tests/test_keys.py: адреса из документационных диапазонов, UUID и пароли выдуманы
class KeysTest {
    private val uuid = "b831381d-6324-4d53-ad4f-8cda48b30811"

    @Test fun vlessReality() {
        val k = Keys.parseKey("vless://$uuid@203.0.113.5:443?type=tcp&security=reality&pbk=PUBKEY&sid=ab12" +
            "&sni=www.microsoft.com&fp=chrome&flow=xtls-rprx-vision&encryption=none#%D0%9C%D0%BE%D0%B9%20%D1%81%D0%B5%D1%80%D0%B2%D0%B5%D1%80")
        val ob = k.outbound
        assertEquals("Мой сервер", k.name)
        assertEquals("vless", ob.getString("type"))
        assertEquals("203.0.113.5", ob.getString("server"))
        assertEquals(443, ob.getInt("server_port"))
        assertEquals(uuid, ob.getString("uuid"))
        assertEquals("xtls-rprx-vision", ob.getString("flow"))
        val reality = ob.getJSONObject("tls").getJSONObject("reality")
        assertEquals("PUBKEY", reality.getString("public_key"))
        assertEquals("ab12", reality.getString("short_id"))
        assertEquals("chrome", ob.getJSONObject("tls").getJSONObject("utls").getString("fingerprint"))
        assertFalse(ob.has("transport"))
        assertEquals("proxy", ob.getString("tag"))
    }

    @Test fun vlessWsTls() {
        val ob = Keys.parseKey("vless://$uuid@example.com:443?type=ws&security=tls&path=%2Fws&host=cdn.example.com").outbound
        val t = ob.getJSONObject("transport")
        assertEquals("ws", t.getString("type"))
        assertEquals("/ws", t.getString("path"))
        assertEquals("cdn.example.com", t.getJSONObject("headers").getString("Host"))
    }

    @Test fun ipv6Host() {
        val ob = Keys.parseKey("trojan://pw@[2001:db8::1]:443#v6").outbound
        assertEquals("2001:db8::1", ob.getString("server"))
    }

    @Test fun realityWithoutPbkIsRejected() {
        assertThrows(Keys.KeyParseError::class.java) { Keys.parseKey("vless://$uuid@198.51.100.1:443?security=reality&sni=a.com") }
    }

    @Test fun unsupportedTransport() {
        assertThrows(Keys.KeyParseError::class.java) { Keys.parseKey("vless://$uuid@198.51.100.1:443?type=xhttp&security=tls") }
    }

    @Test fun vmess() {
        val body = Base64.getEncoder().encodeToString(JSONObject(mapOf("v" to "2", "ps" to "vm", "add" to "198.51.100.7",
            "port" to "8443", "id" to uuid, "aid" to "0", "scy" to "auto", "net" to "grpc", "path" to "svc",
            "tls" to "tls", "sni" to "s.example.com")).toString().toByteArray())
        val k = Keys.parseKey("vmess://$body")
        assertEquals("vm", k.name)
        assertEquals(8443, k.outbound.getInt("server_port"))
        assertEquals("svc", k.outbound.getJSONObject("transport").getString("service_name"))
        assertEquals("s.example.com", k.outbound.getJSONObject("tls").getString("server_name"))
    }

    @Test fun ssSip002AndLegacy() {
        val ui = Base64.getUrlEncoder().withoutPadding().encodeToString("chacha20-ietf-poly1305:pass123".toByteArray())
        val a = Keys.parseKey("ss://$ui@198.51.100.2:8388#ss").outbound
        assertEquals("chacha20-ietf-poly1305", a.getString("method"))
        assertEquals("pass123", a.getString("password"))
        val b = Keys.parseKey("ss://2022-blake3-aes-128-gcm:YWJjZGVmZ2hpamtsbW5vcA%3D%3D@198.51.100.2:443").outbound
        assertEquals("YWJjZGVmZ2hpamtsbW5vcA==", b.getString("password"))
        val whole = Base64.getEncoder().encodeToString("aes-256-gcm:pw@198.51.100.3:1234".toByteArray())
        val c = Keys.parseKey("ss://$whole#old").outbound
        assertEquals(1234, c.getInt("server_port"))
    }

    @Test fun hysteria2AndTuic() {
        val h = Keys.parseKey("hy2://pw@203.0.113.9:443?sni=h.example.com&obfs=salamander&obfs-password=x&insecure=1").outbound
        assertEquals("salamander", h.getJSONObject("obfs").getString("type"))
        assertTrue(h.getJSONObject("tls").getBoolean("insecure"))
        val t = Keys.parseKey("tuic://$uuid:pw@203.0.113.9:443?congestion_control=bbr&alpn=h3&sni=t.example.com").outbound
        assertEquals("pw", t.getString("password"))
        assertEquals("h3", t.getJSONObject("tls").getJSONArray("alpn").getString(0))
    }

    @Test fun garbage() {
        for (bad in listOf("hello", "http://example.com", "vless://", "vless://uuid@host")) {
            assertThrows(IllegalArgumentException::class.java) { Keys.parseKey(bad) }
        }
    }

    @Test fun base64SubscriptionWithBadLine() {
        val text = listOf("vless://$uuid@198.51.100.1:443?security=tls#a", "junk://x", "trojan://p@h.example:443#b").joinToString("\n")
        val (found, errors) = Keys.parseMany(Base64.getEncoder().encodeToString(text.toByteArray()))
        assertEquals(listOf("a", "b"), found.map { it.name })
        assertEquals(1, errors.size)
    }
}
