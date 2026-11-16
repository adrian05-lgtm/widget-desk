"""Журнал помилок у файл + вікно «Сталася помилка» замість тихого падіння."""

import datetime
import sys
import traceback

from core import config
from core.version import VERSION

MAX_BYTES = 512 * 1024
_shown = {"n": 0}


def write(text):
    try:
        config.ensure_dir()
        if config.LOG_FILE.exists() and config.LOG_FILE.stat().st_size > MAX_BYTES:
            config.LOG_FILE.replace(config.LOG_FILE.with_suffix(".old.txt"))
        with open(config.LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] v{VERSION}  {text}\n")
    except OSError:
        pass


def _hook(etype, value, tb):
    text = "".join(traceback.format_exception(etype, value, tb))
    write("ПОМИЛКА\n" + text)
    try:
        sys.__stderr__.write(text)
    except Exception:
        pass
    _shown["n"] += 1
    if _shown["n"] > 3:                      # не засипати екран вікнами, якщо помилка повторюється
        return
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox
        if QApplication.instance() is None:
            return
        box = QMessageBox()
        box.setWindowTitle("WidgetDesk — сталася помилка")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText("Щось пішло не так, але програма працює далі.\n\n"
                    f"Подробиці записано у файл:\n{config.LOG_FILE}\n\nСкинь цей файл Claude.")
        box.setDetailedText(text)
        box.exec()
    except Exception:
        pass


def install():
    sys.excepthook = _hook
    write("запуск")
