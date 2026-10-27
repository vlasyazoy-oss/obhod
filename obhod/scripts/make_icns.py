"""Иконка .icns для macOS из эмблемы. Нужен Mac: собирает набор PNG и вызывает системный iconutil.

    python3 scripts/make_icns.py build-mac/Obhod.icns
"""
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import emblem  # noqa: E402


def main(out):
    from PIL import Image  # есть в requirements.txt

    work = tempfile.mkdtemp()
    try:
        big = os.path.join(work, "1024.png")
        emblem.write_png(big, 1024)  # рисуется один раз, остальные размеры — уменьшением
        iconset = os.path.join(work, "Obhod.iconset")
        os.makedirs(iconset)
        with Image.open(big) as src:
            for size in (16, 32, 128, 256, 512):
                for scale in (1, 2):
                    name = f"icon_{size}x{size}{'@2x' if scale == 2 else ''}.png"
                    src.resize((size * scale, size * scale), Image.LANCZOS).save(os.path.join(iconset, name))
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        subprocess.run(["iconutil", "-c", "icns", iconset, "-o", out], check=True)
        print("иконка:", out)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "build-mac/Obhod.icns")
