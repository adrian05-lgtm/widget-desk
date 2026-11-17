"""Поля редактора. Кожне поле будується автоматично з опису властивості (Prop).

Уроки з панелі:
- сигнал changed має тип object — щоб будь-яке значення (число, текст, так/ні) проходило без помилки;
- set_value() змінює поле БЕЗ сигналу — щоб оновлення значень ззовні не запускало зайвих змін;
- колесо мишки не міняє значення, поки на полі немає фокусу — інакше, гортаючи список, випадково
  міняєш розміри й кольори."""

import os

from PyQt6.QtCore import QEvent, QObject, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QFileDialog, QFontComboBox,
                             QHBoxLayout, QLineEdit, QMenu, QPlainTextEdit, QPushButton, QSlider, QSpinBox,
                             QToolButton, QVBoxLayout, QWidget)

from model.element import TOKENS


class _NoWheel(QObject):
    """Колесо мишки на полі без фокусу передається далі — гортати список, а не міняти значення."""

    def eventFilter(self, obj, e):
        if e.type() == QEvent.Type.Wheel and not obj.hasFocus():
            e.ignore()
            return True
        return False


_NOWHEEL = _NoWheel()


def _guard(w):
    w.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    w.installEventFilter(_NOWHEEL)
    if isinstance(w, QComboBox):                     # довгі назви не розпирають панель убік
        w.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        w.setMinimumContentsLength(8)
    return w


def swatch(color, w=22, h=16):
    """Квадратик кольору з «шаховою дошкою» під ним — щоб було видно прозорість."""
    pm = QPixmap(w, h)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    r = QRectF(0.5, 0.5, w - 1, h - 1)
    p.setClipRect(r)
    for i in range(0, w, 5):
        for j in range(0, h, 5):
            p.fillRect(i, j, 5, 5, QColor(200, 200, 200) if (i + j) // 5 % 2 else QColor(255, 255, 255))
    p.fillRect(r, QColor(color))
    p.setClipping(False)
    p.setPen(QColor(255, 255, 255, 90))
    p.drawRoundedRect(r, 3, 3)
    p.end()
    return pm


def hexa(c):
    return QColor(c).name(QColor.NameFormat.HexArgb)


class Control(QWidget):
    changed = pyqtSignal(object)

    def __init__(self, prop):
        super().__init__()
        self.prop = prop

    def set_value(self, v):
        pass


class NumberControl(Control):
    """Повзунок + поле числа (для великих діапазонів — тільки поле)."""

    def __init__(self, prop):
        super().__init__(prop)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lo = prop.lo if prop.lo is not None else -99999
        hi = prop.hi if prop.hi is not None else 99999
        if prop.kind == "float":
            self.spin = QDoubleSpinBox()
            self.spin.setDecimals(2)
            self.spin.setSingleStep(prop.step or 0.1)
        else:
            self.spin = QSpinBox()
            self.spin.setSingleStep(int(prop.step or 1))
        self.spin.setRange(lo, hi)
        self.spin.setMinimumWidth(78)
        _guard(self.spin)
        self.slider = None
        if prop.kind == "int" and prop.lo is not None and hi - lo <= 1000:
            self.slider = _guard(QSlider(Qt.Orientation.Horizontal))
            self.slider.setRange(lo, hi)
            self.slider.valueChanged.connect(self._from_slider)
            lay.addWidget(self.slider, 1)
        else:
            lay.addStretch(1)
        self.spin.valueChanged.connect(self._from_spin)
        lay.addWidget(self.spin)

    def _from_slider(self, v):
        self.spin.blockSignals(True)
        self.spin.setValue(v)
        self.spin.blockSignals(False)
        self.changed.emit(v)

    def _from_spin(self, v):
        if self.slider is not None:
            self.slider.blockSignals(True)
            self.slider.setValue(int(v))
            self.slider.blockSignals(False)
        self.changed.emit(v)

    def set_value(self, v):
        for w in (self.spin, self.slider):
            if w is not None:
                w.blockSignals(True)
                w.setValue(v if w is self.spin else int(v))
                w.blockSignals(False)


class BoolControl(Control):
    def __init__(self, prop):
        super().__init__(prop)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.box = QCheckBox()
        self.box.toggled.connect(lambda v: self.changed.emit(bool(v)))
        lay.addWidget(self.box)
        lay.addStretch(1)

    def set_value(self, v):
        self.box.blockSignals(True)
        self.box.setChecked(bool(v))
        self.box.blockSignals(False)


class ChoiceControl(Control):
    def __init__(self, prop):
        super().__init__(prop)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.combo = _guard(QComboBox())
        for val, title in prop.choices:
            self.combo.addItem(title, val)
        self.combo.currentIndexChanged.connect(lambda i: self.changed.emit(self.combo.itemData(i)))
        lay.addWidget(self.combo, 1)

    def set_value(self, v):
        i = self.combo.findData(v)
        self.combo.blockSignals(True)
        self.combo.setCurrentIndex(max(0, i))
        self.combo.blockSignals(False)


class ColorControl(Control):
    """Кнопка-кольорок: меню з недавніми кольорами або повний вибір (з прозорістю і піпеткою)."""

    def __init__(self, prop, ctx):
        super().__init__(prop)
        self.ctx = ctx
        self.value = prop.default
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.btn = QPushButton()
        self.btn.setObjectName("swatch")
        self.btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn.clicked.connect(self._menu)
        lay.addWidget(self.btn, 1)

    def set_value(self, v):
        self.value = v
        c = QColor(v)
        self.btn.setIcon(QIcon(swatch(v, 34, 18)))
        self.btn.setIconSize(swatch(v, 34, 18).size())
        alpha = round(c.alpha() / 255 * 100)
        self.btn.setText(f"  {c.name().upper()}" + ("" if alpha == 100 else f"   {alpha}%"))

    def _menu(self):
        m = QMenu(self)
        recent = [c for c in self.ctx.recent_colors() if QColor(c).isValid()]
        if recent:
            t = m.addAction("Недавні кольори")
            t.setEnabled(False)
            for c in recent[:12]:
                a = m.addAction(QIcon(swatch(c)), "  " + QColor(c).name().upper()
                                + ("" if QColor(c).alpha() == 255 else f"  ({round(QColor(c).alpha() / 2.55)}%)"))
                a.triggered.connect(lambda _=False, c=c: self._pick(c))
            m.addSeparator()
        m.addAction("Вибрати колір…  (є прозорість і піпетка)").triggered.connect(self._dialog)
        m.addAction(QIcon(swatch("#00000000")), "  Повністю прозорий").triggered.connect(
            lambda: self._pick("#00000000"))
        m.exec(self.btn.mapToGlobal(self.btn.rect().bottomLeft()))

    def _pick(self, c):
        self.set_value(hexa(c))
        self.changed.emit(self.value)
        self.ctx.remember_color(self.value)

    def _dialog(self):
        old = self.value
        d = QColorDialog(QColor(old), self)
        d.setWindowTitle("Колір: " + self.prop.label)
        d.setOptions(QColorDialog.ColorDialogOption.ShowAlphaChannel
                     | QColorDialog.ColorDialogOption.DontUseNativeDialog)
        d.currentColorChanged.connect(lambda c: (self.set_value(hexa(c)), self.changed.emit(self.value)))
        if d.exec():
            self._pick(d.currentColor())
        else:                                               # «Скасувати» в діалозі — повернути, як було
            self.set_value(old)
            self.changed.emit(old)


class FontControl(Control):
    """Список шрифтів (лише масштабовані). Перемикач «Кир» — показувати тільки шрифти з українськими літерами."""

    def __init__(self, prop):
        super().__init__(prop)
        self.family = prop.default
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.combo = _guard(QFontComboBox())
        self.combo.setFontFilters(QFontComboBox.FontFilter.ScalableFonts)
        self.combo.setWritingSystem(QFontDatabase.WritingSystem.Cyrillic)
        self.combo.setMaxVisibleItems(16)
        self.combo.currentFontChanged.connect(self._changed)
        self.cyr = QToolButton()
        self.cyr.setText("Кир")
        self.cyr.setCheckable(True)
        self.cyr.setChecked(True)
        self.cyr.setToolTip("Показувати лише шрифти з українськими літерами.\n"
                            "Вимкни, щоб побачити всі (для англійського тексту).")
        self.cyr.toggled.connect(self._filter)
        lay.addWidget(self.combo, 1)
        lay.addWidget(self.cyr)

    def _changed(self, f):
        self.family = f.family()
        self.changed.emit(self.family)

    def _filter(self, on):
        self.combo.blockSignals(True)
        self.combo.setWritingSystem(QFontDatabase.WritingSystem.Cyrillic if on else QFontDatabase.WritingSystem.Any)
        self.combo.setCurrentFont(QFont(self.family))
        self.combo.blockSignals(False)

    def set_value(self, v):
        self.family = v
        self.combo.blockSignals(True)
        self.combo.setCurrentFont(QFont(v))
        self.combo.blockSignals(False)


class TextControl(Control):
    """Поле тексту на кілька рядків; «＋» вставляє живі значення ({time}, {date}…)."""

    def __init__(self, prop, tokens=True):
        super().__init__(prop)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.edit = QPlainTextEdit()
        self.edit.setFixedHeight(54)
        self.edit.textChanged.connect(lambda: self.changed.emit(self.edit.toPlainText()))
        lay.addWidget(self.edit, 1)
        if tokens:
            b = QToolButton()
            b.setText("＋")
            b.setToolTip("Вставити живе значення: час, дату, день тижня…")
            b.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            m = QMenu(b)
            for key, title in TOKENS:
                m.addAction(title).triggered.connect(lambda _=False, k=key: self.edit.insertPlainText("{" + k + "}"))
            b.setMenu(m)
            col = QVBoxLayout()
            col.addWidget(b)
            col.addStretch(1)
            lay.addLayout(col)

    def set_value(self, v):
        if self.edit.toPlainText() == v:
            return                                  # не скидати курсор, якщо текст той самий
        self.edit.blockSignals(True)
        self.edit.setPlainText(v)
        self.edit.blockSignals(False)


class LineControl(Control):
    """Один рядок (наприклад, що відкрити кнопкою) + «Огляд…» для вибору файла."""

    def __init__(self, prop, browse=False):
        super().__init__(prop)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit()
        self.edit.textChanged.connect(lambda t: self.changed.emit(t))
        lay.addWidget(self.edit, 1)
        if browse:
            b = QPushButton("Огляд…")
            b.clicked.connect(self._browse)
            lay.addWidget(b)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, self.prop.label, os.path.expanduser("~"))
        if path:
            self.edit.setText(os.path.normpath(path))

    def set_value(self, v):
        if self.edit.text() == v:
            return
        self.edit.blockSignals(True)
        self.edit.setText(v)
        self.edit.blockSignals(False)


class ImageControl(Control):
    def __init__(self, prop):
        super().__init__(prop)
        self.path = ""
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.name = QLineEdit()
        self.name.setReadOnly(True)
        self.name.setPlaceholderText("не вибрано")
        b = QPushButton("Вибрати…")
        b.clicked.connect(self._browse)
        x = QToolButton()
        x.setText("✕")
        x.setToolTip("Прибрати картинку")
        x.clicked.connect(lambda: (self.set_value(""), self.changed.emit("")))
        lay.addWidget(self.name, 1)
        lay.addWidget(b)
        lay.addWidget(x)

    def _browse(self):
        start = os.path.dirname(self.path) if self.path else os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(self, "Вибери картинку", start,
                                              "Картинки (*.png *.jpg *.jpeg *.bmp *.gif *.webp)")
        if path:
            self.set_value(os.path.normpath(path))
            self.changed.emit(self.path)

    def set_value(self, v):
        self.path = v
        self.name.setText(os.path.basename(v) if v else "")
        self.name.setToolTip(v)


def make_control(prop, ctx):
    """ctx — об'єкт із методами recent_colors() і remember_color(c)."""
    k = prop.kind
    if k in ("int", "float"):
        return NumberControl(prop)
    if k == "bool":
        return BoolControl(prop)
    if k == "choice":
        return ChoiceControl(prop)
    if k == "color":
        return ColorControl(prop, ctx)
    if k == "font":
        return FontControl(prop)
    if k == "image":
        return ImageControl(prop)
    if k == "text":
        if prop.key == "target":
            return LineControl(prop, browse=True)
        return TextControl(prop, tokens=(prop.key == "text" and prop.group == "Текст"))
    return Control(prop)
