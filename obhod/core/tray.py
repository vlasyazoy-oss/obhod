"""Значок в трее (pystray): иконка-эмблема с открытыми или закрытыми глазами и меню.

Обработчики вызываются из потока трея, поэтому приложение передаёт сюда функции, которые только кладут
событие в свою очередь, а не трогают tkinter напрямую.
"""
from . import emblem
from .osinfo import MAC

try:
    import pystray
    from PIL import Image
except ImportError:
    pystray = None


def available():
    # На macOS pystray требует главный поток, а его занимает окно tkinter — трея на Mac пока нет
    return pystray is not None and not MAC


def _icon_image(eyes_open):
    size = 64
    return Image.frombytes("RGB", (size, size), emblem.rgb(size, eyes_open=eyes_open))


class Tray:
    def __init__(self, on_show, on_toggle, on_quit):
        self.connected = False
        self._images = {True: _icon_image(True), False: _icon_image(False)}
        menu = pystray.Menu(
            pystray.MenuItem("Показать окно", lambda: on_show(), default=True),  # default — двойной клик по значку
            pystray.MenuItem(lambda item: "Отключить" if self.connected else "Подключить", lambda: on_toggle()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Выход", lambda: on_quit()),
        )
        self.icon = pystray.Icon("obhod", self._images[False], "Обход: не подключено", menu)

    def start(self):
        self.icon.run_detached()

    def set_state(self, connected, text):
        self.connected = connected
        self.icon.icon = self._images[connected]
        self.icon.title = f"Обход: {text}"[:127]  # ограничение подсказки в Windows
        self.icon.update_menu()

    def notify(self, message):
        try:
            self.icon.notify(message, "Обход")
        except (NotImplementedError, OSError):
            pass

    def stop(self):
        self.icon.stop()
