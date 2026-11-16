"""Віджет = картка (фон, рамка, тінь) + список елементів. Усе це — дані, які зберігаються в JSON."""

import uuid

from core.props import Prop, clean
from model import element

CARD = [
    Prop("bg", "Фон", "choice", "glass", "Фон",
         choices=[("glass", "Скло"), ("solid", "Колір"), ("gradient", "Градієнт"), ("image", "Картинка"),
                  ("none", "Без фону")]),
    Prop("color", "Колір фону", "color", "#d912141f", "Фон"),
    Prop("color2", "Другий колір (градієнт)", "color", "#d93a1f5c", "Фон"),
    Prop("angle", "Кут градієнта, °", "int", 90, "Фон", 0, 360),
    Prop("image", "Картинка фону", "image", "", "Фон"),
    Prop("image_dim", "Затемнення картинки, %", "int", 20, "Фон", 0, 100),
    Prop("radius", "Заокруглення кутів", "int", 22, "Форма", 0, 400),
    Prop("border", "Товщина рамки", "int", 1, "Рамка", 0, 30),
    Prop("border_color", "Колір рамки", "color", "#3cffffff", "Рамка"),
    Prop("shadow", "Розмір тіні", "int", 18, "Тінь", 0, 60),
    Prop("shadow_alpha", "Сила тіні, %", "int", 45, "Тінь", 0, 100),
    Prop("opacity", "Прозорість віджета, %", "int", 100, "Вигляд", 5, 100),
]

MIN_W, MIN_H = 40, 30
MAX_W, MAX_H = 4000, 3000


def _num(v, default, lo, hi):
    try:
        return max(lo, min(hi, int(round(float(v)))))
    except (TypeError, ValueError):
        return default


class Widget:
    def __init__(self, data=None):
        data = data if isinstance(data, dict) else {}
        self.id = str(data.get("id") or uuid.uuid4().hex[:8])
        self.name = str(data.get("name") or "Віджет")
        self.x = _num(data.get("x"), 80, -20000, 20000)
        self.y = _num(data.get("y"), 80, -20000, 20000)
        self.w = _num(data.get("w"), 300, MIN_W, MAX_W)
        self.h = _num(data.get("h"), 180, MIN_H, MAX_H)
        self.locked = bool(data.get("locked", False))
        self.p = clean(CARD, data.get("props"))
        self.elements = []
        seen = set()
        for d in data.get("elements") if isinstance(data.get("elements"), list) else []:
            el = element.make(d)
            if el is None:
                continue                                   # зіпсований елемент пропускаємо, віджет живе далі
            if el.id in seen:
                el.id = uuid.uuid4().hex[:8]
            seen.add(el.id)
            self.elements.append(el)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "x": self.x, "y": self.y, "w": self.w, "h": self.h,
                "locked": self.locked, "props": dict(self.p),
                "elements": [e.to_dict() for e in self.elements]}

    def is_live(self):
        return any(e.is_live() and e.p["visible"] for e in self.elements)


def demo_widget():
    """Стартовий віджет: показує, що вміє ядро (живий час, дата, фігури, іконка)."""
    return Widget({
        "name": "Привіт", "x": 90, "y": 90, "w": 340, "h": 190,
        "elements": [
            {"type": "shape", "name": "Смужка", "props": {"x": 22, "y": 24, "w": 5, "h": 62, "radius": 3,
                                                           "gradient": True, "angle": 90}},
            {"type": "text", "name": "Час", "props": {"text": "{time}", "x": 40, "y": 14, "w": 220, "h": 62,
                                                      "size": 54, "bold": True, "shadow": True}},
            {"type": "text", "name": "Дата", "props": {"text": "{weekday}, {date}", "x": 42, "y": 74, "w": 280,
                                                       "h": 24, "size": 15, "color": "#c8ffffff"}},
            {"type": "shape", "name": "Лінія", "props": {"shape": "line", "ax": "stretch", "x": 22, "y": 116,
                                                         "h": 1, "radius": 0, "fill": "#30ffffff"}},
            {"type": "icon", "name": "Зірка", "props": {"icon": "star", "x": 22, "y": 20, "ay": "bottom",
                                                        "w": 22, "h": 22, "color": "#ffffc857"}},
            {"type": "text", "name": "Підпис", "props": {"text": "WidgetDesk — перший віджет", "x": 54, "y": 20,
                                                         "ay": "bottom", "w": 260, "h": 22, "size": 13,
                                                         "color": "#b4ffffff"}},
        ],
    })
