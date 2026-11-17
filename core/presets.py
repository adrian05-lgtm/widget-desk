"""Стилі: свої (зберігаються у %APPDATA%\\WidgetDesk\\styles.json) і готові ★ (вбудовані, не видаляються).

Стиль — це лише ВИГЛЯД: кольори, шрифти, заокруглення, тіні. Положення, розмір, сам текст,
шлях до картинки і дія кнопки в стиль не входять — тому стиль можна накласти на будь-який елемент
того ж типу, і він не «зламає» розкладку.

Вид стилю (kind): "card" — картка віджета; "el:text", "el:shape"… — елементи."""

import copy

from core import config
from core.props import clean

STYLES_FILE = config.APP_DIR / "styles.json"
EXCLUDE = {"visible", "x", "y", "w", "h", "ax", "ay", "text", "path", "image", "target", "action",
           "value", "source"}


def kind_of(target):
    """target — None (картка) або елемент."""
    return "card" if target is None else "el:" + target.TYPE


def style_keys(schema):
    return [p.key for p in schema if p.key not in EXCLUDE]


def extract(schema, values):
    return {k: copy.deepcopy(values[k]) for k in style_keys(schema) if k in values}


# ---------------- свої стилі ----------------
def _all():
    d = config.read_json(STYLES_FILE, {})
    return d if isinstance(d, dict) else {}


def load(kind):
    lst = _all().get(kind, [])
    return [s for s in lst if isinstance(s, dict) and isinstance(s.get("name"), str)
            and isinstance(s.get("values"), dict)]


def save_list(kind, lst):
    d = _all()
    d[kind] = lst
    return config.write_json(STYLES_FILE, d)


# ---------------- готові ★ ----------------
_BUILTIN = {
    "card": [
        ("Темне скло", {}),
        ("Світле скло", {"color": "#55ffffff", "blur": 28, "border_color": "#66ffffff", "radius": 24,
                         "shadow": 16, "shadow_alpha": 30}),
        ("Кривавий місяць", {"bg": "solid", "color": "#e60a0a0c", "border": 1, "border_color": "#88b3122e",
                             "radius": 16, "shadow": 22, "shadow_alpha": 60}),
        ("Синтвейв", {"bg": "gradient", "color": "#cc2a0a4a", "color2": "#cc8a1a6e", "angle": 90,
                      "border": 1, "border_color": "#99ff5ca8", "radius": 18}),
        ("Біла картка (macOS)", {"bg": "solid", "color": "#f2f5f5fa", "border": 0, "radius": 28,
                                 "shadow": 20, "shadow_alpha": 35}),
        ("Без фону", {"bg": "none"}),
    ],
    "el:text": [
        ("Великий заголовок", {"size": 48, "bold": True, "color": "#ffffffff"}),
        ("Підпис", {"size": 14, "color": "#b4ffffff"}),
        ("Рукописний", {"font": "Segoe Script", "size": 34}),
        ("Великими літерами", {"upper": True, "spacing": 4, "size": 13, "bold": True, "color": "#c8ffffff"}),
        ("Темний текст", {"color": "#ff1c1c28"}),
        ("Кривавий місяць", {"color": "#ffb3122e", "bold": True}),
    ],
    "el:shape": [
        ("Акцентна смужка", {"fill": "#ff7b5cff", "gradient": True, "fill2": "#ffff5ca8", "angle": 90,
                             "radius": 3}),
        ("Тонкий розділювач", {"shape": "line", "fill": "#30ffffff", "radius": 0}),
        ("Червоне коло", {"shape": "ellipse", "fill": "#ffb3122e"}),
    ],
    "el:progress": [
        ("Тонкий", {"track": 4, "knob": False, "fill": "#ffffffff", "track_color": "#33ffffff"}),
        ("Неоновий", {"track": 6, "gradient": True, "fill": "#ff3ec6ff", "fill2": "#ff7b5cff",
                      "knob": True, "knob_color": "#ffffffff"}),
        ("Кривавий місяць", {"fill": "#ffb3122e", "track_color": "#26ffffff", "knob": True,
                             "knob_shape": "bar", "knob_size": 16}),
    ],
    "el:button": [
        ("Фіолетова", {}),
        ("Скляна", {"bg": "#26ffffff", "hover": "#40ffffff", "down": "#1affffff", "border": 1,
                    "border_color": "#4dffffff"}),
        ("Пігулка", {"radius": 999}),
        ("Кривавий місяць", {"bg": "#ffb3122e", "hover": "#ffcc1a3a", "down": "#ff8a0e23"}),
    ],
    "el:icon": [
        ("Біла", {"color": "#ffffffff"}),
        ("Жовта", {"color": "#ffffc857"}),
        ("Червона", {"color": "#ffb3122e"}),
    ],
}


def builtins(kind, schema):
    """Готові стилі: повні набори значень (типові + зміни), щоб від попереднього стилю нічого не лишалось."""
    out = []
    for name, over in _BUILTIN.get(kind, []):
        full = clean(schema, over)
        out.append({"name": name, "values": extract(schema, full)})
    return out
