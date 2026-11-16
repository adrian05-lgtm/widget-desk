"""Вікно одного віджета на робочому столі: лежить «на дні» — над іконками, під звичайними вікнами."""

from PyQt6.QtCore import QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QCursor, QPainter, QPen, QColor
from PyQt6.QtWidgets import QWidget

from core import platform_win
from render import painter


class WidgetHost(QWidget):
    changed = pyqtSignal()                           # віджет пересунули — треба зберегти

    def __init__(self, wd, ctl):
        super().__init__()
        self.wd = wd
        self.ctl = ctl
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
                            | Qt.WindowType.WindowStaysOnBottomHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._drag = None
        self._live = QTimer(self)                    # живі тексти ({time}…) — раз на секунду
        self._live.timeout.connect(self.update)
        self.sync()

    # ---------------- розмір і місце ----------------
    def sync(self):
        """Привести вікно у відповідність до даних віджета (після будь-якої зміни)."""
        m = painter.margin(self.wd)
        self.m = m
        self.setGeometry(self.wd.x - m, self.wd.y - m, self.wd.w + 2 * m, self.wd.h + 2 * m)
        if self.wd.is_live():
            if not self._live.isActive():
                self._live.start(1000)
        else:
            self._live.stop()
        self.update()

    def card(self):
        return QRectF(self.m, self.m, self.wd.w, self.wd.h)

    def keep_bottom(self):
        if self.isVisible():
            platform_win.send_to_bottom(int(self.winId()))

    def showEvent(self, e):
        super().showEvent(e)
        self.keep_bottom()

    # ---------------- малювання ----------------
    def paintEvent(self, _):
        p = QPainter(self)
        painter.paint_widget(p, self.wd, self.card())
        if self.ctl.st.get("edit_mode"):                         # у режимі редагування — пунктирна рамка
            p.setPen(QPen(QColor(123, 92, 255, 230), 1.5, Qt.PenStyle.DashLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            path, _r = painter.card_path(self.card().adjusted(-2, -2, 2, 2), self.wd.p["radius"] + 2)
            p.drawPath(path)

    # ---------------- перетягування (лише в режимі редагування) ----------------
    def mousePressEvent(self, e):
        if (e.button() == Qt.MouseButton.LeftButton and self.ctl.st.get("edit_mode")
                and not self.wd.locked and self.card().contains(e.position())):
            self._drag = QCursor.pos() - self.pos()
            self.ctl.clock.subscribe(self._follow)               # рух за таймером кадрів — плавно
        self.keep_bottom()

    def _follow(self, _dt):
        if self._drag is not None:
            self.move(QCursor.pos() - self._drag)

    def mouseReleaseEvent(self, _):
        if self._drag is not None:
            self._drag = None
            self.ctl.clock.unsubscribe(self._follow)
            self.wd.x, self.wd.y = self.x() + self.m, self.y() + self.m
            self.ctl.clamp_to_screen(self.wd)
            self.sync()
            self.changed.emit()
        self.keep_bottom()
