package org.obhod.app

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

class ConfigTest {
    private val regions = JSONObject(File("../../core/regions.json").readText())
    private fun region(code: String) = regions.getJSONObject(code)
    private val proxy = JSONObject().put("type", "trojan").put("tag", "x").put("server", "198.51.100.1")
        .put("server_port", 443).put("password", "p").put("tls", JSONObject().put("enabled", true).put("server_name", "a.example"))

    private fun rules(c: JSONObject): List<JSONObject> = c.getJSONObject("route").getJSONArray("rules").let { a ->
        (0 until a.length()).map { a.getJSONObject(it) }
    }

    private fun to(c: JSONObject, tag: String) = rules(c).filter { it.optString("outbound") == tag }

    private fun tags(c: JSONObject) = c.getJSONArray("outbounds").let { a -> (0 until a.length()).map { a.getJSONObject(it).getString("tag") } }

    @Test fun dpiModeNeedsNoKey() {
        val c = Config.build(region("ru"), "dpi", null)
        assertEquals("direct", c.getJSONObject("route").getString("final"))
        assertEquals(listOf("direct", "dpi"), tags(c))
        assertTrue(to(c, "dpi")[0].getJSONArray("domain_suffix").toString().contains("youtube.com"))
    }

    @Test fun dnsFromVpnIsHijacked() {
        val c = Config.build(region("tr"), "dpi", null)
        assertTrue(rules(c).any { it.optString("action") == "hijack-dns" })
        val servers = c.getJSONObject("dns").getJSONArray("servers")
        assertFalse("на Android нет системного резолвера для sing-box",
            (0 until servers.length()).any { servers.getJSONObject(it).getString("type") == "local" })
    }

    @Test fun keyRequiredForVpnAndHybrid() {
        for (mode in listOf("vpn", "hybrid")) {
            assertThrows(Config.ConfigError::class.java) { Config.build(region("ru"), mode, null) }
        }
    }

    @Test fun chinaRefusesDpi() {
        val e = assertThrows(Config.ConfigError::class.java) { Config.build(region("cn"), "dpi", null) }
        assertTrue(e.message!!.contains("ключ"))
    }

    @Test fun hybridRoutesThreeWays() {
        val c = Config.build(region("ru"), "hybrid", proxy)
        assertTrue(to(c, "proxy")[0].getJSONArray("domain_suffix").toString().contains("chatgpt.com"))
        assertTrue(to(c, "dpi")[0].getJSONArray("domain_suffix").toString().contains("discord.com"))
        assertFalse("исходный outbound не должен меняться", proxy.getJSONObject("tls").has("fragment"))
    }

    @Test fun byedpiArgs() {
        val s = region("tr").getJSONArray("strategies").getJSONObject(0)
        assertEquals(listOf("--ip", "127.0.0.1", "--port", "1080"), Config.byedpiArgs(s).take(4))
    }

    /** Все конфиги в build/singbox-configs: их проверяет настоящий sing-box (scripts/check_android_configs.py). */
    @Test fun dumpAllConfigsForSingBoxCheck() {
        val out = File("build/singbox-configs").apply { deleteRecursively(); mkdirs() }
        var n = 0
        for (code in regions.keys()) {
            val r = region(code)
            for (mode in Config.MODES.keys) {
                if (mode != "vpn" && !r.getBoolean("dpi_supported")) continue
                for (dpiAll in listOf(false, true)) {
                    val c = Config.build(r, mode, if (mode == "dpi") null else proxy, dpiAll)
                    File(out, "$code-$mode-${if (dpiAll) "all" else "list"}.json").writeText(c.toString(2))
                    n++
                }
            }
        }
        assertTrue(n >= 20)
        File(out, "tunnel.yml").writeText(Config.tunnelYaml())
    }
}
