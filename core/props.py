"""Опис властивостей. Кожна властивість описується ОДИН раз — і з цього опису автоматично
виходять: перевірка значення, типове значення, скидання і (з етапу 4) поле в редакторі.

Види (kind): int, float, bool, color (#AARRGGBB), font, choice, text, image."""

from PyQt6.QtGui import QColor


class Prop:
    def __init__(self, key, label, kind, default, group="Загальне", lo=None, hi=None, step=1,
                 choices=None, hint=""):
        self.key, self.label, self.kind, self.default = key, label, kind, default
        self.group, self.lo, self.hi, self.step = group, lo, hi, step
        self.choices = choices or []          # [(значення, назва), ...]
        self.hint = hint

    def clean(self, v):
        """Привести будь-що до правильного значення; якщо не виходить — типове."""
        try:
            if self.kind == "int":
                v = int(round(float(v)))
                return max(self.lo, min(self.hi, v)) if self.lo is not None else v
            if self.kind == "float":
                v = float(v)
                return max(self.lo, min(self.hi, v)) if self.lo is not None else v
            if self.kind == "bool":
                return bool(v)
            if self.kind == "color":
                return v if isinstance(v, str) and QColor(v).isValid() else self.default
            if self.kind == "choice":
                return v if v in [c[0] for c in self.choices] else self.default
            if self.kind in ("text", "font", "image"):
                return v if isinstance(v, str) else self.default
        except (TypeError, ValueError):
            pass
        return self.default


def defaults(schema):
    return {p.key: p.default for p in schema}


def clean(schema, data):
    """Словник лише з відомими ключами і перевіреними значеннями."""
    data = data if isinstance(data, dict) else {}
    return {p.key: p.clean(data.get(p.key, p.default)) for p in schema}


def by_key(schema):
    return {p.key: p for p in schema}
