"""Редактор вигляду віджета — «найменші деталі».

Ліворуч — шари: картка і всі елементи (галочка = показувати, подвійний клік = перейменувати).
Праворуч — властивості вибраного шару, згруповані по розділах. Поля будуються автоматично з опису
властивостей, тому новий тип елемента не потребує окремого редактора.

Усі зміни видно на робочому столі одразу. «Зберегти» — залишити, «Скасувати» — повернути, як було
до відкриття редактора. Ctrl+Z — крок назад усередині редактора."""

import time

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (QAbstractItemView, QComboBox, QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
                             QListWidget, QListWidgetItem, QMenu, QMessageBox, QPushButton, QScrollArea,
                             QSizePolicy, QToolButton, QVBoxLayout, QWidget)

from core import presets
from core.props import Prop
from model import element
from model.widget import CARD, MAX_H, MAX_W, MIN_H, MIN_W
from ui.controls import make_control

SIZE = [Prop("w", "Ширина віджета", "int", 340, "Розмір", MIN_W, MAX_W),
        Prop("h", "Висота віджета", "int", 170, "Розмір", MIN_H, MAX_H),
        Prop("locked", "Закріпити на місці", "bool", False, "Розмір",
             hint="Закріплений віджет не рухається і не змінює розмір мишкою.")]
CARD_SCHEMA = SIZE + CARD
FOLDED = {"Тінь", "Вигляд"}              # розділи, згорнуті за замовчуванням
HISTORY = 80


class Inspector(QWidget):
    closed = pyqtSignal()

    def __init__(self, ctl, wd):
        super().__init__(None, Qt.WindowType.Window)
        self.setObjectName("window")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.ctl, self.wd = ctl, wd
        self.host = ctl.host_of(wd)
        self.snapshot = wd.to_dict()                         # для «Скасувати»
        self.before_all = [w.to_dict() for w in ctl.widgets]  # для «Повернути» вже після збереження
        self.hist = []
        self._last = (0.0, None)
        self.sel = None                                      # None = картка, інакше елемент
        self.rows = {}
        self.folded = set(FOLDED)
        self._finished = False
        self.setWindowTitle(f"Вигляд віджета — {wd.name}")
        self._build()
        self.rebuild_layers()
        self.select(None)
        self._place()

    # ================= побудова вікна =================
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 12)
        root.setSpacing(10)

        top = QHBoxLayout()
        lbl = QLabel("Назва віджета")
        lbl.setObjectName("hint")
        self.name_edit = QLineEdit(self.wd.name)
        self.name_edit.textEdited.connect(self._rename_widget)
        top.addWidget(lbl)
        top.addWidget(self.name_edit, 1)
        root.addLayout(top)

        body = QHBoxLayout()
        body.setSpacing(12)
        root.addLayout(body, 1)

        # ---- шари ----
        left = QFrame()
        left.setObjectName("card")
        left.setFixedWidth(232)
        lv = QVBoxLayout(left)
        lv.setContentsMargins(10, 10, 10, 10)
        t = QLabel("Шари")
        t.setObjectName("section")
        lv.addWidget(t)
        self.layers = QListWidget()
        self.layers.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        self.layers.currentRowChanged.connect(self._layer_row)
        self.layers.itemChanged.connect(self._layer_item_changed)
        lv.addWidget(self.layers, 1)
        add = QPushButton("＋  Додати елемент")
        add.setObjectName("primary")
        m = QMenu(add)
        for t_, title in element.ADD_MENU:
            m.addAction(title).triggered.connect(lambda _=False, t_=t_: self.add_element(t_))
        add.setMenu(m)
        lv.addWidget(add)
        tools = QHBoxLayout()
        tools.setSpacing(4)
        for text, tip, fn in (("↑", "Вище (поверх інших)", lambda: self.move_element(+1)),
                              ("↓", "Нижче", lambda: self.move_element(-1)),
                              ("⧉", "Дублювати", self.duplicate_element),
                              ("✕", "Видалити", self.delete_element)):
            b = QToolButton()
            b.setText(text)
            b.setToolTip(tip)
            b.clicked.connect(fn)
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            tools.addWidget(b)
        lv.addLayout(tools)
        hint = QLabel("Клік по елементу на робочому столі теж вибирає його, а перетягування — рухає.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        lv.addWidget(hint)
        body.addWidget(left)

        # ---- властивості ----
        right = QVBoxLayout()
        right.setSpacing(8)
        self.title = QLabel()
        self.title.setObjectName("title")
        right.addWidget(self.title)
        right.addWidget(self._styles_bar())
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.panel = QWidget()
        self.panel.setObjectName("panel")
        self.scroll.setWidget(self.panel)
        right.addWidget(self.scroll, 1)
        body.addLayout(right, 1)

        # ---- низ ----
        self.status = QLabel("")
        self.status.setObjectName("hint")
        root.addWidget(self.status)
        bottom = QHBoxLayout()
        self.b_undo = QPushButton("↶ Крок назад")
        self.b_undo.setToolTip("Ctrl+Z")
        self.b_undo.clicked.connect(self.undo)
        b_reset = QPushButton("Скинути вигляд…")
        b_reset.setToolTip("Повернути типові кольори, шрифти й інше для вибраного шару")
        b_reset.clicked.connect(self.reset_style)
        b_cancel = QPushButton("Скасувати")
        b_cancel.clicked.connect(self.cancel)
        b_save = QPushButton("Зберегти")
        b_save.setObjectName("primary")
        b_save.clicked.connect(self.save)
        bottom.addWidget(self.b_undo)
        bottom.addWidget(b_reset)
        bottom.addStretch(1)
        bottom.addWidget(b_cancel)
        bottom.addWidget(b_save)
        root.addLayout(bottom)
        QShortcut(QKeySequence.StandardKey.Undo, self, activated=self.undo)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.save)
        self._update_undo()

    def _styles_bar(self):
        bar = QFrame()
        bar.setObjectName("card")
        h = QHBoxLayout(bar)
        h.setContentsMargins(10, 6, 6, 6)
        lb = QLabel("Стиль")
        lb.setObjectName("hint")
        self.style_combo = QComboBox()
        self.style_combo.setMinimumWidth(180)
        self.style_combo.activated.connect(self._style_picked)
        save = QPushButton("💾 Зберегти як новий")
        save.clicked.connect(self.style_save_new)
        more = QToolButton()
        more.setText("⋯")
        more.setToolTip("Інші дії зі стилем")
        more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        mm = QMenu(more)
        mm.addAction("Перезаписати вибраний свій стиль").triggered.connect(self.style_overwrite)
        mm.addAction("Перейменувати вибраний свій стиль").triggered.connect(self.style_rename)
        mm.addAction("Видалити вибраний свій стиль").triggered.connect(self.style_delete)
        mm.addSeparator()
        mm.addAction("Копіювати стиль").triggered.connect(self.style_copy)
        mm.addAction("Вставити стиль").triggered.connect(self.style_paste)
        more.setMenu(mm)
        h.addWidget(lb)
        h.addWidget(self.style_combo, 1)
        h.addWidget(save)
        h.addWidget(more)
        return bar

    def _place(self):
        """Поставити редактор поруч із віджетом, але щоб він повністю вміщався на екрані."""
        g = self.ctl.qapp.primaryScreen().availableGeometry()
        w, h = min(800, g.width() - 40), min(700, g.height() - 40)
        self.resize(w, h)
        wd = self.wd
        if wd.x + wd.w + 20 + w <= g.right():
            x = wd.x + wd.w + 20
        elif wd.x - 20 - w >= g.left():
            x = wd.x - 20 - w
        else:
            x = g.right() - w - 10
        y = max(g.top() + 10, min(wd.y, g.bottom() - h - 10))
        self.move(int(x), int(y))

    # ================= шари =================
    def target_list(self):
        """Порядок у списку: картка, потім елементи згори вниз (верхній — той, що малюється поверх)."""
        return [None] + list(reversed(self.wd.elements))

    def rebuild_layers(self):
        self.layers.blockSignals(True)
        self.layers.clear()
        it = QListWidgetItem("▣  Картка (фон, рамка, тінь)")
        it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        self.layers.addItem(it)
        for el in reversed(self.wd.elements):
            it = QListWidgetItem(el.name)
            it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                        | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEditable)
            it.setCheckState(Qt.CheckState.Checked if el.p["visible"] else Qt.CheckState.Unchecked)
            it.setToolTip(f"{el.TITLE}. Галочка — показувати. Подвійний клік — перейменувати.")
            self.layers.addItem(it)
        self.layers.blockSignals(False)
        self._mark_current()

    def _mark_current(self):
        targets = self.target_list()
        row = next((i for i, t in enumerate(targets) if t is self.sel), 0)
        self.layers.blockSignals(True)
        self.layers.setCurrentRow(row)
        self.layers.blockSignals(False)

    def _layer_row(self, row):
        targets = self.target_list()
        if 0 <= row < len(targets):
            self.select(targets[row], from_list=True)

    def _layer_item_changed(self, item):
        row = self.layers.row(item)
        targets = self.target_list()
        if not (0 < row < len(targets)):
            return
        el = targets[row]
        vis = item.checkState() == Qt.CheckState.Checked
        name = item.text().strip() or el.TITLE
        if vis != el.p["visible"] or name != el.name:
            self.push()
            el.p["visible"] = vis
            el.name = name
            self.host.sync()

    def select(self, target, from_list=False):
        self.sel = target
        if not from_list:
            self._mark_current()
        self.title.setText("Картка віджета" if target is None else f"{target.TITLE}:  {target.name}")
        self.build_props()
        self.reload_styles()
        self.host.update()

    # ================= властивості =================
    def schema(self):
        return CARD_SCHEMA if self.sel is None else self.sel.schema()

    def values(self):
        if self.sel is None:
            v = dict(self.wd.p)
            v.update(w=self.wd.w, h=self.wd.h, locked=self.wd.locked)
            return v
        return self.sel.p

    def build_props(self):
        self.panel = QWidget()                              # нова панель; стара видаляється разом із полями
        self.panel.setObjectName("panel")
        self.scroll.setWidget(self.panel)
        lay = QVBoxLayout(self.panel)
        lay.setContentsMargins(0, 0, 16, 0)                 # місце під смугу прокрутки
        lay.setSpacing(4)
        self.rows = {}
        schema = [p for p in self.schema() if p.key != "visible"]
        own = [p.group for p in (self.sel.OWN if self.sel is not None else [])]
        groups = []
        for g in own + [p.group for p in schema]:          # спершу розділи самого елемента, потім спільні
            if g not in groups:
                groups.append(g)
        vals = self.values()
        for g in groups:
            props = [p for p in schema if p.group == g]
            if not props:
                continue
            head = QToolButton(self.panel)
            head.setObjectName("group")
            head.setCheckable(True)
            head.setChecked(g not in self.folded)
            head.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            head.setArrowType(Qt.ArrowType.DownArrow if head.isChecked() else Qt.ArrowType.RightArrow)
            head.setText(g)
            head.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            box = QFrame(self.panel)                        # одразу з батьком — інакше Qt покаже його окремим вікном
            box.setObjectName("card")
            bl = QVBoxLayout(box)
            bl.setContentsMargins(12, 8, 8, 8)
            bl.setSpacing(6)
            head.toggled.connect(lambda on, g=g, b=box, h=head: self._fold(g, b, h, on))
            lay.addWidget(head)
            lay.addWidget(box)
            if not head.isChecked():
                box.hide()
            for prop in props:
                row = QWidget(box)
                rl = QHBoxLayout(row)
                rl.setContentsMargins(0, 0, 0, 0)
                name = QLabel(prop.label + ("  ⓘ" if prop.hint else ""))
                name.setFixedWidth(178)
                name.setToolTip(prop.hint or prop.label)
                ctrl = make_control(prop, self.ctl)
                ctrl.set_value(vals.get(prop.key, prop.default))
                ctrl.changed.connect(lambda v, k=prop.key: self.on_change(k, v))
                rst = QToolButton()
                rst.setText("↺")
                rst.setToolTip("Типове значення")
                rst.clicked.connect(lambda _=False, pr=prop: self._reset_one(pr))
                rl.addWidget(name)
                rl.addWidget(ctrl, 1)
                rl.addWidget(rst, 0, Qt.AlignmentFlag.AlignTop)
                row.setMinimumHeight(max(32, ctrl.sizeHint().height()))   # рядки не стискаються — є прокрутка
                bl.addWidget(row)
                self.rows[prop.key] = (row, ctrl, prop)
        lay.addStretch(1)
        self.update_visibility()

    def _fold(self, group, box, head, on):
        box.setVisible(on)
        head.setArrowType(Qt.ArrowType.DownArrow if on else Qt.ArrowType.RightArrow)
        (self.folded.discard if on else self.folded.add)(group)

    def update_visibility(self):
        vals = self.values()
        for row, _c, prop in self.rows.values():
            row.setVisible(prop.shown(vals))

    def refresh_values(self, keys=None):
        """Оновити поля після зміни ззовні (перетягнули мишкою, крок назад) — без зайвих сигналів."""
        vals = self.values()
        for k, (_row, ctrl, prop) in self.rows.items():
            if keys is None or k in keys:
                ctrl.set_value(vals.get(k, prop.default))
        self.update_visibility()

    def on_change(self, key, v):
        prop = next((p for p in self.schema() if p.key == key), None)
        if prop is None:
            return
        v = prop.clean(v)
        self.push(key)
        if self.sel is None:
            if key in ("w", "h"):
                setattr(self.wd, key, v)
            elif key == "locked":
                self.wd.locked = v
            else:
                self.wd.p[key] = v
        else:
            self.sel.p[key] = v
        self.host.sync()
        self.update_visibility()

    def _reset_one(self, prop):
        self.on_change(prop.key, prop.default)
        self.refresh_values([prop.key])

    def _rename_widget(self, text):
        self.push("name")
        self.wd.name = text.strip() or "Віджет"
        self.setWindowTitle(f"Вигляд віджета — {self.wd.name}")

    # ================= кроки назад =================
    def push(self, key=None):
        """Запам'ятати стан перед зміною. Поспіль зміни одного поля (тягнеш повзунок) — один крок."""
        now = time.monotonic()
        tag = (id(self.sel), key)
        if key is None or tag != self._last[1] or now - self._last[0] > 0.8:
            sid = None if self.sel is None else self.sel.id
            self.hist.append((self.wd.to_dict(), sid))
            del self.hist[:-HISTORY]
        self._last = (now, tag)
        self._update_undo()

    def _update_undo(self):
        self.b_undo.setEnabled(bool(self.hist))

    def undo(self):
        if not self.hist:
            self.status.setText("Немає кроків назад.")
            return
        data, sid = self.hist.pop()
        self._last = (0.0, None)
        self.wd.assign(data)
        self.host.sync()
        self.name_edit.setText(self.wd.name)
        self.sel = next((e for e in self.wd.elements if e.id == sid), None)
        self.rebuild_layers()
        self.select(self.sel)
        self._update_undo()
        self.status.setText("Крок назад.")

    # ================= елементи =================
    def add_element(self, type_):
        self.push()
        cls = element.TYPES[type_]
        n = len(self.wd.elements)
        el = cls({"props": {"x": 16 + 8 * (n % 6), "y": 16 + 8 * (n % 6)}})
        if type_ == "text":
            el.p["text"] = "Новий текст"
        self.wd.elements.append(el)
        self.host.sync()
        self.rebuild_layers()
        self.select(el)
        self.status.setText(f"Додано: {el.TITLE}. Перетягни його мишкою на віджеті або задай відступи нижче.")

    def duplicate_element(self):
        if self.sel is None:
            self.status.setText("Вибери елемент у списку шарів.")
            return
        self.push()
        d = self.sel.to_dict()
        d.pop("id")
        d["name"] = self.sel.name + " (копія)"
        el = element.make(d)
        el.p["x"] += 10
        el.p["y"] += 10
        self.wd.elements.insert(self.wd.elements.index(self.sel) + 1, el)
        self.host.sync()
        self.rebuild_layers()
        self.select(el)

    def delete_element(self):
        if self.sel is None:
            self.status.setText("Картку видалити не можна — вибери елемент у списку шарів.")
            return
        self.push()
        name = self.sel.name
        i = self.wd.elements.index(self.sel)
        self.wd.elements.remove(self.sel)
        self.host.sync()
        self.rebuild_layers()
        rest = self.wd.elements
        self.select(rest[min(i, len(rest) - 1)] if rest else None)
        self.status.setText(f"Видалено «{name}». Ctrl+Z — повернути.")

    def move_element(self, step):
        if self.sel is None:
            return
        els = self.wd.elements
        i = els.index(self.sel)
        j = i + step
        if not 0 <= j < len(els):
            return
        self.push()
        els[i], els[j] = els[j], els[i]
        self.host.sync()
        self.rebuild_layers()

    # ================= стилі =================
    def style_kind(self):
        return presets.kind_of(self.sel)

    def style_schema(self):
        """Що входить у стиль: для картки — лише вигляд (без розміру і «закріпити»)."""
        return CARD if self.sel is None else self.sel.schema()

    def reload_styles(self, select_name=None):
        kind, schema = self.style_kind(), self.style_schema()
        self._builtins = presets.builtins(kind, schema)
        self._mine = presets.load(kind)
        c = self.style_combo
        c.blockSignals(True)
        c.clear()
        c.addItem("— вибери стиль —", None)
        for i, s in enumerate(self._builtins):
            c.addItem("★ " + s["name"], ("b", i))
        for i, s in enumerate(self._mine):
            c.addItem(s["name"], ("m", i))
        idx = 0
        if select_name is not None:
            idx = max(0, c.findText(select_name))
        c.setCurrentIndex(idx)
        c.blockSignals(False)

    def _style_picked(self, idx):
        d = self.style_combo.itemData(idx)
        if not d:
            return
        src = self._builtins if d[0] == "b" else self._mine
        st = src[d[1]]
        self.apply_style_values(st["values"])
        self.status.setText(f"Застосовано стиль «{st['name']}». Не подобається — Ctrl+Z.")

    def apply_style_values(self, vals):
        allowed = set(presets.style_keys(self.style_schema()))
        self.push()
        tgt = self.wd.p if self.sel is None else self.sel.p
        schema = {p.key: p for p in self.style_schema()}
        for k, v in vals.items():
            if k in allowed:
                tgt[k] = schema[k].clean(v)
        self.host.sync()
        self.refresh_values()

    def _current_values(self):
        return presets.extract(self.style_schema(), self.values())

    def _mine_selected(self):
        d = self.style_combo.currentData()
        return d[1] if d and d[0] == "m" else None

    def style_save_new(self):
        n = len(self._mine) + 1
        name, ok = QInputDialog.getText(self, "Новий стиль", "Назва стилю:", text=f"Мій стиль {n}")
        name = name.strip()
        if not ok or not name:
            return
        mine = presets.load(self.style_kind())
        same = next((i for i, s in enumerate(mine) if s["name"].lower() == name.lower()), None)
        if same is not None:
            if not self.ask(f"Свій стиль «{name}» уже є. Замінити його?"):
                return
            mine[same]["values"] = self._current_values()
        else:
            mine.append({"name": name, "values": self._current_values()})
        if presets.save_list(self.style_kind(), mine):
            self.reload_styles(select_name=name)
            self.status.setText(f"Стиль «{name}» збережено. Своїх стилів цього виду: {len(mine)}.")
        else:
            self.status.setText("Не вдалося записати файл стилів.")

    def style_overwrite(self):
        i = self._mine_selected()
        if i is None:
            self.status.setText("Спершу вибери у списку СВІЙ стиль (готові ★ змінювати не можна).")
            return
        name = self._mine[i]["name"]
        if not self.ask(f"Записати поточний вигляд у стиль «{name}»?"):
            return
        self._mine[i]["values"] = self._current_values()
        presets.save_list(self.style_kind(), self._mine)
        self.reload_styles(select_name=name)
        self.status.setText(f"Стиль «{name}» оновлено.")

    def style_rename(self):
        i = self._mine_selected()
        if i is None:
            self.status.setText("Спершу вибери у списку СВІЙ стиль.")
            return
        old = self._mine[i]["name"]
        name, ok = QInputDialog.getText(self, "Перейменувати стиль", "Нова назва:", text=old)
        name = name.strip()
        if ok and name:
            self._mine[i]["name"] = name
            presets.save_list(self.style_kind(), self._mine)
            self.reload_styles(select_name=name)

    def style_delete(self):
        i = self._mine_selected()
        if i is None:
            self.status.setText("Спершу вибери у списку СВІЙ стиль (готові ★ видалити не можна).")
            return
        name = self._mine[i]["name"]
        if not self.ask(f"Видалити стиль «{name}»? Повернути його не вийде."):
            return
        del self._mine[i]
        presets.save_list(self.style_kind(), self._mine)
        self.reload_styles()
        self.status.setText(f"Стиль «{name}» видалено.")

    def style_copy(self):
        self.ctl.style_clip = (self.style_kind(), self._current_values())
        self.status.setText("Стиль скопійовано. Вибери інший шар або віджет і натисни «Вставити стиль».")

    def style_paste(self):
        clip = getattr(self.ctl, "style_clip", None)
        if not clip:
            self.status.setText("Спершу скопіюй стиль.")
            return
        kind, vals = clip
        allowed = set(presets.style_keys(self.style_schema()))
        common = {k: v for k, v in vals.items() if k in allowed}
        if not common:
            self.status.setText("Цей стиль не підходить до вибраного шару.")
            return
        self.apply_style_values(common)
        part = "" if kind == self.style_kind() else " (лише спільні властивості — інший тип)"
        self.status.setText("Стиль вставлено" + part + ".")

    def reset_style(self):
        what = "картки" if self.sel is None else f"елемента «{self.sel.name}»"
        if not self.ask(f"Повернути типовий вигляд для {what}?\n"
                        "Положення, розмір і текст залишаться. Ctrl+Z — повернути назад."):
            return
        self.apply_style_values({p.key: p.default for p in self.style_schema()})
        self.status.setText("Вигляд скинуто до типового.")

    # ================= завершення =================
    def ask(self, text):
        box = QMessageBox(self)
        box.setWindowTitle("WidgetDesk")
        box.setText(text)
        yes = box.addButton("Так", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Ні", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        return box.clickedButton() is yes

    def dirty(self):
        return self.wd.to_dict() != self.snapshot

    def _commit(self):
        if self.dirty():
            self.ctl.undo_stack.append(self.before_all)       # одна дія «Повернути» скасує все редагування
            del self.ctl.undo_stack[:-30]
        self.ctl.clamp_to_screen(self.wd)
        self.host.sync()
        self.ctl.save()
        self._finished = True

    def _revert(self):
        self.wd.assign(self.snapshot)
        self.ctl.clamp_to_screen(self.wd)
        self.host.sync()                                     # урок: після масової зміни — усе видно і на місці
        self.ctl.restack()
        self.ctl.save()
        self._finished = True

    def save(self):
        self._commit()
        self.close()

    def cancel(self):
        self._revert()
        self.close()

    def try_close(self):
        """Закрити з питанням про незбережене. Повертає True, якщо редактор закрито."""
        self.close()
        return self._finished

    def closeEvent(self, e):
        if not self._finished:
            if self.dirty():
                box = QMessageBox(self)
                box.setWindowTitle("WidgetDesk")
                box.setText("Зберегти зміни у вигляді віджета?")
                b_save = box.addButton("Зберегти", QMessageBox.ButtonRole.AcceptRole)
                b_drop = box.addButton("Не зберігати", QMessageBox.ButtonRole.DestructiveRole)
                box.addButton("Повернутись до редагування", QMessageBox.ButtonRole.RejectRole)
                box.exec()
                if box.clickedButton() is b_save:
                    self._commit()
                elif box.clickedButton() is b_drop:
                    self._revert()
                else:
                    e.ignore()
                    return
            self._finished = True
        self.closed.emit()
        super().closeEvent(e)
