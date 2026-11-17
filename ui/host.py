"""Вікно одного віджета на робочому столі: лежить «на дні» — над іконками, під звичайними вікнами.

Три режими мишки:
- звичайний — працюють кнопки всередині віджета (наведення, натискання, дія);
- редагування (Ctrl+Alt+E) — віджет тягнеться, розмір міняється за краї й кути, меню правою кнопкою;
- відкритий редактор вигляду для ЦЬОГО віджета — клік вибирає елемент, перетягування рухає елемент."""

from PyQt6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QAction, QColor, QCursor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QMenu, QWidget

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
SEL = QColor(62, 198, 255)       # колір рамки вибраного елемента


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
        self._el_drag = None         # [елемент, позиція курсора, x0, y0, чи записано крок назад]
        self._hover = None           # кнопка під мишкою
        self._pressed = None         # натиснута кнопка
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

    def inspector(self):
        """Редактор вигляду, якщо він відкритий саме для цього віджета."""
        i = self.ctl.inspector
        return i if i is not None and i.wd is self.wd else None

    def element_at(self, pos, interactive_only=False):
        """Верхній видимий елемент під точкою (координати вікна) або None."""
        c = self.card()
        local = QPointF(pos) - c.topLeft()
        for el in reversed(self.wd.elements):
            if not el.p["visible"] or (interactive_only and not el.INTERACTIVE):
                continue
            r = el.rect(c.width(), c.height())
            if r.adjusted(-4, -4, 4, 4).contains(local):      # тонкі лінії теж можна зачепити
                return el
        return None

    # ---------------- малювання ----------------
    def paintEvent(self, _):
        p = QPainter(self)
        wd = self.wd
        back = None
        if wd.p["bg"] == "glass":
            back = self.ctl.backdrop.piece(wd.x, wd.y, wd.w, wd.h, wd.p["blur"])
        painter.paint_widget(p, wd, self.card(), back)
        insp = self.inspector()
        if insp is not None:
            self._paint_selection(p, insp.sel)
        if not self.editing() and insp is None:
            return
        if insp is None:
            col = QColor(255, 200, 87) if wd.locked else QColor(123, 92, 255)
            p.setPen(QPen(col, 1.5, Qt.PenStyle.DashLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            path, _r = painter.card_path(self.card().adjusted(-2, -2, 2, 2), wd.p["radius"] + 2)
            p.drawPath(path)
        if (self._mode and self._mode != "move") or (wd.locked and self.editing()):
            text = "закріплено" if wd.locked and not self._mode else f"{wd.w} × {wd.h}"
            self._badge(p, text)

    def _paint_selection(self, p, sel):
        c = self.card()
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(SEL, 1.5, Qt.PenStyle.DashLine))
        if sel is None:
            path, _r = painter.card_path(c.adjusted(-2, -2, 2, 2), self.wd.p["radius"] + 2)
            p.drawPath(path)
            return
        r = sel.rect(c.width(), c.height()).translated(c.topLeft()).adjusted(-3, -3, 3, 3)
        p.drawRect(r)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(SEL)
        for pt in (r.topLeft(), r.topRight(), r.bottomLeft(), r.bottomRight()):
            p.drawRect(QRectF(pt.x() - 2.5, pt.y() - 2.5, 5, 5))

    def _badge(self, p, text):
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
        if not c.adjusted(-GRIP / 2, -GRIP / 2, GRIP / 2, GRIP / 2).contains(QPointF(pos)):
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

    def _set_hover(self, el):
        if el is self._hover:
            return
        if self._hover is not None:
            self._hover.state = "normal"
        self._hover = el
        if el is not None:
            el.state = "down" if el is self._pressed else "hover"
        self.update()

    def mouseMoveEvent(self, e):
        if self._mode is not None or self._el_drag is not None:
            return
        pos = e.position()
        insp = self.inspector()
        can_size = self.editing() and not self.wd.locked
        edges = self._edges_at(pos) if can_size else None
        if edges:
            self.setCursor(CURSORS[edges])
        elif insp is not None:
            self.setCursor(Qt.CursorShape.PointingHandCursor if self.element_at(pos) else
                           (Qt.CursorShape.SizeAllCursor if can_size else Qt.CursorShape.ArrowCursor))
        elif edges == "":
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        elif not self.editing():
            btn = self.element_at(pos, interactive_only=True)
            self._set_hover(btn)
            if btn is not None and btn.p["action"] != "none":
                self.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.unsetCursor()
        else:
            self.unsetCursor()

    def leaveEvent(self, _):
        self._set_hover(None)

    def mousePressEvent(self, e):
        self.ctl.restack()
        if e.button() != Qt.MouseButton.LeftButton:
            return
        pos = e.position()
        insp = self.inspector()
        can_size = self.editing() and not self.wd.locked
        edges = self._edges_at(pos) if can_size else None
        if edges:                                            # зміна розміру за край/кут
            self._start_widget_drag(edges)
            return
        if insp is not None:                                 # редактор відкритий: клік вибирає елемент
            el = self.element_at(pos)
            if el is not None:
                insp.select(el)
                self._el_drag = [el, QCursor.pos(), el.p["x"], el.p["y"], False]
                self.ctl.clock.subscribe(self._follow)
            elif self.card().contains(pos):
                insp.select(None)
                if can_size:
                    self._start_widget_drag("move")
            return
        if edges == "":                                      # режим редагування: тягнемо віджет
            self._start_widget_drag("move")
            return
        if not self.editing():                               # звичайний режим: кнопка
            btn = self.element_at(pos, interactive_only=True)
            if btn is not None:
                self._pressed = btn
                btn.state = "down"
                self.update()

    def _start_widget_drag(self, mode):
        self.ctl.checkpoint()
        self._mode = mode
        self._start = (QCursor.pos(), self.wd.x, self.wd.y, self.wd.w, self.wd.h)
        self.ctl.clock.subscribe(self._follow)               # рух за таймером кадрів — плавно

    def _follow(self, _dt):
        if self._mode is None and self._el_drag is None:
            return
        if not QApplication.mouseButtons() & Qt.MouseButton.LeftButton:
            self._finish()                                   # кнопку відпустили поза вікном
            return
        if self._el_drag is not None:
            self._follow_element()
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
        insp = self.inspector()
        if insp is not None and insp.sel is None:
            insp.refresh_values(["w", "h"])

    def _follow_element(self):
        """Рух елемента всередині картки. Відступ рахується від того краю, до якого елемент прив'язаний."""
        el, p0, x0, y0, noted = self._el_drag
        d = QCursor.pos() - p0
        if d.isNull():
            return
        insp = self.inspector()
        if not noted and insp is not None:                   # крок назад — лише якщо справді посунули
            insp.push()
            self._el_drag[4] = True
        if el.p["ax"] in ("left", "center"):
            el.p["x"] = max(-4000, min(4000, x0 + d.x()))
        elif el.p["ax"] == "right":
            el.p["x"] = max(-4000, min(4000, x0 - d.x()))
        if el.p["ay"] in ("top", "center"):
            el.p["y"] = max(-4000, min(4000, y0 + d.y()))
        elif el.p["ay"] == "bottom":
            el.p["y"] = max(-4000, min(4000, y0 - d.y()))
        self.update()
        if insp is not None:
            insp.refresh_values(["x", "y"])

    def _finish(self):
        self.ctl.clock.unsubscribe(self._follow)
        if self._el_drag is not None:
            self._el_drag = None
            return
        if self._mode is None:
            return
        self._mode = None
        self.ctl.clamp_to_screen(self.wd)
        self.sync()
        self.ctl.save()

    def mouseReleaseEvent(self, e):
        btn, self._pressed = self._pressed, None
        if btn is not None:                                  # кнопка спрацьовує, якщо відпустили над нею
            over = self.element_at(e.position(), interactive_only=True) is btn
            btn.state = "hover" if over else "normal"
            self.update()
            if over:
                self.ctl.run_action(btn)
        self._finish()
        self.ctl.restack()

    def mouseDoubleClickEvent(self, e):
        if self.editing() and self.card().contains(e.position()) and self.inspector() is None:
            self.ctl.open_inspector(self.wd)

    # ---------------- меню правою кнопкою ----------------
    def contextMenuEvent(self, e):
        if not self.card().contains(QPointF(QPoint(e.pos()))):
            return
        m = QMenu()
        ctl, wd = self.ctl, self.wd

        def add(menu, text, fn, enabled=True):
            a = QAction(text, menu)
            a.setEnabled(enabled)
            a.triggered.connect(lambda _=False: fn())
            menu.addAction(a)

        if self.inspector() is not None:
            add(m, "Показати редактор вигляду", lambda: (ctl.inspector.raise_(), ctl.inspector.activateWindow()))
        elif not self.editing():
            add(m, "Налаштувати вигляд…", lambda: ctl.open_inspector(wd))
            add(m, "Редагувати віджети", ctl.toggle_edit)
            add(m, "Налаштування…", ctl.open_settings)
        else:
            add(m, "Налаштувати вигляд…", lambda: ctl.open_inspector(wd))
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
