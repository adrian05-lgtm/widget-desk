"""Малювання віджета. Не залежить від Windows — тому перевіряється офлайн (рендер у картинку)."""

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen

from model.element import draw_pixmap_fit, load_pixmap


def margin(wd):
    """Поле навколо картки під тінь."""
    return int(wd.p["shadow"]) + 4 if wd.p["shadow"] and wd.p["bg"] != "none" else 4


def card_path(card, radius):
    rad = min(radius, card.width() / 2, card.height() / 2)
    path = QPainterPath()
    path.addRoundedRect(card, rad, rad)
    return path, rad


def paint_widget(p, wd, card, backdrop=None):
    """Намалювати віджет wd у прямокутнику card (QRectF). backdrop — розмитий фон для «скла» (або None)."""
    s = wd.p
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.setOpacity(s["opacity"] / 100)
    path, rad = card_path(card, s["radius"])

    if s["bg"] != "none" and s["shadow"] and s["shadow_alpha"]:          # м'яка тінь у полі вікна
        n = max(1, s["shadow"] // 2)
        a = max(1, int(255 * s["shadow_alpha"] / 100 / n / 2.2))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, a))
        for i in range(n):
            g = s["shadow"] * (i + 1) / n
            p.drawRoundedRect(card.adjusted(-g, -g + g * 0.25, g, g + g * 0.25), rad + g, rad + g)

    if s["bg"] == "glass":
        if backdrop is not None:
            p.save()
            p.setClipPath(path)
            p.drawPixmap(card, backdrop, QRectF(backdrop.rect()))
            p.restore()
        p.fillPath(path, QColor(s["color"]))
        gl = QLinearGradient(card.topLeft(), card.bottomLeft())            # легкий відблиск зверху
        gl.setColorAt(0, QColor(255, 255, 255, 22))
        gl.setColorAt(0.5, QColor(255, 255, 255, 0))
        p.fillPath(path, gl)
    elif s["bg"] == "solid":
        p.fillPath(path, QColor(s["color"]))
    elif s["bg"] == "gradient":
        a = math.radians(s["angle"])
        c, hx, hy = card.center(), math.cos(a) * card.width() / 2, math.sin(a) * card.height() / 2
        g = QLinearGradient(QPointF(c.x() - hx, c.y() - hy), QPointF(c.x() + hx, c.y() + hy))
        g.setColorAt(0, QColor(s["color"]))
        g.setColorAt(1, QColor(s["color2"]))
        p.fillPath(path, g)
    elif s["bg"] == "image":
        pm = load_pixmap(s["image"])
        p.save()
        p.setClipPath(path)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if pm.isNull():
            p.fillPath(path, QColor(s["color"]))
        else:
            draw_pixmap_fit(p, pm, card, "cover")
            p.fillPath(path, QColor(0, 0, 0, int(255 * s["image_dim"] / 100)))
        p.restore()

    p.save()
    p.setClipPath(path)                                                    # елементи не вилазять за картку
    p.translate(card.topLeft())
    for el in wd.elements:
        if el.p["visible"]:
            paint_element(p, el, card.width(), card.height())
    p.restore()

    if s["border"] and s["bg"] != "none":
        b = s["border"]
        inner, _ = card_path(card.adjusted(b / 2, b / 2, -b / 2, -b / 2), max(0, rad - b / 2))
        p.setPen(QPen(QColor(s["border_color"]), b))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(inner)
    p.setOpacity(1)


def paint_element(p, el, cw, ch):
    s = el.p
    r = el.rect(cw, ch)
    p.save()
    p.setOpacity(p.opacity() * s["opacity"] / 100)
    if s["rotation"]:
        c = r.center()
        p.translate(c)
        p.rotate(s["rotation"])
        p.translate(-c)
    if s["shadow"]:
        el.paint(p, r.translated(s["shadow_dx"], s["shadow_dy"]), color_override=s["shadow_color"])
    el.paint(p, r)
    p.restore()
