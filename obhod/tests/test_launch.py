"""QR-импорт, автозапуск, иконки трея."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import autostart, emblem, keys, qr, tray  # noqa: E402

VLESS = ("vless://b831381d-6324-4d53-ad4f-8cda48b30811@203.0.113.5:443?type=tcp&security=reality"
         "&pbk=jNXHt1yRo0vDuchQlIP6Z0ZvjT3KtzVI-T4E7RoLJS0&sid=ab12&sni=www.microsoft.com&fp=chrome#QR-ключ")
TROJAN = "trojan://secret@example.org:443?sni=example.org#второй"


@unittest.skipUnless(qr.available(), "нет Pillow/zxing-cpp")
class QR(unittest.TestCase):
    def test_key_survives_qr_round_trip(self):
        texts = qr.decode(qr.to_image(VLESS))
        self.assertEqual(texts, [VLESS])
        found, errors = keys.parse_many(texts[0])
        self.assertEqual((found[0].name, errors), ("QR-ключ", []))

    def test_two_codes_on_one_screenshot(self):
        from PIL import Image
        a, b = qr.to_image(VLESS, 4), qr.to_image(TROJAN, 4)
        canvas = Image.new("L", (a.width + b.width + 120, max(a.height, b.height) + 80), 255)
        canvas.paste(a, (30, 40))
        canvas.paste(b, (a.width + 90, 40))
        self.assertEqual(sorted(qr.decode(canvas)), sorted([VLESS, TROJAN]))

    def test_from_file_and_empty_picture(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "key.png")
            qr.to_image(TROJAN).save(path)
            self.assertEqual(qr.from_file(path), [TROJAN])
            blank = os.path.join(d, "blank.png")
            Image.new("RGB", (200, 200), "white").save(blank)
            self.assertEqual(qr.from_file(blank), [])

    def test_screen_capture_runs(self):
        self.assertIsInstance(qr.from_screen(), list)


class Autostart(unittest.TestCase):
    def test_command_uses_pythonw_and_tray_flag(self):
        cmd = autostart.command()
        self.assertTrue(cmd.endswith('app.py" --tray'), cmd)
        self.assertIn("pythonw.exe", cmd.lower())

    def test_enable_disable_round_trip_restores_previous_value(self):
        before = autostart.current()
        try:
            autostart.enable()
            self.assertEqual(autostart.current(), autostart.command())
            autostart.disable()
            self.assertFalse(autostart.is_enabled())
        finally:
            if before is not None:
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, autostart.RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
                    winreg.SetValueEx(k, autostart.NAME, 0, winreg.REG_SZ, before)


class Icons(unittest.TestCase):
    def test_open_and_closed_eyes_differ(self):
        opened, closed = emblem.rgb(32, eyes_open=True), emblem.rgb(32, eyes_open=False)
        self.assertEqual(len(opened), 32 * 32 * 3)
        self.assertNotEqual(opened, closed)

    @unittest.skipUnless(tray.available(), "нет pystray")
    def test_tray_menu_items_call_handlers(self):
        calls = []
        t = tray.Tray(on_show=lambda: calls.append("show"), on_toggle=lambda: calls.append("toggle"),
                      on_quit=lambda: calls.append("quit"))
        self.assertEqual(t.icon.title, "Обход: не подключено")
        items = [i for i in t.icon.menu.items if i is not tray.pystray.Menu.SEPARATOR]
        self.assertEqual([i.text for i in items], ["Показать окно", "Подключить", "Выход"])
        self.assertTrue(items[0].default, "двойной клик по значку должен открывать окно")
        for item in items:
            item(t.icon)
        self.assertEqual(calls, ["show", "toggle", "quit"])
        t.connected = True
        self.assertEqual(items[1].text, "Отключить")


if __name__ == "__main__":
    unittest.main()
