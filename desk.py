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
from model.widget import Widget, demo_widget
from ui.app_windows import SettingsWindow, UpdateDialog
from render.backdrop import Backdrop
from ui.host import WidgetHost

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

        self.hosts = []
        self.undo_stack = []
        self.backdrop = Backdrop()
        self.backdrop.refresh(qapp.primaryScreen().geometry())
        self.widgets = [Widget(d) for d in self.st.get("widgets", []) if isinstance(d, dict)]
        if not self.widgets and not self.st.get("seen_demo"):
            self.widgets.append(demo_widget())           # перший запуск: один віджет для прикладу
        self.st["seen_demo"] = True
        for wd in self.widgets:
            self.clamp_to_screen(wd)
            self._add_host(wd)

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
        self.wall_watch = QTimer(self)                  # раз на 5 с: чи не змінились шпалери / екран
        self.wall_watch.timeout.connect(self.check_wallpaper)
        self.wall_watch.start(5000)
        qapp.primaryScreen().geometryChanged.connect(lambda *_: self.screen_changed())
        qapp.screenAdded.connect(lambda *_: self.screen_changed())
        qapp.screenRemoved.connect(lambda *_: self.screen_changed())

        self.hotkey = platform_win.GlobalHotkey({"edit": ("ctrl+alt", 0x45)})      # Ctrl+Alt+E
        self.hotkey.pressed.connect(lambda name: self.toggle_edit() if name == "edit" else None)
        self.restack()

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

        add("Режим редагування  (Ctrl+Alt+E)", self.toggle_edit, self.st.get("edit_mode"))
        add("Додати тестовий віджет", self.add_demo)
        if self.can_undo():
            add("Повернути останню дію", self.undo)
        add("Зібрати всі віджети на екран", self.gather)
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
        for h in self.hosts:
            h.update()
        if self.st["edit_mode"]:
            self.notify("Режим редагування", "Увімкнено: тягни віджети мишкою. Вимкни тут же, коли розставиш.")

    # ---------------- віджети ----------------
    def _add_host(self, wd):
        h = WidgetHost(wd, self)
        h.show()
        self.hosts.append(h)

    def host_of(self, wd):
        return next((h for h in self.hosts if h.wd is wd), None)

    def rebuild_hosts(self):
        for h in self.hosts:
            h.close()
            h.deleteLater()
        self.hosts = []
        for wd in self.widgets:
            self._add_host(wd)
        self.restack()

    def restack(self):
        """Порядок вікон «на дні»: перший у списку — найнижчий, останній — найвищий."""
        for h in reversed(self.hosts):
            if h.isVisible():
                platform_win.send_to_bottom(int(h.winId()))

    def other_rects(self, wd):
        return [(o.x, o.y, o.w, o.h) for o in self.widgets if o is not wd]

    def screen_rect(self, wd):
        g = self._screen_of(wd)
        return (g.left(), g.top(), g.width(), g.height())

    # --- дії з віджетами (кожна спершу робить знімок для «Повернути») ---
    def checkpoint(self):
        self.undo_stack.append([w.to_dict() for w in self.widgets])
        del self.undo_stack[:-30]

    def can_undo(self):
        return bool(self.undo_stack)

    def undo(self):
        if not self.undo_stack:
            return
        self.widgets = [Widget(d) for d in self.undo_stack.pop()]
        self.rebuild_hosts()
        self.save()

    def add_demo(self):
        self.checkpoint()
        wd = demo_widget()
        n = len(self.widgets)
        wd.x, wd.y = 90 + 40 * (n % 8), 90 + 40 * (n % 8)
        self.clamp_to_screen(wd)
        self.widgets.append(wd)
        self._add_host(wd)
        self.restack()
        self.save()

    def duplicate(self, wd):
        self.checkpoint()
        d = wd.to_dict()
        d.pop("id")
        for e in d["elements"]:
            e.pop("id", None)
        new = Widget(d)
        new.x, new.y, new.locked = wd.x + 30, wd.y + 30, False
        self.clamp_to_screen(new)
        self.widgets.append(new)
        self._add_host(new)
        self.restack()
        self.save()

    def delete(self, wd):
        self.checkpoint()
        h = self.host_of(wd)
        self.widgets.remove(wd)
        if h:
            self.hosts.remove(h)
            h.close()
            h.deleteLater()
        self.save()
        self.notify("Віджет видалено", "Повернути: права кнопка на віджеті або іконка в треї → «Повернути останню дію».")

    def resize_widget(self, wd, w, h):
        self.checkpoint()
        wd.w, wd.h = w, h
        self.clamp_to_screen(wd)
        self.host_of(wd).sync()
        self.save()

    def toggle_lock(self, wd):
        self.checkpoint()
        wd.locked = not wd.locked
        self.host_of(wd).update()
        self.save()

    def reorder(self, wd, to_front):
        self.checkpoint()
        h = self.host_of(wd)
        self.widgets.remove(wd)
        self.hosts.remove(h)
        if to_front:
            self.widgets.append(wd)
            self.hosts.append(h)
        else:
            self.widgets.insert(0, wd)
            self.hosts.insert(0, h)
        self.restack()
        self.save()

    def _screen_of(self, wd):
        from PyQt6.QtCore import QRect
        r = QRect(wd.x, wd.y, wd.w, wd.h)
        for scr in self.qapp.screens():
            if scr.availableGeometry().intersects(r):
                return scr.availableGeometry()
        return self.qapp.primaryScreen().availableGeometry()

    def check_wallpaper(self):
        if self.backdrop.refresh(self.qapp.primaryScreen().geometry()):
            for h in self.hosts:
                h.update()

    def screen_changed(self):
        """Змінилась роздільність або кількість моніторів — нічого не має лишитись за екраном."""
        self.check_wallpaper()
        for h in self.hosts:
            self.clamp_to_screen(h.wd)
            h.sync()
        self.restack()

    def clamp_to_screen(self, wd):
        """Віджет не може опинитись за краєм екрана (урок: «панель зникла»)."""
        g = self._screen_of(wd)
        keep = 40                                        # щонайменше стільки віджета має бути видно
        wd.x = max(g.left() - wd.w + keep, min(g.right() - keep, wd.x))
        wd.y = max(g.top(), min(g.bottom() - keep, wd.y))

    def gather(self):
        g = self.qapp.primaryScreen().availableGeometry()
        self.checkpoint()
        for i, h in enumerate(self.hosts):
            h.wd.x, h.wd.y = g.left() + 60 + 36 * (i % 10), g.top() + 60 + 36 * (i % 10)
            h.sync()
        self.restack()
        self.save()

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
        self.st["widgets"] = [w.to_dict() for w in self.widgets]
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
        for h in self.hosts:
            h.close()
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
