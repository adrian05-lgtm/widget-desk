"""Офлайн-перевірка малювання: рендерить віджети у PNG без Windows.
   python tools/render_test.py out.png"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from PyQt6.QtCore import QRectF  # noqa: E402
from PyQt6.QtGui import QColor, QImage, QLinearGradient, QPainter  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from model.widget import Widget, demo_widget  # noqa: E402
from render import painter  # noqa: E402


def render(widgets, path, size=(1100, 520)):
    img = QImage(size[0], size[1], QImage.Format.Format_ARGB32_Premultiplied)
    p = QPainter(img)
    g = QLinearGradient(0, 0, size[0], size[1])
    g.setColorAt(0, QColor("#203a6b"))
    g.setColorAt(1, QColor("#5a2a6e"))
    p.fillRect(img.rect(), g)
    for wd in widgets:
        painter.paint_widget(p, wd, QRectF(wd.x, wd.y, wd.w, wd.h))
    p.end()
    img.save(path)


if __name__ == "__main__":
    app = QApplication([])
    a = demo_widget()
    a.x, a.y = 40, 40
    b = Widget(a.to_dict()); b.id = "b"; b.x, b.y, b.w, b.h = 420, 40, 560, 260      # той самий, розтягнутий
    b.p.update(bg="gradient", color="#e61b1035", color2="#e6b3122e", radius=40)
    c = Widget({"x": 40, "y": 270, "w": 340, "h": 200, "props": {"bg": "solid", "color": "#f0f5f5fa", "radius": 28,
                                                                    "border": 0},
                "elements": [
                    {"type": "image", "props": {"x": 16, "y": 16, "w": 110, "h": 110, "radius": 55}},
                    {"type": "text", "props": {"text": "Субота", "x": 140, "y": 20, "w": 190, "h": 44, "size": 34,
                                               "bold": True, "color": "#ff1c1c28", "italic": True}},
                    {"type": "text", "props": {"text": "Повернутий текст", "x": 140, "y": 78, "w": 190, "h": 26,
                                               "size": 14, "color": "#ff55556a", "rotation": -6}},
                    {"type": "shape", "props": {"shape": "ellipse", "ax": "right", "ay": "bottom", "x": 16, "y": 16,
                                                "w": 44, "h": 44, "fill": "#ffb3122e", "shadow": True,
                                                "shadow_dy": 4, "shadow_color": "#55000000"}},
                    {"type": "icon", "props": {"icon": "play", "ax": "right", "ay": "bottom", "x": 27, "y": 27,
                                               "w": 22, "h": 22}},
                    {"type": "bogus", "props": {}}, "сміття",
                    {"type": "shape", "props": {"shape": "rect", "ax": "stretch", "ay": "bottom", "x": 16, "y": 70,
                                                "h": 6, "radius": 3, "fill": "#22000000", "w": "зламано"}},
                ]})
    d = Widget({"x": 420, "y": 320, "w": 560, "h": 170, "props": {"bg": "solid", "color": "#e60a0a0c", "radius": 16,
                                                                     "border_color": "#88b3122e"},
                "elements": [
                    {"type": "progress", "props": {"x": 24, "y": 28, "w": 300, "h": 20, "value": 65}},
                    {"type": "progress", "props": {"x": 24, "y": 64, "w": 300, "h": 20, "value": 30, "track": 4,
                                                   "gradient": True, "fill": "#ff3ec6ff", "knob_shape": "bar",
                                                   "knob_size": 16}},
                    {"type": "progress", "props": {"x": 24, "y": 100, "w": 300, "h": 20, "source": "minute",
                                                   "fill": "#ffb3122e", "knob": False, "track": 8}},
                    {"type": "progress", "props": {"x": 350, "y": 20, "w": 20, "h": 130, "orient": "v",
                                                   "value": 75, "knob_shape": "square"}},
                    {"type": "button", "props": {"x": 390, "y": 24, "w": 150, "h": 40, "icon": "play",
                                                 "text": "Грати"}},
                    {"type": "button", "props": {"x": 390, "y": 76, "w": 150, "h": 40, "text": "Скляна",
                                                 "bg": "#26ffffff", "border": 1, "radius": 999}},
                    {"type": "button", "props": {"x": 390, "y": 126, "w": 40, "h": 32, "text": "", "icon": "heart",
                                                 "bg": "#ffb3122e", "radius": 999, "icon_size": 16}},
                ]})
    d.elements[5].state = "hover"
    render([a, b, c, d], sys.argv[1] if len(sys.argv) > 1 else "render_test.png")
    print("elements in c:", len(c.elements), "| round-trip equal:", Widget(c.to_dict()).to_dict() == c.to_dict())
