package org.obhod.app

import android.content.Context
import android.telephony.TelephonyManager
import java.util.Locale
import java.util.TimeZone

/** Регион без сети: страна SIM-карты, потом страна сети, часовой пояс, язык. */
object Region {
    private val COUNTRIES = setOf("ru", "tr", "ir", "cn")
    private val ZONES = mapOf("Europe/Istanbul" to "tr", "Asia/Istanbul" to "tr", "Asia/Tehran" to "ir",
        "Asia/Shanghai" to "cn", "Asia/Urumqi" to "cn", "Asia/Chongqing" to "cn", "Asia/Harbin" to "cn")
    private val LANGS = mapOf("ru" to "ru", "tr" to "tr", "fa" to "ir", "zh" to "cn")

    fun fromCountry(iso: String?): String? = iso?.lowercase()?.takeIf { it in COUNTRIES }

    fun fromZone(id: String): String? = ZONES[id] ?: if (id.startsWith("Europe/Moscow") || id in RUSSIAN_ZONES) "ru" else null

    private val RUSSIAN_ZONES = setOf("Europe/Kaliningrad", "Europe/Samara", "Europe/Volgograd", "Europe/Saratov",
        "Europe/Ulyanovsk", "Europe/Astrakhan", "Europe/Kirov", "Asia/Yekaterinburg", "Asia/Omsk", "Asia/Novosibirsk",
        "Asia/Barnaul", "Asia/Tomsk", "Asia/Novokuznetsk", "Asia/Krasnoyarsk", "Asia/Irkutsk", "Asia/Chita",
        "Asia/Yakutsk", "Asia/Khandyga", "Asia/Vladivostok", "Asia/Ust-Nera", "Asia/Magadan", "Asia/Sakhalin",
        "Asia/Srednekolymsk", "Asia/Kamchatka", "Asia/Anadyr")

    /** (код региона, откуда узнали) */
    fun detect(context: Context): Pair<String, String> {
        val tm = context.getSystemService(TelephonyManager::class.java)
        fromCountry(tm?.simCountryIso)?.let { return it to "страна SIM-карты" }
        fromCountry(tm?.networkCountryIso)?.let { return it to "страна сотовой сети" }
        val zone = TimeZone.getDefault().id
        fromZone(zone)?.let { return it to "часовой пояс $zone" }
        LANGS[Locale.getDefault().language]?.let { return it to "язык системы ${Locale.getDefault().toLanguageTag()}" }
        return "other" to "не удалось определить"
    }
}
