package org.obhod.app

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

class I18nTest {
    private val keysUsed by lazy {
        // Все ключи t("…") в исходниках экрана и службы
        val src = File("src/main/java/org/obhod/app").listFiles()!!.filter { it.extension == "kt" }.joinToString("\n") { it.readText() }
        Regex("""\bt\("([a-z_]+)"""").findAll(src).map { it.groupValues[1] }.toSet()
    }

    @Test fun everyUsedKeyIsTranslatedToEveryLanguage() {
        for (lang in I18n.LANGS.keys) {
            I18n.lang = lang
            for (key in keysUsed) {
                assertTrue("$lang: нет перевода «$key»", I18n.t(key) != key)
            }
        }
    }

    @Test fun regionsModesAndNotesExistInEveryLanguage() {
        val regions = JSONObject(File("../../core/regions.json").readText())
        for (lang in I18n.LANGS.keys) {
            I18n.lang = lang
            for (code in regions.keys()) {
                assertTrue("$lang/$code", I18n.region(code) != "region_$code")
                if (regions.getJSONObject(code).optString("dpi_note").isNotEmpty()) assertTrue(I18n.t("note_$code") != "note_$code")
            }
            for (m in Config.MODES.keys) {
                assertTrue(I18n.mode(m) != "mode_$m")
                assertTrue(I18n.t("mode_${m}_desc") != "mode_${m}_desc")
            }
        }
    }

    @Test fun strategyNamesLoseCyrillicOutsideRussian() {
        val regions = JSONObject(File("../../core/regions.json").readText())
        val names = regions.keys().asSequence().flatMap { code ->
            val a = regions.getJSONObject(code).getJSONArray("strategies")
            (0 until a.length()).map { a.getJSONObject(it).getString("name") }
        }.toSet()
        for (lang in listOf("en", "tr", "fa", "zh")) {
            I18n.lang = lang
            for (n in names) assertFalse("$lang: «${I18n.strategy(n)}»", Regex("[а-яё]", RegexOption.IGNORE_CASE).containsMatchIn(I18n.strategy(n)))
        }
    }

    @Test fun formatArguments() {
        I18n.lang = "en"
        assertEquals("Connected · Turkey · Hybrid", I18n.t("status_connected", "Turkey · Hybrid"))
        assertTrue(I18n.rtl.not())
        I18n.lang = "fa"
        assertTrue(I18n.rtl)
        I18n.lang = "ru"
    }
}
