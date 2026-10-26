"""Проверяет настоящим sing-box (bin/sing-box.exe) конфиги, которые собирает Android-версия.

Сначала: cd android && gradlew testDebugUnitTest (тест ConfigTest сохранит их в android/app/build/singbox-configs).
    py scripts/check_android_configs.py
"""
import glob
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from core.engine import NO_WINDOW, SING_BOX  # noqa: E402

files = sorted(glob.glob(os.path.join(ROOT, "android", "app", "build", "singbox-configs", "*.json")))
if not files:
    sys.exit("конфигов нет — сначала запустите unit-тесты Android")
bad = 0
for path in files:
    r = subprocess.run([SING_BOX, "check", "-c", path], capture_output=True, creationflags=NO_WINDOW)
    ok = r.returncode == 0
    bad += not ok
    print(f"{'✓' if ok else '✗'} {os.path.basename(path)}" + ("" if ok else ": " + (r.stderr or r.stdout).decode(errors="replace").strip()))
print(f"\n{len(files) - bad} из {len(files)} приняты")
sys.exit(1 if bad else 0)
