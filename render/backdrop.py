"""Розмите «скло»: беремо файл шпалер Windows, один раз розмиваємо і вирізаємо шматок під кожен віджет.

Один розмитий знімок на всі віджети (на кожну силу розмиття) — дешево. Якщо файл шпалер недоступний
(або фон малює інша програма), скло лишається просто напівпрозорим кольором."""

import os

from PyQt6.QtCore import QRect, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPixmap

from core import platform_win

SCALE = 4            # розмиту копію тримаємо в 1/4 розміру екрана — вистачає і майже не їсть пам'яті


class Backdrop:
    def __init__(self, path_override=None):
        self.override = path_override
        self.sig = None              # (шлях, час зміни, режим, розмір екрана)
        self.base = None             # шпалери, вписані в екран, у зменшеному розмірі
        self.cache = {}              # сила розмиття -> QPixmap
        self.screen = QRect()

    def _source(self):
        if self.override:
            return self.override, "fill"
        return platform_win.wallpaper_info()

    def refresh(self, screen_geom):
        """Перечитати шпалери, якщо вони змінились. Повертає True, якщо треба перемалювати віджети."""
        path, mode = self._source()
        try:
            mt = os.path.getmtime(path) if path else 0
        except OSError:
            path, mt = "", 0
        sig = (path, mt, mode, screen_geom.width(), screen_geom.height())
        if sig == self.sig:
            return False
        self.sig, self.screen, self.cache, self.base = sig, QRect(screen_geom), {}, None
        src = QPixmap(path) if path else QPixmap()
        if src.isNull():
            return True
        w, h = max(1, screen_geom.width() // SCALE), max(1, screen_geom.height() // SCALE)
        base = QPixmap(w, h)
        base.fill(QColor(0, 0, 0))
        p = QPainter(base)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        sw, sh = src.width(), src.height()
        if mode == "stretch":
            p.drawPixmap(QRectF(0, 0, w, h), src, QRectF(src.rect()))
        elif mode == "fit":
            k = min(w / sw, h / sh)
            p.drawPixmap(QRectF((w - sw * k) / 2, (h - sh * k) / 2, sw * k, sh * k), src, QRectF(src.rect()))
        else:
            k = max(w / sw, h / sh)
            cw, ch = w / k, h / k
            p.drawPixmap(QRectF(0, 0, w, h), src, QRectF((sw - cw) / 2, (sh - ch) / 2, cw, ch))
        p.end()
        self.base = base
        return True

    def _blurred(self, blur):
        blur = max(0, min(40, int(blur) // 4 * 4))
        if blur not in self.cache:
            pm = self.base
            if blur:
                k = 1 + blur / 3                       # що сильніше розмиття, то більше стискаємо
                small = pm.scaled(max(2, int(pm.width() / k)), max(2, int(pm.height() / k)),
                                  Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                mid = small.scaled(max(2, pm.width() // 2), max(2, pm.height() // 2),
                                   Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                pm = mid.scaled(pm.width(), pm.height(), Qt.AspectRatioMode.IgnoreAspectRatio,
                                Qt.TransformationMode.SmoothTransformation)
            self.cache[blur] = pm
        return self.cache[blur]

    def piece(self, x, y, w, h, blur):
        """Шматок розмитих шпалер під прямокутник екрана (x, y, w, h) або None."""
        if self.base is None or self.screen.isEmpty():
            return None
        pm = self._blurred(blur)
        fx, fy = pm.width() / self.screen.width(), pm.height() / self.screen.height()
        r = QRect(int((x - self.screen.left()) * fx), int((y - self.screen.top()) * fy),
                  max(1, int(w * fx)), max(1, int(h * fy)))
        if not r.intersects(pm.rect()):
            return None
        return pm.copy(r)                              # за краєм екрана копія доповнюється прозорим
