"""Елементи, з яких складається віджет: текст, фігура, картинка, іконка, повзунок/прогрес, кнопка.

Елемент = тип + словник властивостей. Положення задається відносно картки віджета
з прив'язкою до краю, тому при зміні розміру віджета елементи не «з'їжджають»."""

import datetime
import math
import os
import uuid

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QBrush, QColor, QFont, QFontMetricsF, QLinearGradient, QPainter, QPainterPath, QPen,
                         QPixmap, QTransform)

from core.props import Prop, clean

AX = [("left", "Від лівого краю"), ("center", "По центру"), ("right", "Від правого краю"),
      ("stretch", "На всю ширину")]
AY = [("top", "Від верху"), ("center", "По центру"), ("bottom", "Від низу"), ("stretch", "На всю висоту")]


def _pos(v):
    return (v or 0) > 0


COMMON = [
    Prop("visible", "Показувати", "bool", True, "Елемент"),
    Prop("ax", "Прив'язка по горизонталі", "choice", "left", "Положення", choices=AX,
         hint="До якого краю картки прив'язаний елемент. Тоді при зміні розміру віджета він не з'їжджає."),
    Prop("ay", "Прив'язка по вертикалі", "choice", "top", "Положення", choices=AY),
    Prop("x", "Відступ по горизонталі", "int", 16, "Положення", -4000, 4000),
    Prop("y", "Відступ по вертикалі", "int", 16, "Положення", -4000, 4000),
    Prop("w", "Ширина", "int", 120, "Положення", 1, 4000, show_if={"ax": ("left", "center", "right")}),
    Prop("h", "Висота", "int", 40, "Положення", 1, 4000, show_if={"ay": ("top", "center", "bottom")}),
    Prop("opacity", "Непрозорість, %", "int", 100, "Вигляд", 0, 100),
    Prop("rotation", "Поворот, °", "int", 0, "Вигляд", -180, 180),
    Prop("shadow", "Тінь", "bool", False, "Тінь"),
    Prop("shadow_color", "Колір тіні", "color", "#99000000", "Тінь", show_if={"shadow": (True,)}),
    Prop("shadow_dx", "Зсув тіні вбік", "int", 0, "Тінь", -40, 40, show_if={"shadow": (True,)}),
    Prop("shadow_dy", "Зсув тіні вниз", "int", 2, "Тінь", -40, 40, show_if={"shadow": (True,)}),
]

UK_DAYS = ["понеділок", "вівторок", "середа", "четвер", "п'ятниця", "субота", "неділя"]
UK_MONTHS = ["січня", "лютого", "березня", "квітня", "травня", "червня", "липня", "серпня", "вересня",
             "жовтня", "листопада", "грудня"]
EN_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
EN_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
             "October", "November", "December"]

# підстановки для тексту: (ключ, назва в меню «Вставити»)
TOKENS = [("time", "Час  19:15"), ("time_s", "Час із секундами"), ("weekday", "День тижня"),
          ("date", "Дата  16 листопада"), ("day", "Число"), ("month", "Місяць"), ("year", "Рік"),
          ("weekday_en", "День тижня англ."), ("date_en", "Дата англ."), ("month_en", "Місяць англ.")]


def tokens(now=None):
    """Живі підстановки для тексту: {time}, {date}, {weekday}…"""
    n = now or datetime.datetime.now()
    return {
        "time": n.strftime("%H:%M"), "time_s": n.strftime("%H:%M:%S"), "hour": n.strftime("%H"),
        "minute": n.strftime("%M"), "second": n.strftime("%S"), "day": str(n.day), "year": str(n.year),
        "date": f"{n.day} {UK_MONTHS[n.month - 1]}", "weekday": UK_DAYS[n.weekday()],
        "month": UK_MONTHS[n.month - 1], "date_en": f"{EN_MONTHS[n.month - 1]} {n.day}",
        "weekday_en": EN_DAYS[n.weekday()], "month_en": EN_MONTHS[n.month - 1],
    }


class Element:
    TYPE = "base"
    TITLE = "Елемент"
    OWN = []                               # власні властивості типу
    COMMON_DEFAULTS = {}                   # інші типові значення спільних властивостей
    INTERACTIVE = False                    # реагує на мишку, коли не редагуємо (кнопка)

    def __init__(self, data=None):
        data = data if isinstance(data, dict) else {}
        self.id = str(data.get("id") or uuid.uuid4().hex[:8])
        self.name = str(data.get("name") or self.TITLE)
        src = dict(self.COMMON_DEFAULTS)
        src.update(data.get("props") if isinstance(data.get("props"), dict) else {})
        self.p = clean(self.schema(), src)
        self.state = "normal"              # normal / hover / down — для кнопок, не зберігається

    @classmethod
    def schema(cls):
        own_keys = {p.key for p in cls.OWN}
        common = []
        for p in COMMON:                   # типові значення спільних властивостей можуть бути свої
            if p.key in cls.COMMON_DEFAULTS:
                p = Prop(p.key, p.label, p.kind, cls.COMMON_DEFAULTS[p.key], p.group, p.lo, p.hi, p.step,
                         p.choices, p.hint, p.show_if)
            if p.key not in own_keys:
                common.append(p)
        return common + cls.OWN

    def to_dict(self):
        return {"id": self.id, "type": self.TYPE, "name": self.name, "props": dict(self.p)}

    def rect(self, cw, ch):
        """Прямокутник елемента всередині картки розміром cw×ch."""
        p = self.p
        w, h = p["w"], p["h"]
        if p["ax"] == "stretch":
            x, w = p["x"], max(1, cw - 2 * p["x"])
        elif p["ax"] == "right":
            x = cw - p["x"] - w
        elif p["ax"] == "center":
            x = (cw - w) / 2 + p["x"]
        else:
            x = p["x"]
        if p["ay"] == "stretch":
            y, h = p["y"], max(1, ch - 2 * p["y"])
        elif p["ay"] == "bottom":
            y = ch - p["y"] - h
        elif p["ay"] == "center":
            y = (ch - h) / 2 + p["y"]
        else:
            y = p["y"]
        return QRectF(x, y, w, h)

    def is_live(self):
        """Чи треба перемальовувати щосекунди (є живі підстановки)."""
        return False

    def paint(self, p, r, color_override=None):
        pass


def _font(family, size, bold, italic, spacing=0):
    f = QFont(family or "Segoe UI")
    f.setPixelSize(max(1, int(size)))
    f.setBold(bool(bold))
    f.setItalic(bool(italic))
    if spacing:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    return f


def _gradient(r, c1, c2, angle):
    a = math.radians(angle)
    c, hx, hy = r.center(), math.cos(a) * r.width() / 2, math.sin(a) * r.height() / 2
    g = QLinearGradient(QPointF(c.x() - hx, c.y() - hy), QPointF(c.x() + hx, c.y() + hy))
    g.setColorAt(0, QColor(c1))
    g.setColorAt(1, QColor(c2))
    return QBrush(g)


ALIGN_H = {"left": Qt.AlignmentFlag.AlignLeft, "center": Qt.AlignmentFlag.AlignHCenter,
           "right": Qt.AlignmentFlag.AlignRight}
ALIGN_V = {"top": Qt.AlignmentFlag.AlignTop, "center": Qt.AlignmentFlag.AlignVCenter,
           "bottom": Qt.AlignmentFlag.AlignBottom}


class TextElement(Element):
    TYPE = "text"
    TITLE = "Текст"
    COMMON_DEFAULTS = {"w": 180, "h": 30}
    OWN = [
        Prop("text", "Текст", "text", "Текст", "Текст",
             hint="Кнопка «＋» вставляє живі значення: час, дату, день тижня…"),
        Prop("font", "Шрифт", "font", "Segoe UI", "Шрифт"),
        Prop("size", "Розмір", "int", 18, "Шрифт", 4, 600),
        Prop("bold", "Жирний", "bool", False, "Шрифт"),
        Prop("italic", "Курсив", "bool", False, "Шрифт"),
        Prop("upper", "ВЕЛИКИМИ ЛІТЕРАМИ", "bool", False, "Шрифт"),
        Prop("spacing", "Відстань між літерами", "int", 0, "Шрифт", -10, 60),
        Prop("color", "Колір", "color", "#ffffffff", "Шрифт"),
        Prop("align", "Вирівнювання", "choice", "left", "Шрифт",
             choices=[("left", "Ліворуч"), ("center", "По центру"), ("right", "Праворуч")]),
        Prop("valign", "По вертикалі", "choice", "center", "Шрифт",
             choices=[("top", "Зверху"), ("center", "По центру"), ("bottom", "Знизу")]),
        Prop("wrap", "Переносити рядки", "bool", False, "Шрифт"),
    ]

    def resolved(self, now=None):
        t = self.p["text"]
        if "{" in t:
            for k, v in tokens(now).items():
                t = t.replace("{" + k + "}", v)
        return t.upper() if self.p["upper"] else t

    def is_live(self):
        return "{" in self.p["text"]

    def paint(self, p, r, color_override=None):
        s = self.p
        p.setFont(_font(s["font"], s["size"], s["bold"], s["italic"], s["spacing"]))
        p.setPen(QColor(color_override or s["color"]))
        flags = ALIGN_H[s["align"]] | ALIGN_V[s["valign"]]
        if s["wrap"]:
            flags |= Qt.TextFlag.TextWordWrap
        p.drawText(r, int(flags), self.resolved())


class ShapeElement(Element):
    TYPE = "shape"
    TITLE = "Фігура"
    OWN = [
        Prop("shape", "Форма", "choice", "rect", "Фігура",
             choices=[("rect", "Прямокутник"), ("ellipse", "Коло / овал"), ("line", "Лінія")]),
        Prop("fill", "Колір", "color", "#ff7b5cff", "Фігура"),
        Prop("gradient", "Градієнт", "bool", False, "Фігура"),
        Prop("fill2", "Другий колір", "color", "#ffff5ca8", "Фігура", show_if={"gradient": (True,)}),
        Prop("angle", "Кут градієнта, °", "int", 0, "Фігура", 0, 360, show_if={"gradient": (True,)}),
        Prop("radius", "Заокруглення", "int", 8, "Фігура", 0, 2000, show_if={"shape": ("rect", "line")}),
        Prop("border", "Товщина рамки", "int", 0, "Фігура", 0, 60, show_if={"shape": ("rect", "ellipse")}),
        Prop("border_color", "Колір рамки", "color", "#ffffffff", "Фігура",
             show_if={"border": _pos, "shape": ("rect", "ellipse")}),
    ]

    def _brush(self, r, override):
        s = self.p
        if override:
            return QBrush(QColor(override))
        if not s["gradient"]:
            return QBrush(QColor(s["fill"]))
        return _gradient(r, s["fill"], s["fill2"], s["angle"])

    def paint(self, p, r, color_override=None):
        s = self.p
        if s["shape"] == "line":
            pen = QPen(self._brush(r, color_override), max(1, r.height()))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap if s["radius"] else Qt.PenCapStyle.FlatCap)
            p.setPen(pen)
            y = r.center().y()
            pad = r.height() / 2 if s["radius"] else 0
            p.drawLine(QPointF(r.left() + pad, y), QPointF(r.right() - pad, y))
            return
        pen = Qt.PenStyle.NoPen
        if s["border"] and not color_override:
            pen = QPen(QColor(s["border_color"]), s["border"])
            r = r.adjusted(s["border"] / 2, s["border"] / 2, -s["border"] / 2, -s["border"] / 2)
        p.setPen(pen)
        p.setBrush(self._brush(r, color_override))
        if s["shape"] == "ellipse":
            p.drawEllipse(r)
        else:
            rad = min(s["radius"], r.width() / 2, r.height() / 2)
            p.drawRoundedRect(r, rad, rad)


_PIX = {}


def load_pixmap(path):
    """Картинка з кешем (перечитується, якщо файл змінився). Порожній QPixmap, якщо файла немає."""
    if not path:
        return QPixmap()
    try:
        m = os.path.getmtime(path)
    except OSError:
        return QPixmap()
    hit = _PIX.get(path)
    if hit and hit[0] == m:
        return hit[1]
    pm = QPixmap(path)
    _PIX[path] = (m, pm)
    return pm


def draw_pixmap_fit(p, pm, r, fit):
    if pm.isNull():
        return
    if fit == "stretch":
        p.drawPixmap(r, pm, QRectF(pm.rect()))
        return
    sw, sh = pm.width(), pm.height()
    k = max(r.width() / sw, r.height() / sh) if fit == "cover" else min(r.width() / sw, r.height() / sh)
    if fit == "cover":
        cw, ch = r.width() / k, r.height() / k
        p.drawPixmap(r, pm, QRectF((sw - cw) / 2, (sh - ch) / 2, cw, ch))
    else:
        w, h = sw * k, sh * k
        p.drawPixmap(QRectF(r.center().x() - w / 2, r.center().y() - h / 2, w, h), pm, QRectF(pm.rect()))


class ImageElement(Element):
    TYPE = "image"
    TITLE = "Картинка"
    COMMON_DEFAULTS = {"w": 120, "h": 120}
    OWN = [
        Prop("path", "Файл картинки", "image", "", "Картинка"),
        Prop("fit", "Як вписати", "choice", "cover", "Картинка",
             choices=[("cover", "Заповнити (обрізати зайве)"), ("contain", "Вмістити повністю"),
                      ("stretch", "Розтягнути")]),
        Prop("radius", "Заокруглення", "int", 12, "Картинка", 0, 2000),
        Prop("border", "Товщина рамки", "int", 0, "Картинка", 0, 60),
        Prop("border_color", "Колір рамки", "color", "#ffffffff", "Картинка", show_if={"border": _pos}),
    ]

    def paint(self, p, r, color_override=None):
        s = self.p
        rad = min(s["radius"], r.width() / 2, r.height() / 2)
        path = QPainterPath()
        path.addRoundedRect(r, rad, rad)
        if color_override:
            p.fillPath(path, QColor(color_override))
            return
        pm = load_pixmap(s["path"])
        p.save()
        p.setClipPath(path, Qt.ClipOperation.IntersectClip)
        if pm.isNull():                                        # заглушка, поки картинку не вибрано
            p.fillPath(path, QColor(255, 255, 255, 28))
            p.setPen(QColor(255, 255, 255, 150))
            p.setFont(_font("Segoe UI", max(9, min(14, r.height() / 5)), False, False))
            p.drawText(r, int(Qt.AlignmentFlag.AlignCenter), "картинка")
        else:
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            draw_pixmap_fit(p, pm, r, s["fit"])
        p.restore()
        if s["border"]:
            p.setPen(QPen(QColor(s["border_color"]), s["border"]))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)


ICONS = [("play", "Грати"), ("pause", "Пауза"), ("next", "Далі"), ("prev", "Назад"), ("heart", "Серце"),
         ("star", "Зірка"), ("plus", "Плюс"), ("circle", "Коло")]


def icon_path(kind):
    """Векторні іконки в квадраті 0..1."""
    P = QPainterPath()
    if kind == "play":
        P.moveTo(0.28, 0.16); P.lineTo(0.84, 0.5); P.lineTo(0.28, 0.84); P.closeSubpath()
    elif kind == "pause":
        P.addRoundedRect(QRectF(0.24, 0.18, 0.18, 0.64), 0.04, 0.04)
        P.addRoundedRect(QRectF(0.58, 0.18, 0.18, 0.64), 0.04, 0.04)
    elif kind in ("next", "prev"):
        P.moveTo(0.16, 0.2); P.lineTo(0.62, 0.5); P.lineTo(0.16, 0.8); P.closeSubpath()
        P.addRoundedRect(QRectF(0.68, 0.2, 0.14, 0.6), 0.03, 0.03)
        if kind == "prev":
            P = QTransform(-1, 0, 0, 1, 1, 0).map(P)
    elif kind == "heart":
        P.moveTo(0.5, 0.86)
        P.cubicTo(0.0, 0.52, 0.12, 0.12, 0.5, 0.34)
        P.cubicTo(0.88, 0.12, 1.0, 0.52, 0.5, 0.86)
    elif kind == "star":
        for i in range(10):
            rr = 0.46 if i % 2 == 0 else 0.19
            a = -math.pi / 2 + i * math.pi / 5
            pt = QPointF(0.5 + rr * math.cos(a), 0.52 + rr * math.sin(a))
            P.lineTo(pt) if i else P.moveTo(pt)
        P.closeSubpath()
    elif kind == "plus":
        P.addRoundedRect(QRectF(0.42, 0.14, 0.16, 0.72), 0.05, 0.05)
        P.addRoundedRect(QRectF(0.14, 0.42, 0.72, 0.16), 0.05, 0.05)
        P.setFillRule(Qt.FillRule.WindingFill)
    else:                                                       # circle
        P.addEllipse(QRectF(0.14, 0.14, 0.72, 0.72))
    return P


def draw_icon(p, kind, r, color):
    side = min(r.width(), r.height())
    p.save()
    p.translate(r.center().x() - side / 2, r.center().y() - side / 2)
    p.scale(side, side)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    p.drawPath(icon_path(kind))
    p.restore()


class IconElement(Element):
    TYPE = "icon"
    TITLE = "Іконка"
    COMMON_DEFAULTS = {"w": 32, "h": 32}
    OWN = [
        Prop("icon", "Іконка", "choice", "play", "Іконка", choices=ICONS),
        Prop("color", "Колір", "color", "#ffffffff", "Іконка"),
    ]

    def paint(self, p, r, color_override=None):
        draw_icon(p, self.p["icon"], r, color_override or self.p["color"])


SOURCES = [("manual", "Вручну (число нижче)"), ("minute", "Секунди поточної хвилини"),
           ("hour", "Хвилини поточної години"), ("day", "Скільки минуло дня"), ("year", "Скільки минуло року")]


class ProgressElement(Element):
    """Повзунок / смужка прогресу. Поки показує значення вручну або «живий час»;
    з етапу 7 сюди підключаться музика, батарея, завантаження процесора."""
    TYPE = "progress"
    TITLE = "Повзунок"
    COMMON_DEFAULTS = {"w": 200, "h": 20}
    OWN = [
        Prop("source", "Що показує", "choice", "manual", "Значення", choices=SOURCES),
        Prop("value", "Значення, %", "int", 40, "Значення", 0, 100, show_if={"source": ("manual",)}),
        Prop("orient", "Напрямок", "choice", "h", "Смужка",
             choices=[("h", "Горизонтально"), ("v", "Вертикально (знизу вгору)")]),
        Prop("track", "Товщина смужки", "int", 6, "Смужка", 1, 200),
        Prop("radius", "Заокруглення", "int", 99, "Смужка", 0, 200),
        Prop("track_color", "Колір фону смужки", "color", "#33ffffff", "Смужка"),
        Prop("fill", "Колір заповнення", "color", "#ff7b5cff", "Смужка"),
        Prop("gradient", "Градієнт заповнення", "bool", False, "Смужка"),
        Prop("fill2", "Другий колір", "color", "#ffff5ca8", "Смужка", show_if={"gradient": (True,)}),
        Prop("knob", "Показувати бігунок", "bool", True, "Бігунок"),
        Prop("knob_shape", "Форма бігунка", "choice", "circle", "Бігунок",
             choices=[("circle", "Кружечок"), ("square", "Квадратик"), ("bar", "Рисочка")],
             show_if={"knob": (True,)}),
        Prop("knob_size", "Розмір бігунка", "int", 14, "Бігунок", 2, 200, show_if={"knob": (True,)}),
        Prop("knob_color", "Колір бігунка", "color", "#ffffffff", "Бігунок", show_if={"knob": (True,)}),
    ]

    def value(self, now=None):
        s, n = self.p, now or datetime.datetime.now()
        if s["source"] == "minute":
            return (n.second + n.microsecond / 1e6) / 60
        if s["source"] == "hour":
            return (n.minute * 60 + n.second) / 3600
        if s["source"] == "day":
            return (n.hour * 3600 + n.minute * 60 + n.second) / 86400
        if s["source"] == "year":
            start = datetime.datetime(n.year, 1, 1)
            return (n - start).total_seconds() / (datetime.datetime(n.year + 1, 1, 1) - start).total_seconds()
        return s["value"] / 100

    def is_live(self):
        return self.p["source"] != "manual"

    def paint(self, p, r, color_override=None):
        s = self.p
        v = max(0.0, min(1.0, self.value()))
        horiz = s["orient"] == "h"
        ks = s["knob_size"] if s["knob"] else 0
        if horiz:
            t = min(s["track"], r.height())
            track = QRectF(r.left() + ks / 2, r.center().y() - t / 2, max(1, r.width() - ks), t)
        else:
            t = min(s["track"], r.width())
            track = QRectF(r.center().x() - t / 2, r.top() + ks / 2, t, max(1, r.height() - ks))
        rad = min(s["radius"], t / 2)
        path = QPainterPath()
        path.addRoundedRect(track, rad, rad)
        p.setPen(Qt.PenStyle.NoPen)
        p.fillPath(path, QColor(color_override or s["track_color"]))
        if horiz:
            end = QPointF(track.left() + track.width() * v, track.center().y())
            fill = QRectF(track.left() - rad, track.top(), track.width() * v + rad, t)
        else:
            end = QPointF(track.center().x(), track.bottom() - track.height() * v)
            fill = QRectF(track.left(), end.y(), t, track.height() * v + rad)
        if v > 0:
            p.save()
            p.setClipPath(path)
            if color_override:
                brush = QBrush(QColor(color_override))
            elif s["gradient"]:
                brush = _gradient(track, s["fill"], s["fill2"], 0 if horiz else 270)
            else:
                brush = QBrush(QColor(s["fill"]))
            p.setBrush(brush)
            p.drawRoundedRect(fill, rad, rad)
            p.restore()
        if ks:
            p.setBrush(QColor(color_override or s["knob_color"]))
            if s["knob_shape"] == "circle":
                p.drawEllipse(end, ks / 2, ks / 2)
            elif s["knob_shape"] == "square":
                p.drawRoundedRect(QRectF(end.x() - ks / 2, end.y() - ks / 2, ks, ks), ks / 5, ks / 5)
            else:
                bw = max(2, ks / 4)
                k = QRectF(end.x() - bw / 2, end.y() - ks / 2, bw, ks) if horiz else \
                    QRectF(end.x() - ks / 2, end.y() - bw / 2, ks, bw)
                p.drawRoundedRect(k, bw / 2, bw / 2)


class ButtonElement(Element):
    """Кнопка: відкриває програму, файл, папку або сайт. Має окремі кольори для наведення і натискання."""
    TYPE = "button"
    TITLE = "Кнопка"
    COMMON_DEFAULTS = {"w": 140, "h": 40}
    INTERACTIVE = True
    OWN = [
        Prop("text", "Напис", "text", "Кнопка", "Напис"),
        Prop("font", "Шрифт", "font", "Segoe UI", "Напис"),
        Prop("size", "Розмір шрифту", "int", 14, "Напис", 4, 200),
        Prop("bold", "Жирний", "bool", True, "Напис"),
        Prop("text_color", "Колір напису", "color", "#ffffffff", "Напис"),
        Prop("icon", "Іконка", "choice", "none", "Напис", choices=[("none", "Без іконки")] + ICONS),
        Prop("icon_size", "Розмір іконки", "int", 16, "Напис", 4, 200, show_if={"icon": lambda v: v != "none"}),
        Prop("bg", "Колір кнопки", "color", "#ff7b5cff", "Кнопка"),
        Prop("hover", "Колір при наведенні", "color", "#ff8d72ff", "Кнопка"),
        Prop("down", "Колір при натисканні", "color", "#ff6a4be0", "Кнопка"),
        Prop("radius", "Заокруглення", "int", 10, "Кнопка", 0, 200),
        Prop("border", "Товщина рамки", "int", 0, "Кнопка", 0, 30),
        Prop("border_color", "Колір рамки", "color", "#66ffffff", "Кнопка", show_if={"border": _pos}),
        Prop("action", "Що робить", "choice", "none", "Дія",
             choices=[("none", "Нічого"), ("open", "Відкрити програму, файл, папку або сайт")]),
        Prop("target", "Що відкрити", "text", "", "Дія", show_if={"action": ("open",)},
             hint="Шлях до програми/файлу/папки або адреса сайту (https://…)."),
    ]

    def paint(self, p, r, color_override=None):
        s = self.p
        bg = {"hover": s["hover"], "down": s["down"]}.get(self.state, s["bg"])
        rad = min(s["radius"], r.width() / 2, r.height() / 2)
        if s["border"] and not color_override:
            p.setPen(QPen(QColor(s["border_color"]), s["border"]))
            br = r.adjusted(s["border"] / 2, s["border"] / 2, -s["border"] / 2, -s["border"] / 2)
        else:
            p.setPen(Qt.PenStyle.NoPen)
            br = r
        p.setBrush(QColor(color_override or bg))
        p.drawRoundedRect(br, rad, rad)
        if color_override:
            return
        text = s["text"]
        f = _font(s["font"], s["size"], s["bold"], False)
        has_icon = s["icon"] != "none"
        isz = s["icon_size"] if has_icon else 0
        tw = QFontMetricsF(f).horizontalAdvance(text) if text else 0
        gap = 8 if has_icon and text else 0
        x = r.center().x() - (isz + gap + tw) / 2
        if has_icon:
            draw_icon(p, s["icon"], QRectF(x, r.center().y() - isz / 2, isz, isz), s["text_color"])
        if text:
            p.setFont(f)
            p.setPen(QColor(s["text_color"]))
            tr = QRectF(x + isz + gap, r.top(), tw + 2, r.height())
            p.drawText(tr, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), text)


TYPES = {c.TYPE: c for c in (TextElement, ShapeElement, ImageElement, IconElement, ProgressElement,
                             ButtonElement)}
ADD_MENU = [("text", "Текст"), ("shape", "Фігура"), ("image", "Картинка"), ("icon", "Іконка"),
            ("progress", "Повзунок / прогрес"), ("button", "Кнопка")]


def make(data):
    """Створити елемент із даних; невідомий або зіпсований тип → None (його буде пропущено)."""
    cls = TYPES.get(data.get("type")) if isinstance(data, dict) else None
    return cls(data) if cls else None
