"""Службові вікна: загальні налаштування і «Є оновлення»."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QPushButton,
                             QVBoxLayout)

from core import config, platform_win
from core.version import VERSION


class SettingsWindow(QDialog):
    """Загальні налаштування програми. Зміни діють одразу; «Скасувати» повертає, як було."""

    def __init__(self, app_ctl):
        super().__init__()
        self.ctl = app_ctl
        self.st = app_ctl.st
        self.snapshot = {k: self.st[k] for k in ("fps", "eco", "pause_fullscreen", "auto_update")}
        self.auto0 = platform_win.is_autostart()
        self.setWindowTitle("WidgetDesk — налаштування")
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(12)
        t = QLabel("Налаштування")
        t.setObjectName("title")
        lay.addWidget(t)

        card = QFrame()
        card.setObjectName("card")
        c = QVBoxLayout(card)
        c.setContentsMargins(16, 12, 16, 12)
        row = QHBoxLayout()
        row.addWidget(QLabel("Плавність анімацій"))
        self.fps = QComboBox()
        self.fps.addItem("60 кадрів за секунду (плавніше)", 60)
        self.fps.addItem("30 кадрів за секунду (менше навантаження)", 30)
        self.fps.setCurrentIndex(0 if self.st["fps"] == 60 else 1)
        self.fps.currentIndexChanged.connect(self.apply)
        row.addWidget(self.fps, 1)
        c.addLayout(row)
        self.eco = self._check(c, "Економний режим (менше анімацій)", self.st["eco"])
        self.pause = self._check(c, "Ставити анімації на паузу, коли гра на весь екран", self.st["pause_fullscreen"])
        lay.addWidget(card)

        card2 = QFrame()
        card2.setObjectName("card")
        c2 = QVBoxLayout(card2)
        c2.setContentsMargins(16, 12, 16, 12)
        self.autostart = self._check(c2, "Запускати разом із Windows", self.auto0)
        self.upd = self._check(c2, "Автоматично перевіряти оновлення", self.st["auto_update"])
        lay.addWidget(card2)

        h = QLabel(f"Версія {VERSION}.  Налаштування лежать тут: {config.APP_DIR}")
        h.setObjectName("hint")
        h.setWordWrap(True)
        lay.addWidget(h)

        btns = QHBoxLayout()
        b_dir = QPushButton("Відкрити папку")
        b_dir.clicked.connect(lambda: platform_win.open_folder(config.APP_DIR))
        b_no = QPushButton("Скасувати")
        b_no.clicked.connect(self.reject)
        b_ok = QPushButton("Зберегти")
        b_ok.setObjectName("primary")
        b_ok.clicked.connect(self.accept)
        btns.addWidget(b_dir)
        btns.addStretch()
        btns.addWidget(b_no)
        btns.addWidget(b_ok)
        lay.addLayout(btns)

    def _check(self, lay, text, on):
        cb = QCheckBox(text)
        cb.setChecked(bool(on))
        cb.toggled.connect(self.apply)
        lay.addWidget(cb)
        return cb

    def apply(self, *_):
        self.st["fps"] = self.fps.currentData()
        self.st["eco"] = self.eco.isChecked()
        self.st["pause_fullscreen"] = self.pause.isChecked()
        self.st["auto_update"] = self.upd.isChecked()
        self.ctl.apply_settings()

    def done(self, r):
        if r == QDialog.DialogCode.Accepted:
            if self.autostart.isChecked() != self.auto0:
                platform_win.set_autostart(self.autostart.isChecked())
            self.ctl.save()
        else:
            self.st.update(self.snapshot)
            self.ctl.apply_settings()
        super().done(r)


class UpdateDialog(QDialog):
    """«Є нова версія»: Оновити / Пізніше / Пропустити цю версію."""

    def __init__(self, version, notes, on_update, on_skip):
        super().__init__()
        self.setWindowTitle("WidgetDesk — оновлення")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        self.setMinimumWidth(420)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(10)
        t = QLabel(f"Доступна версія {version}")
        t.setObjectName("title")
        lay.addWidget(t)
        lay.addWidget(QLabel(f"Зараз у тебе {VERSION}."))
        if notes:
            n = QLabel(notes[:600])
            n.setWordWrap(True)
            n.setObjectName("hint")
            lay.addWidget(n)
        self.status = QLabel("")
        lay.addWidget(self.status)
        row = QHBoxLayout()
        self.b_skip = QPushButton("Пропустити цю версію")
        self.b_later = QPushButton("Пізніше")
        self.b_ok = QPushButton("Оновити")
        self.b_ok.setObjectName("primary")
        row.addWidget(self.b_skip)
        row.addStretch()
        row.addWidget(self.b_later)
        row.addWidget(self.b_ok)
        lay.addLayout(row)
        self.b_later.clicked.connect(self.close)
        self.b_skip.clicked.connect(lambda: (on_skip(), self.close()))
        self.b_ok.clicked.connect(on_update)

    def busy(self):
        for b in (self.b_skip, self.b_later, self.b_ok):
            b.setEnabled(False)
        self.status.setText("Завантаження…")

    def set_progress(self, pct):
        self.status.setText(f"Завантаження… {pct}%")

    def failed(self, err):
        self.status.setText("Не вдалося: " + err[:120])
        for b in (self.b_later, self.b_ok):
            b.setEnabled(True)
