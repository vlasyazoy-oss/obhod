package org.obhod.app

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/** Регионы из assets и настройки пользователя (SharedPreferences). Аналог core/state.py. */
class Store(private val context: Context) {
    private val prefs = context.getSharedPreferences("obhod", Context.MODE_PRIVATE)

    val regions: JSONObject by lazy {
        JSONObject(context.assets.open("regions.json").bufferedReader(Charsets.UTF_8).use { it.readText() })
    }

    /** Язык интерфейса; по умолчанию язык телефона, если он есть в I18n.LANGS, иначе английский. */
    var lang: String
        get() = prefs.getString("lang", null) ?: I18n.systemDefault()
        set(v) = prefs.edit().putString("lang", v).apply()

    var region: String
        get() = prefs.getString("region", "auto")!!
        set(v) = prefs.edit().putString("region", v).apply()

    /** Пусто — режим по умолчанию для региона. */
    var mode: String
        get() = prefs.getString("mode", "")!!
        set(v) = prefs.edit().putString("mode", v).apply()

    var keys: JSONArray
        get() = JSONArray(prefs.getString("keys", "[]"))
        set(v) = prefs.edit().putString("keys", v.toString()).apply()

    var selectedKey: Int
        get() = prefs.getInt("selected_key", 0)
        set(v) = prefs.edit().putInt("selected_key", v).apply()

    var dpiAll: Boolean
        get() = prefs.getBoolean("dpi_all", false)
        set(v) = prefs.edit().putBoolean("dpi_all", v).apply()

    fun strategyId(regionCode: String): String? = prefs.getString("strategy_$regionCode", null)
    fun setStrategyId(regionCode: String, id: String) = prefs.edit().putString("strategy_$regionCode", id).apply()

    fun regionCode(): String = if (region == "auto") Region.detect(context).first else region
    fun currentRegion(): JSONObject = regions.getJSONObject(regionCode())

    fun currentKey(): JSONObject? = keys.let { k -> if (selectedKey in 0 until k.length()) k.getJSONObject(selectedKey) else null }

    /** Выбор пользователя, если он выполним; иначе режим по умолчанию. */
    fun effectiveMode(): String {
        val r = currentRegion()
        var m = mode.ifEmpty { Config.defaultMode(r, keys.length() > 0) }
        if ((m == "dpi" || m == "hybrid") && !r.getBoolean("dpi_supported")) m = "vpn"
        if ((m == "vpn" || m == "hybrid") && keys.length() == 0 && r.getBoolean("dpi_supported")) m = "dpi"
        return m
    }

    fun strategy(): JSONObject? {
        val list = currentRegion().getJSONArray("strategies")
        if (list.length() == 0) return null
        val wanted = strategyId(regionCode())
        return (0 until list.length()).map { list.getJSONObject(it) }.firstOrNull { it.getString("id") == wanted } ?: list.getJSONObject(0)
    }

    fun addKeys(found: List<Keys.Key>) {
        val arr = keys
        val first = arr.length()
        found.forEach { arr.put(JSONObject().put("name", it.name).put("uri", it.uri).put("outbound", it.outbound)) }
        keys = arr
        if (found.isNotEmpty()) selectedKey = first
    }

    fun deleteKey(index: Int) {
        val arr = keys
        if (index in 0 until arr.length()) arr.remove(index)
        keys = arr
        selectedKey = 0
    }
}
