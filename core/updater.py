"""Автооновлення через GitHub Releases.

Як працює: програма раз на кілька годин питає GitHub «яка остання версія?».
Якщо там новіша — показує повідомлення. «Оновити» → скачує новий WidgetDesk.exe у тимчасову папку,
маленький .bat чекає, поки програма закриється, ставить новий файл на місце старого і запускає його.
Налаштування і віджети лежать окремо (у %APPDATA%), тому оновлення їх не чіпає."""

import json
import os
import subprocess
import sys
import tempfile
import threading
import urllib.request

from PyQt6.QtCore import QObject, pyqtSignal

from core.version import EXE_NAME, UPDATE_REPO, VERSION


def parse(v):
    v = (v or "").strip().lstrip("vV")
    out = []
    for part in v.split("."):
        num = "".join(ch for ch in part if ch.isdigit())
        out.append(int(num) if num else 0)
    return tuple(out + [0] * (3 - len(out)))


def is_frozen():
    return bool(getattr(sys, "frozen", False))


class Updater(QObject):
    available = pyqtSignal(str, str, str)      # версія, що нового, посилання на exe
    up_to_date = pyqtSignal()
    failed = pyqtSignal(str)
    progress = pyqtSignal(int)                 # 0..100
    downloaded = pyqtSignal(str)               # шлях до скачаного файлу

    def __init__(self):
        super().__init__()
        self.release_page = f"https://github.com/{UPDATE_REPO}/releases/latest" if UPDATE_REPO else ""

    def enabled(self):
        return bool(UPDATE_REPO)

    def check(self):
        if not UPDATE_REPO:
            self.failed.emit("Не вказано репозиторій для оновлень (core/version.py → UPDATE_REPO)")
            return

        def run():
            try:
                url = f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest"
                req = urllib.request.Request(url, headers={"User-Agent": "WidgetDesk-updater",
                                                           "Accept": "application/vnd.github+json"})
                with urllib.request.urlopen(req, timeout=15) as r:
                    data = json.loads(r.read().decode("utf-8"))
                tag = data.get("tag_name", "")
                asset = next((a for a in data.get("assets", []) if a.get("name", "").lower() == EXE_NAME.lower()),
                             None) or next((a for a in data.get("assets", [])
                                            if a.get("name", "").lower().endswith(".exe")), None)
                if parse(tag) > parse(VERSION) and asset:
                    self.available.emit(tag.lstrip("vV"), (data.get("body") or "").strip(),
                                        asset["browser_download_url"])
                else:
                    self.up_to_date.emit()
            except Exception as e:
                self.failed.emit(str(e))
        threading.Thread(target=run, daemon=True).start()

    def download(self, url):
        def run():
            try:
                dst = os.path.join(tempfile.gettempdir(), "WidgetDesk_update.exe")
                req = urllib.request.Request(url, headers={"User-Agent": "WidgetDesk-updater"})
                with urllib.request.urlopen(req, timeout=60) as r, open(dst, "wb") as f:
                    total = int(r.headers.get("Content-Length") or 0)
                    got = 0
                    while True:
                        chunk = r.read(256 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        got += len(chunk)
                        if total:
                            self.progress.emit(int(got * 100 / total))
                if os.path.getsize(dst) < 1_000_000:          # exe точно більший за 1 МБ — інакше щось не те
                    raise RuntimeError("скачаний файл пошкоджений")
                self.downloaded.emit(dst)
            except Exception as e:
                self.failed.emit(str(e))
        threading.Thread(target=run, daemon=True).start()


def install_and_restart(new_exe):
    """Запустити заміну файлу і перезапуск. Після цього програма має закритись."""
    cur = sys.executable
    pid = os.getpid()
    bat = os.path.join(tempfile.gettempdir(), "WidgetDesk_update.bat")
    with open(bat, "w", encoding="utf-8") as f:
        f.write("@echo off\r\n"
                "chcp 65001 >nul\r\n"
                ":wait\r\n"
                "timeout /t 1 /nobreak >nul\r\n"
                f'tasklist /fi "PID eq {pid}" | find "{pid}" >nul && goto wait\r\n'
                f'move /y "{new_exe}" "{cur}" >nul\r\n'
                f'start "" "{cur}"\r\n'
                'del "%~f0"\r\n')
    subprocess.Popen(["cmd", "/c", bat], creationflags=0x08000000)   # CREATE_NO_WINDOW — без чорного вікна
