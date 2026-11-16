"""WidgetDesk — етап 0: технічні проби (це ще НЕ програма, лише перевірка основи).

Запуск:  python stage0_test.py
Відкриється маленьке вікно керування. Роби кроки по черзі й дивись, що відбувається.
"""

import ctypes
import math
import os
import random
import sys
import time

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QCursor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (QApplication, QCheckBox, QLabel, QPushButton, QVBoxLayout, QWidget)

IS_WIN = sys.platform == "win32"

# ---------------------------------------------------------------- Windows API
if IS_WIN:
    from ctypes import wintypes

    u32 = ctypes.WinDLL("user32", use_last_error=True)
    HWND = wintypes.HWND
    ENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, HWND, wintypes.LPARAM)
    u32.FindWindowW.restype = HWND
    u32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    u32.FindWindowExW.restype = HWND
    u32.FindWindowExW.argtypes = [HWND, HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
    u32.EnumWindows.argtypes = [ENUMPROC, wintypes.LPARAM]
    u32.SendMessageTimeoutW.argtypes = [HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
                                        wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]
    u32.SetParent.restype = HWND
    u32.SetParent.argtypes = [HWND, HWND]
    u32.SetWindowPos.argtypes = [HWND, HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    u32.GetForegroundWindow.restype = HWND
    u32.GetClassNameW.argtypes = [HWND, wintypes.LPWSTR, ctypes.c_int]
    u32.GetSystemMetrics.argtypes = [ctypes.c_int]

SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x1, 0x2, 0x10
HWND_BOTTOM, HWND_TOPMOST, HWND_NOTOPMOST = 1, -1, -2


def find_wallpaper_parent():
    """Знайти вікно, що лежить ПІД іконками робочого стола. Повертає (hwnd, опис)."""
    progman = u32.FindWindowW("Progman", None)
    if not progman:
        return None, "не знайдено Progman"
    res = ctypes.c_size_t(0)
    for wp, lp in ((0xD, 0x1), (0, 0)):            # просимо Windows створити шар WorkerW
        u32.SendMessageTimeoutW(progman, 0x052C, wp, lp, 0, 1000, ctypes.byref(res))
    found = []

    def cb(top, _):
        if u32.FindWindowExW(top, None, "SHELLDLL_DefView", None):
            w = u32.FindWindowExW(None, top, "WorkerW", None)
            if w:
                found.append(w)
        return True

    u32.EnumWindows(ENUMPROC(cb), 0)
    if found:
        return found[0], "WorkerW (звичайний спосіб)"
    return progman, "Progman (запасний спосіб)"


def fg_class():
    buf = ctypes.create_unicode_buffer(64)
    u32.GetClassNameW(u32.GetForegroundWindow(), buf, 64)
    return buf.value


def set_z(widget, after):
    u32.SetWindowPos(int(widget.winId()), after, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)


# ---------------------------------------------------------------- шар шпалер
class WallpaperLayer(QWidget):
    """Анімований фон. Має опинитися ПІД іконками робочого стола."""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.t0 = time.time()
        self.how = "—"

    def attach(self):
        self.show()
        if not IS_WIN:
            self.how = "не Windows — тільки малювання"
            return self.how
        parent, self.how = find_wallpaper_parent()
        if not parent:
            return self.how
        u32.SetParent(int(self.winId()), parent)
        x, y = -u32.GetSystemMetrics(76), -u32.GetSystemMetrics(77)      # початок головного монітора
        w, h = u32.GetSystemMetrics(0), u32.GetSystemMetrics(1)
        u32.SetWindowPos(int(self.winId()), None, x, y, w, h, SWP_NOACTIVATE)
        return self.how

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        t = time.time() - self.t0
        w, h = self.width(), self.height()
        g = QLinearGradient(0, 0, w, h)
        g.setColorAt(0, QColor.fromHsvF((t * 0.02) % 1, 0.75, 0.35))
        g.setColorAt(1, QColor.fromHsvF((t * 0.02 + 0.35) % 1, 0.8, 0.18))
        p.fillRect(self.rect(), g)
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(6):                                              # кола, що плавають
            cx = w * (0.5 + 0.4 * math.sin(t * 0.3 + i * 1.7))
            cy = h * (0.5 + 0.4 * math.cos(t * 0.23 + i * 2.3))
            p.setBrush(QColor(255, 255, 255, 26))
            p.drawEllipse(QPointF(cx, cy), 90 + 30 * i, 90 + 30 * i)
        p.setPen(QColor(255, 255, 255, 230))
        p.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                   "ШАР ШПАЛЕР\nіконки робочого стола мають бути ПОВЕРХ цього фону")


# ---------------------------------------------------------------- картка-віджет
class Card(QWidget):
    """Картка «на дні»: над іконками, під звичайними вікнами. Рухається, має кнопку і дощ."""
    M = 18                                       # поле під тінь

    def __init__(self, idx, panel):
        super().__init__()
        self.panel = panel
        self.idx = idx
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
                            | Qt.WindowType.WindowStaysOnBottomHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(300 + 2 * self.M, 190 + 2 * self.M)
        self.clicks = 0
        self.drag_off = None
        self.drops = [[random.random(), random.random(), 0.5 + random.random()] for _ in range(70)]
        self.frames, self.fps, self.fps_t = 0, 0, time.time()
        self.last = time.time()

    def card_rect(self):
        return QRectF(self.M, self.M, self.width() - 2 * self.M, self.height() - 2 * self.M)

    def btn_rect(self):
        c = self.card_rect()
        return QRectF(c.left() + 20, c.bottom() - 54, 150, 36)

    def tick(self):
        now = time.time()
        dt, self.last = min(0.1, now - self.last), now
        if self.drag_off is not None:                           # рух за таймером, а не за подіями миші
            self.move(QCursor.pos() - self.drag_off)
        if self.panel.rain.isChecked():
            for d in self.drops:
                d[1] += dt * d[2] * 0.9
                if d[1] > 1.05:
                    d[0], d[1] = random.random(), -0.05
        self.frames += 1
        if now - self.fps_t >= 1:
            self.fps, self.frames, self.fps_t = self.frames, 0, now
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = self.card_rect()
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(self.M, 0, -3):                                   # м'яка тінь
            p.setBrush(QColor(0, 0, 0, 7))
            p.drawRoundedRect(c.adjusted(-i, -i + 3, i, i + 3), 22 + i, 22 + i)
        path = QPainterPath()
        path.addRoundedRect(c, 22, 22)
        p.fillPath(path, QColor(18, 20, 34, 215))
        p.setClipPath(path)
        if self.panel.rain.isChecked():                                  # дощ усередині картки
            p.setPen(QPen(QColor(150, 200, 255, 150), 1.4))
            for x, y, s in self.drops:
                px, py = c.left() + x * c.width(), c.top() + y * c.height()
                p.drawLine(QPointF(px, py), QPointF(px - 3, py + 10 + 8 * s))
        p.setClipping(False)
        p.setPen(QPen(QColor(255, 255, 255, 60), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        p.setPen(QColor(255, 255, 255))
        p.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        p.drawText(c.adjusted(20, 16, -20, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                   f"Картка {self.idx}")
        p.setFont(QFont("Segoe UI", 10))
        p.setPen(QColor(255, 255, 255, 190))
        p.drawText(c.adjusted(20, 48, -20, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                   f"Тягни мене мишкою.\nКадрів за секунду: {self.fps}")
        b = self.btn_rect()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(123, 92, 255))
        p.drawRoundedRect(b, 10, 10)
        p.setPen(QColor(255, 255, 255))
        p.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        p.drawText(b, Qt.AlignmentFlag.AlignCenter, f"Натисни: {self.clicks}")

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        if self.btn_rect().contains(e.position()):
            self.clicks += 1
        elif self.card_rect().contains(e.position()):
            self.drag_off = QCursor.pos() - self.pos()
        self.panel.keep_bottom()

    def mouseReleaseEvent(self, _):
        self.drag_off = None
        self.panel.keep_bottom()


# ---------------------------------------------------------------- вікно керування
class Panel(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setWindowTitle("WidgetDesk — проба (етап 0)")
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        self.wall = None
        self.cards = []
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        scr = app.primaryScreen()
        info = (f"Екранів: {len(app.screens())}   Головний: {scr.size().width()}×{scr.size().height()}"
                f"   Масштаб: {int(scr.devicePixelRatio() * 100)} %")
        lay.addWidget(QLabel(info))
        self.status = QLabel("Крок 1: натисни кнопку нижче.")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        for text, fn in (("1. Показати / сховати шар шпалер", self.toggle_wall),
                         ("2. Показати 1 картку", lambda: self.set_cards(1)),
                         ("3. Показати 5 карток", lambda: self.set_cards(5)),
                         ("Прибрати картки", lambda: self.set_cards(0))):
            b = QPushButton(text)
            b.clicked.connect(fn)
            lay.addWidget(b)
        self.rain = QCheckBox("Дощ на картках")
        self.rain.setChecked(True)
        self.fps60 = QCheckBox("60 кадрів за секунду (без галочки — 30)")
        self.fps60.setChecked(True)
        self.fps60.toggled.connect(self.set_fps)
        self.guard = QCheckBox("Захист від Win+D (вмикати, лише якщо картки зникають)")
        for w in (self.rain, self.fps60, self.guard):
            lay.addWidget(w)
        self.cpu = QLabel("Навантаження: —")
        self.cpu.setWordWrap(True)
        lay.addWidget(self.cpu)
        b = QPushButton("Закрити пробу")
        b.clicked.connect(app.quit)
        lay.addWidget(b)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.set_fps()
        self.slow = QTimer(self)
        self.slow.timeout.connect(self.second)
        self.slow.start(1000)
        self.cpu_t, self.cpu_p = time.time(), time.process_time()
        self.desk_mode = False

    def set_fps(self):
        self.timer.start(16 if self.fps60.isChecked() else 33)

    def tick(self):
        if self.wall and self.wall.isVisible():
            self.wall.update()
        for c in self.cards:
            c.tick()
        if IS_WIN and self.guard.isChecked() and self.cards:
            on_desk = fg_class() in ("WorkerW", "Progman")
            if on_desk != self.desk_mode:
                self.desk_mode = on_desk
                for c in self.cards:
                    set_z(c, HWND_TOPMOST if on_desk else HWND_NOTOPMOST)
                if not on_desk:
                    self.keep_bottom()

    def second(self):
        now, cp = time.time(), time.process_time()
        used = (cp - self.cpu_p) / max(0.001, now - self.cpu_t) * 100
        self.cpu_t, self.cpu_p = now, cp
        cores = os.cpu_count() or 1
        self.cpu.setText(f"Навантаження: {used / cores:.1f} % процесора "
                         f"(як у диспетчері завдань), {used:.0f} % одного ядра")

    def keep_bottom(self):
        if IS_WIN and not self.desk_mode:
            for c in self.cards:
                set_z(c, HWND_BOTTOM)

    def toggle_wall(self):
        if self.wall:
            self.wall.close()
            self.wall = None
            self.status.setText("Шар шпалер прибрано.")
            return
        self.wall = WallpaperLayer()
        how = self.wall.attach()
        self.status.setText(f"Шар шпалер увімкнено. Спосіб: {how}.\n"
                            "Згорни всі вікна і подивись: кольоровий фон має бути ПІД іконками.")

    def set_cards(self, n):
        for c in self.cards:
            c.close()
        self.cards = []
        g = self.app.primaryScreen().availableGeometry()
        for i in range(n):
            c = Card(i + 1, self)
            c.move(g.left() + 60 + (i % 3) * 350, g.top() + 60 + (i // 3) * 240)
            c.show()
            self.cards.append(c)
        self.desk_mode = False
        self.keep_bottom()
        if n:
            self.status.setText("Картки на столі. Перевір: клік по кнопці, перетягування, "
                                "відкрий інше вікно поверх, натисни Win+D.")

    def closeEvent(self, e):
        self.app.quit()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    panel = Panel(app)
    panel.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
