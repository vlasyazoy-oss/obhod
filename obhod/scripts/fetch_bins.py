"""Скачивает движки в bin/: sing-box и ByeDPI (ciadpi), только официальные релизы GitHub.

    py scripts/fetch_bins.py [--force]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.fetch import fetch  # noqa: E402

if __name__ == "__main__":
    fetch(force="--force" in sys.argv)
