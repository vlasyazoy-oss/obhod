"""Переводы: у каждой строки пять языков, одинаковые подстановки, а в коде нет ключей без перевода."""
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from core import config as cfg, i18n  # noqa: E402
from core.i18n import t  # noqa: E402

PLACEHOLDER = re.compile(r"%[sd]")


class Strings(unittest.TestCase):
    def tearDown(self):
        i18n.set_lang("ru")

    def test_every_string_has_all_languages_with_same_placeholders(self):
        for key, row in i18n.STRINGS.items():
            self.assertEqual(len(row), len(i18n.LANGS), key)
            want = PLACEHOLDER.findall(row[0])
            for code, text in zip(i18n.LANGS, row):
                self.assertTrue(text.strip(), f"{key}/{code} пустая")
                self.assertEqual(PLACEHOLDER.findall(text), want, f"{key}/{code}: подстановки не совпадают")

    def test_phrase_tables_have_all_languages(self):
        for row in i18n.STRATEGY_PHRASES + i18n.HOW_PHRASES:
            self.assertEqual(len(row), len(i18n.LANGS), row[0])

    def test_keys_used_in_code_exist(self):
        used = set()
        for folder in (ROOT, os.path.join(ROOT, "core")):
            for name in os.listdir(folder):
                if name.endswith(".py"):
                    with open(os.path.join(folder, name), encoding="utf-8") as f:
                        used |= set(re.findall(r"""\bt\(\s*["']([a-z_]*[a-z])["']""", f.read()))
        self.assertTrue(used)
        self.assertEqual(sorted(used - set(i18n.STRINGS)), [])

    def test_regions_strategies_and_notes_translate(self):
        regions = cfg.load_regions()
        i18n.set_lang("en")
        self.assertEqual(i18n.region("tr"), "Turkey")
        self.assertEqual(i18n.strategy("разрез TLS-записи по SNI"), "TLS record split at SNI")
        self.assertEqual(i18n.how("часовой пояс Turkey Standard Time"), "time zone Turkey Standard Time")
        self.assertTrue(cfg.region_note(regions["cn"]).startswith("In China"))
        self.assertEqual(cfg.region_note(regions["tr"]), "")
        for code in i18n.LANGS:
            i18n.set_lang(code)
            for region in regions:
                self.assertNotEqual(i18n.region(region), "region_" + region)
            for s in (s for r in regions.values() for s in r["strategies"]):
                if code != "ru":
                    self.assertNotRegex(i18n.strategy(s["name"]), "[а-яё]", f"{code}: {s['name']}")

    def test_formatting_and_fallback(self):
        i18n.set_lang("zh")
        self.assertEqual(t("log_keys_added", 3), "已添加密钥：3")
        self.assertEqual(t("no_such_key"), "no_such_key")
        self.assertEqual(i18n.set_lang("xx"), i18n.system_default())
        self.assertIn(i18n.system_default(), i18n.LANGS)

    def test_core_errors_follow_language(self):
        i18n.set_lang("tr")
        with self.assertRaises(cfg.ConfigError) as cm:
            cfg.build(cfg.load_regions()["ru"], "vpn")
        self.assertIn("anahtar", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
