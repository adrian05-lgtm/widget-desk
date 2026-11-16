"""Налаштування: де лежать, типові значення, надійне збереження, міграції між версіями.

Правила (з уроків попередніх програм):
- усе лежить у %APPDATA%\\WidgetDesk, а не поруч з exe — оновлення нічого не стирає;
- запис атомарний: спершу тимчасовий файл, потім заміна — збій не зіпсує налаштування;
- перед записом зберігається резервна копія останнього робочого файла;
- у файлі є номер схеми; старі файли проходять через MIGRATIONS."""

import copy
import json
import os
from pathlib import Path

from core.version import APP_NAME

APP_DIR = Path(os.environ.get("APPDATA") or (Path.home() / ".config")) / APP_NAME
SETTINGS_FILE = APP_DIR / "settings.json"
LOG_FILE = APP_DIR / "log.txt"

SCHEMA = 1

DEFAULTS = {
    "schema": SCHEMA,
    "auto_update": True,       # самому перевіряти оновлення
    "skip_version": "",        # версія, яку попросили пропустити
    "fps": 60,                 # ліміт кадрів для анімацій: 30 або 60
    "eco": False,              # економний режим (менше анімацій)
    "pause_fullscreen": True,  # пауза анімацій, коли гра на весь екран
    "edit_mode": False,
    "seen_demo": False,        # стартовий віджет уже показували
    "widgets": [],             # список віджетів (з етапу 2)
}

# MIGRATIONS[n] перетворює дані схеми n у схему n+1
MIGRATIONS = {}


def ensure_dir():
    APP_DIR.mkdir(parents=True, exist_ok=True)


def read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return copy.deepcopy(default)


def write_json(path, data):
    """Атомарний запис. Повертає True, якщо вдалося."""
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        if path.exists():
            try:
                os.replace(path, path.with_suffix(path.suffix + ".bak"))
            except OSError:
                pass
        os.replace(tmp, path)
        return True
    except OSError:
        return False


def migrate(data):
    v = int(data.get("schema", 1) or 1)
    while v < SCHEMA and v in MIGRATIONS:
        data = MIGRATIONS[v](data)
        v += 1
    data["schema"] = SCHEMA
    return data


def load():
    """Завантажити налаштування. Якщо основний файл зіпсований — узяти резервну копію."""
    ensure_dir()
    data = read_json(SETTINGS_FILE, None)
    if not isinstance(data, dict):
        data = read_json(SETTINGS_FILE.with_suffix(".json.bak"), None)
    if not isinstance(data, dict):
        data = {}
    data = migrate(data)
    out = copy.deepcopy(DEFAULTS)
    out.update(data)
    if out.get("fps") not in (30, 60):
        out["fps"] = 60
    if not isinstance(out.get("widgets"), list):
        out["widgets"] = []
    return out


def save(st):
    return write_json(SETTINGS_FILE, st)
