"""Спільний годинник кадрів: один таймер на всю програму.

Усе, що анімується, підписується сюди і отримує tick(dt). Так легко обмежити FPS,
поставити все на паузу (гра на весь екран, економний режим) і не плодити десятки таймерів."""

import time

from PyQt6.QtCore import QObject, QTimer, Qt


class FrameClock(QObject):
    def __init__(self, fps=60, parent=None):
        super().__init__(parent)
        self._subs = []
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._tick)
        self._last = time.perf_counter()
        self.paused = False
        self.fps = 0                       # виміряні кадри за секунду
        self._n, self._t = 0, self._last
        self.set_fps(fps)

    def set_fps(self, fps):
        self.limit = 30 if int(fps) <= 30 else 60
        self._timer.setInterval(int(1000 / self.limit))
        self._sync()

    def subscribe(self, fn):
        if fn not in self._subs:
            self._subs.append(fn)
        self._sync()

    def unsubscribe(self, fn):
        if fn in self._subs:
            self._subs.remove(fn)
        self._sync()

    def set_paused(self, on):
        self.paused = bool(on)
        self._sync()

    def _sync(self):
        """Таймер працює, лише коли є кому малювати і немає паузи — у спокої 0 % процесора."""
        need = bool(self._subs) and not self.paused
        if need and not self._timer.isActive():
            self._last = time.perf_counter()
            self._timer.start()
        elif not need and self._timer.isActive():
            self._timer.stop()

    def _tick(self):
        now = time.perf_counter()
        dt = min(0.1, now - self._last)    # після зависання не робити величезний стрибок
        self._last = now
        self._n += 1
        if now - self._t >= 1:
            self.fps, self._n, self._t = self._n, 0, now
        for fn in list(self._subs):
            fn(dt)
