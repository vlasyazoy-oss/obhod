"""Значок в трее (pystray): иконка-эмблема с открытыми или закрытыми глазами и меню.

Обработчики вызываются из потока трея, поэтому приложение передаёт сюда функции, которые только кладут
событие в свою очередь, а не трогают tkinter напрямую.
"""
from . import emblem
from .i18n import t

try:
    import pystray
    from PIL import Image
except ImportError:
    pystray = None


def available():
    return pystray is not None


def _icon_image(eyes_open):
    size = 64
    return Image.frombytes("RGB", (size, size), emblem.rgb(size, eyes_open=eyes_open))


class Tray:
    def __init__(self, on_show, on_toggle, on_quit):
        self.connected = False
        self._images = {True: _icon_image(True), False: _icon_image(False)}
        menu = pystray.Menu(
            # Подписи — функции: меню собирается заново после смены языка (update_menu)
            pystray.MenuItem(lambda item: t("tray_show"), lambda: on_show(), default=True),  # default — двойной клик
            pystray.MenuItem(lambda item: t("tray_disconnect" if self.connected else "tray_connect"), lambda: on_toggle()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(lambda item: t("tray_quit"), lambda: on_quit()),
        )
        self.icon = pystray.Icon("obhod", self._images[False], f"{t('app')}: {t('tray_off')}", menu)

    def start(self):
        self.icon.run_detached()

    def set_state(self, connected, text):
        self.connected = connected
        self.icon.icon = self._images[connected]
        self.icon.title = f"{t('app')}: {text}"[:127]  # ограничение подсказки в Windows
        self.icon.update_menu()

    def notify(self, message):
        try:
            self.icon.notify(message, t("app"))
        except (NotImplementedError, OSError):
            pass

    def stop(self):
        self.icon.stop()
