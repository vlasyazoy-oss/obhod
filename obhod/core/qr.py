"""Чтение ключей из QR-кодов: с экрана, из файла картинки, из картинки в буфере обмена.

Нужны Pillow и zxing-cpp (py -m pip install --user -r requirements.txt). Без них available() == False.
"""
from .osinfo import MAC

try:
    import zxingcpp
    from PIL import Image, ImageGrab
except ImportError:  # приложение работает и без QR
    zxingcpp = None


class QRError(RuntimeError):
    pass


def available():
    return zxingcpp is not None


def _need():
    if not available():
        raise QRError("Для QR нужны библиотеки: py -m pip install --user -r requirements.txt")


def decode(image):
    """Все QR-коды на картинке, текстом, без повторов и в порядке нахождения."""
    _need()
    found = []
    for b in zxingcpp.read_barcodes(image.convert("RGB"), formats=zxingcpp.BarcodeFormat.QRCode):
        if b.valid and b.text and b.text not in found:
            found.append(b.text)
    return found


def from_screen():
    """Снимок всех мониторов. Окно приложения перед этим нужно убрать, чтобы не мешало."""
    _need()
    # all_screens есть только в Windows; на macOS снимается основной экран, и нужно разрешение
    # «Запись экрана» (Системные настройки → Конфиденциальность), иначе снимок будет пустым
    return decode(ImageGrab.grab(all_screens=True) if not MAC else ImageGrab.grab())


def from_file(path):
    _need()
    with Image.open(path) as img:
        return decode(img)


def from_clipboard():
    """QR из картинки в буфере обмена (скриншот или скопированный файл). None — картинки в буфере нет."""
    _need()
    data = ImageGrab.grabclipboard()
    if data is None:
        return None
    if isinstance(data, list):  # скопированы файлы
        texts = []
        for path in data:
            try:
                texts += from_file(path)
            except OSError:
                pass
        return texts
    return decode(data)


def to_image(text, scale=6):
    """QR для текста (для тестов и «поделиться ключом»)."""
    _need()
    barcode = zxingcpp.create_barcode(text, zxingcpp.BarcodeFormat.QRCode)
    return Image.fromarray(barcode.to_image(scale=scale))
