"""Пише release\\build_info.txt: версія, час, розмір і SHA-256 зібраного exe.
Перед публікацією Claude звіряє розмір/хеш із цим файлом (а не час зміни файлу)."""

import datetime
import hashlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from core.version import EXE_NAME, VERSION  # noqa: E402

exe = sys.argv[1]
reported = sys.argv[2].strip() if len(sys.argv) > 2 else ""
h = hashlib.sha256()
with open(exe, "rb") as f:
    for chunk in iter(lambda: f.read(1 << 20), b""):
        h.update(chunk)
size = os.path.getsize(exe)
ok = reported == VERSION
out = os.path.join(os.path.dirname(exe), "build_info.txt")
with open(out, "w", encoding="utf-8") as f:
    f.write(f"file: {EXE_NAME}\nversion: {VERSION}\nexe_reports: {reported or '?'}\n"
            f"built: {datetime.datetime.now():%Y-%m-%d %H:%M:%S} (local time)\n"
            f"size: {size}\nsha256: {h.hexdigest()}\n")
print(f"version {VERSION}, exe reports {reported or '?'}, size {size}")
sys.exit(0 if ok else 3)
