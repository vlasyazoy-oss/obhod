#!/bin/bash
# Сборка Obhod.app для macOS. Запускать на Mac из папки obhod/:
#     bash scripts/build_macos.sh
# Результат: dist-mac/Obhod.app и архив dist-mac/Obhod-macos-<arm64|x86_64>.zip для передачи другим.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"

python3 -c 'import tkinter' 2>/dev/null || {
    echo "В этом Python нет tkinter. Поставьте Python с python.org (в нём есть Tk) или: brew install python-tk"
    exit 1
}

python3 -m venv .venv-mac
source .venv-mac/bin/activate
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt pyinstaller

python scripts/make_icns.py "$ROOT/build-mac/Obhod.icns"

# Пути абсолютные: PyInstaller считает относительные пути от папки со spec-файлом (build-mac)
pyinstaller --noconfirm --windowed --name Obhod \
    --osx-bundle-identifier org.obhod.app \
    --icon "$ROOT/build-mac/Obhod.icns" \
    --add-data "$ROOT/core/regions.json:core" \
    --distpath "$ROOT/dist-mac" --workpath "$ROOT/build-mac/work" --specpath "$ROOT/build-mac" \
    app.py

ARCH="$(uname -m)"
rm -f "dist-mac/Obhod-macos-$ARCH.zip"
ditto -c -k --keepParent dist-mac/Obhod.app "dist-mac/Obhod-macos-$ARCH.zip"
echo
echo "Готово: dist-mac/Obhod.app и dist-mac/Obhod-macos-$ARCH.zip"
echo "Проверка без окон: dist-mac/Obhod.app/Contents/MacOS/Obhod --selftest"
echo "Отчёт:             ~/Library/Application Support/Obhod/data/selftest.txt"
