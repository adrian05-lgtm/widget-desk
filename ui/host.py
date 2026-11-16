"""Вікно одного віджета на робочому столі: лежить «на дні» — над іконками, під звичайними вікнами.
У режимі редагування його можна тягнути, змінювати розмір за краї й кути, є меню правою кнопкою."""

from PyQt6.QtCore import QPoint, QRectF, Qt, QTimer
from PyQt6.QtGui import QAction, QColor, QCursor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QMenu, QWidget

from core import platform_win
from model.widget import MIN_H, MIN_W
from render import painter
from ui import snap

GRIP = 9                         # ширина зони біля краю, за яку тягнуть розмір
SIZES = [("Малий  170×170", 170, 170), ("Середній  340×170", 340, 170), ("Великий  340×340", 340, 340),
         ("Широкий  520×170", 520, 170), ("Високий  170×340", 170, 340)]
CURSORS = {"l": Qt.CursorShape.SizeHorCursor, "r": Qt.CursorShape.SizeHorCursor,
           "t": Qt.CursorShape.SizeVerCursor, "b": Qt.CursorShape.SizeVerCursor,
           "lt": Qt.CursorShape.SizeFDiagCursor, "rb": Qt.CursorShape.SizeFDiagCursor,
           "rt": Qt.CursorShape.SizeBDiagCursor, "lb": Qt.CursorShape.SizeBDiagCursor}


class WidgetHost(QWidget):
    def __init__(self, wd, ctl):
        super().__init__()
        self.wd = wd
        self.ctl = ctl
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
                            | Qt.WindowType.WindowStaysOnBottomHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self._mode = None            # None / "move" / краї, які тягнуть ("r", "lt"…)
        self._start = None           # (позиція курсора, x, y, w, h) на початку руху
        self._live = QTimer(self)    # живі тексти ({time}…) — раз на секунду
        self._live.timeout.connect(self.update)
        self.sync()

    # ---------------- розмір і місце ----------------
    def sync(self):
        """Привести вікно у відповідність до даних віджета (після будь-якої зміни)."""
        self.m = painter.margin(self.wd)
        self.setGeometry(self.wd.x - self.m, self.wd.y - self.m, self.wd.w + 2 * self.m, self.wd.h + 2 * self.m)
        if self.wd.is_live():
            if not self._live.isActive():
                self._live.start(1000)
        else:
            self._live.stop()
        self.update()

    def card(self):
        return QRectF(self.m, self.m, self.wd.w, self.wd.h)

    def editing(self):
        return bool(self.ctl.st.get("edit_mode"))

    # ---------------- малювання ----------------
    def paintEvent(self, _):
        p = QPainter(self)
        wd = self.wd
        back = None
        if wd.p["bg"] == "glass":
            back = self.ctl.backdrop.piece(wd.x, wd.y, wd.w, wd.h, wd.p["blur"])
        painter.paint_widget(p, wd, self.card(), back)
        if not self.editing():
            return
        col = QColor(255, 200, 87) if wd.locked else QColor(123, 92, 255)
        p.setPen(QPen(col, 1.5, Qt.PenStyle.DashLine))
        p.setBrush(Qt.BrushStyle.NoBrush)
        path, _r = painter.card_path(self.card().adjusted(-2, -2, 2, 2), wd.p["radius"] + 2)
        p.drawPath(path)
        if self._mode and self._mode != "move" or wd.locked:                 # підказка: розмір або «закріплено»
            text = "закріплено" if wd.locked and not self._mode else f"{wd.w} × {wd.h}"
            f = QFont("Segoe UI")
            f.setPixelSize(12)
            f.setBold(True)
            p.setFont(f)
            tw = p.fontMetrics().horizontalAdvance(text) + 16
            r = QRectF(self.card().center().x() - tw / 2, self.card().bottom() - 28, tw, 20)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 170))
            p.drawRoundedRect(r, 10, 10)
            p.setPen(QColor(255, 255, 255))
            p.drawText(r, int(Qt.AlignmentFlag.AlignCenter), text)

    # ---------------- мишка ----------------
    def _edges_at(self, pos):
        """Які краї картки під курсором: '' (середина) / 'l', 'rb'… або None (поза карткою)."""
        c = self.card()
        if not c.adjusted(-GRIP / 2, -GRIP / 2, GRIP / 2, GRIP / 2).contains(pos):
            return None
        e = ""
        if pos.x() < c.left() + GRIP:
            e += "l"
        elif pos.x() > c.right() - GRIP:
            e += "r"
        if pos.y() < c.top() + GRIP:
            e += "t"
        elif pos.y() > c.bottom() - GRIP:
            e += "b"
        return e

    def mouseMoveEvent(self, e):
        if self._mode is None:
            edges = self._edges_at(e.position()) if self.editing() and not self.wd.locked else None
            if edges:
                self.setCursor(CURSORS[edges])
            elif edges == "":
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            else:
                self.unsetCursor()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.editing() and not self.wd.locked:
            edges = self._edges_at(e.position())
            if edges is not None:
                self.ctl.checkpoint()
                self._mode = edges or "move"
                self._start = (QCursor.pos(), self.wd.x, self.wd.y, self.wd.w, self.wd.h)
                self.ctl.clock.subscribe(self._follow)       # рух за таймером кадрів — плавно
        self.ctl.restack()

    def _follow(self, _dt):
        if self._mode is None:
            return
        if not QApplication.mouseButtons() & Qt.MouseButton.LeftButton:
            self._finish()                                   # кнопку відпустили поза вікном
            return
        p0, x0, y0, w0, h0 = self._start
        d = QCursor.pos() - p0
        free = bool(QApplication.keyboardModifiers() & Qt.KeyboardModifier.AltModifier)   # Alt — без прилипання
        grid = 1 if free else int(self.ctl.st.get("grid", 10))
        others = [] if free else self.ctl.other_rects(self.wd)
        scr = self.ctl.screen_rect(self.wd)
        if self._mode == "move":
            x, y = x0 + d.x(), y0 + d.y()
            if not free:
                x, y = snap.snap_move((x, y, w0, h0), others, scr, grid)
            self.wd.x, self.wd.y = x, y
        else:
            l, t, r, b = x0, y0, x0 + w0, y0 + h0
            if "l" in self._mode:
                l = min(l + d.x(), r - MIN_W)
            if "r" in self._mode:
                r = max(r + d.x(), l + MIN_W)
            if "t" in self._mode:
                t = min(t + d.y(), b - MIN_H)
            if "b" in self._mode:
                b = max(b + d.y(), t + MIN_H)
            rect = (l, t, r - l, b - t)
            if not free:
                rect = snap.snap_resize(rect, self._mode, others, scr, grid, min_w=MIN_W, min_h=MIN_H)
            self.wd.x, self.wd.y, self.wd.w, self.wd.h = rect
        self.sync()

    def _finish(self):
        if self._mode is None:
            return
        self._mode = None
        self.ctl.clock.unsubscribe(self._follow)
        self.ctl.clamp_to_screen(self.wd)
        self.sync()
        self.ctl.save()

    def mouseReleaseEvent(self, _):
        self._finish()
        self.ctl.restack()

    # ---------------- меню правою кнопкою ----------------
    def contextMenuEvent(self, e):
        if not self.card().contains(QPoint(e.pos())):
            return
        m = QMenu()
        ctl, wd = self.ctl, self.wd

        def add(menu, text, fn, enabled=True):
            a = QAction(text, menu)
            a.setEnabled(enabled)
            a.triggered.connect(lambda _=False: fn())
            menu.addAction(a)

        if not self.editing():
            add(m, "Редагувати віджети", ctl.toggle_edit)
            add(m, "Налаштування…", ctl.open_settings)
        else:
            sub = m.addMenu("Розмір")
            for text, w, h in SIZES:
                add(sub, text, lambda w=w, h=h: ctl.resize_widget(wd, w, h), not wd.locked)
            add(m, "Відкріпити" if wd.locked else "Закріпити на місці", lambda: ctl.toggle_lock(wd))
            add(m, "Дублювати", lambda: ctl.duplicate(wd))
            m.addSeparator()
            add(m, "На передній план", lambda: ctl.reorder(wd, True))
            add(m, "На задній план", lambda: ctl.reorder(wd, False))
            m.addSeparator()
            add(m, "Повернути останню дію", ctl.undo, ctl.can_undo())
            add(m, "Видалити віджет", lambda: ctl.delete(wd))
            m.addSeparator()
            add(m, "Завершити редагування", ctl.toggle_edit)
        m.exec(e.globalPos())
        self.ctl.restack()
