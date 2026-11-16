"""WidgetDesk — робочий стіл із віджетів.
Запуск:  python desk.py   (з папки desk)"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.version import APP_NAME, VERSION

if "--version" in sys.argv:                      # для перевірки зібраного exe (у нього немає консолі)
    with open(os.path.join(tempfile.gettempdir(), "WidgetDesk_version.txt"), "w", encoding="utf-8") as f:
        f.write(VERSION)
    sys.exit(0)

from PyQt6.QtCore import QLoggingCategory, QObject, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from core import config, log, platform_win
from core.clock import FrameClock
from core.updater import Updater, install_and_restart, is_frozen
from ui import theme
from ui.app_windows import SettingsWindow, UpdateDialog

SERVER_NAME = "WidgetDesk_single_instance"


class App(QObject):
    """Головний керівник: налаштування, трей, годинник кадрів, оновлення."""

    def __init__(self, qapp):
        super().__init__()
        self.qapp = qapp
        self.st = config.load()
        self.clock = FrameClock(self.st["fps"], self)
        self.settings_win = None
        self.upd_dlg = None
        self.upd_manual = False
        self.upd_url = ""

        self.tray = QSystemTrayIcon(theme.app_icon(), self)
        self.tray.setToolTip(f"WidgetDesk {VERSION}")
        self.menu = QMenu()
        self.menu.aboutToShow.connect(self.build_menu)
        self.build_menu()
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(lambda r: self.open_settings()
                                    if r == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray.show()

        self.watch = QTimer(self)                       # раз на секунду: чи не пора на паузу
        self.watch.timeout.connect(self.check_pause)
        self.watch.start(1000)

        self.updater = Updater()
        self.updater.available.connect(self.on_update_available)
        self.updater.up_to_date.connect(self.on_up_to_date)
        self.updater.failed.connect(self.on_update_failed)
        self.updater.progress.connect(lambda p: self.upd_dlg and self.upd_dlg.set_progress(p))
        self.updater.downloaded.connect(self.on_update_downloaded)
        self.upd_timer = QTimer(self)
        self.upd_timer.timeout.connect(lambda: self.check_updates(False))
        self.upd_timer.start(6 * 3600 * 1000)
        QTimer.singleShot(15000, lambda: self.check_updates(False))

    # ---------------- меню в треї ----------------
    def build_menu(self):
        m = self.menu
        m.clear()

        def add(text, fn, checked=None):
            a = QAction(text, m)
            if checked is not None:
                a.setCheckable(True)
                a.setChecked(bool(checked))
            a.triggered.connect(lambda _=False: fn())
            m.addAction(a)

        add("Режим редагування", self.toggle_edit, self.st.get("edit_mode"))
        add("Налаштування…", self.open_settings)
        m.addSeparator()
        add("Запускати разом із Windows",
            lambda: platform_win.set_autostart(not platform_win.is_autostart()), platform_win.is_autostart())
        add(f"Перевірити оновлення  (версія {VERSION})", lambda: self.check_updates(True))
        add("Відкрити папку з налаштуваннями", lambda: platform_win.open_folder(config.APP_DIR))
        m.addSeparator()
        add("Вийти", self.quit)

    def toggle_edit(self):
        self.st["edit_mode"] = not self.st.get("edit_mode")
        self.save()
        self.notify("Режим редагування", "Увімкнено. Самі віджети з'являться на наступному етапі."
                    if self.st["edit_mode"] else "Вимкнено.")

    def notify(self, title, text):
        self.tray.showMessage(title, text, QSystemTrayIcon.MessageIcon.Information, 4000)

    # ---------------- налаштування ----------------
    def open_settings(self):
        if self.settings_win and self.settings_win.isVisible():
            self.settings_win.raise_()
            self.settings_win.activateWindow()
            return
        self.settings_win = SettingsWindow(self)
        self.settings_win.show()

    def apply_settings(self):
        """Одне місце, де налаштування застосовуються до всієї програми."""
        self.clock.set_fps(self.st["fps"])
        self.check_pause()

    def check_pause(self):
        self.clock.set_paused(bool(self.st.get("pause_fullscreen")) and platform_win.fullscreen_app_active())

    def save(self):
        if not config.save(self.st):
            log.write("не вдалося зберегти налаштування")

    # ---------------- оновлення ----------------
    def check_updates(self, manual):
        if not manual and (not self.st.get("auto_update", True) or not is_frozen()):
            return                                       # з .py автоматично не перевіряємо
        self.upd_manual = manual
        self.updater.check()

    def on_up_to_date(self):
        if self.upd_manual:
            self.notify("Оновлення", f"У тебе остання версія ({VERSION}).")

    def on_update_failed(self, err):
        if self.upd_dlg and self.upd_dlg.isVisible():
            self.upd_dlg.failed(err)
        elif self.upd_manual:
            self.notify("Оновлення", "Не вдалося перевірити (немає інтернету або ще немає жодного випуску).")

    def on_update_available(self, version, notes, url):
        if not self.upd_manual and version == self.st.get("skip_version"):
            return
        if self.upd_dlg and self.upd_dlg.isVisible():
            return
        self.upd_url = url

        def skip():
            self.st["skip_version"] = version
            self.save()

        self.upd_dlg = UpdateDialog(version, notes, self.start_update, skip)
        self.upd_dlg.show()

    def start_update(self):
        if not is_frozen():
            import webbrowser
            webbrowser.open(self.updater.release_page)
            self.upd_dlg.status.setText("Це .py-версія — відкрив сторінку з новим exe у браузері.")
            return
        self.upd_dlg.busy()
        self.updater.download(self.upd_url)

    def on_update_downloaded(self, path):
        self.save()
        install_and_restart(path)
        QTimer.singleShot(300, self.quit)

    def quit(self):
        self.save()
        self.tray.hide()
        self.qapp.quit()


def main():
    QLoggingCategory.setFilterRules("qt.qpa.fonts.warning=false")
    qapp = QApplication(sys.argv)
    qapp.setQuitOnLastWindowClosed(False)
    qapp.setApplicationName(APP_NAME)
    qapp.setWindowIcon(theme.app_icon())
    qapp.setStyleSheet(theme.APP_CSS)

    sock = QLocalSocket()                                # лише одна копія програми
    sock.connectToServer(SERVER_NAME)
    if sock.waitForConnected(300):
        sock.write(b"show")
        sock.flush()
        sock.waitForBytesWritten(300)
        return 0
    QLocalServer.removeServer(SERVER_NAME)
    server = QLocalServer()
    server.listen(SERVER_NAME)

    log.install()
    app = App(qapp)

    def on_new_connection():
        c = server.nextPendingConnection()
        if c is not None:
            c.readyRead.connect(lambda: (c.readAll(), app.open_settings()))

    server.newConnection.connect(on_new_connection)
    if "--settings" in sys.argv or not config.SETTINGS_FILE.exists():
        app.open_settings()                              # перший запуск: показати, що програма жива
        app.save()
    return qapp.exec()


if __name__ == "__main__":
    sys.exit(main())
