"""Темний стиль для всіх вікон програми (налаштування, діалоги, меню)."""

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPixmap

ACCENT = "#7b5cff"
BG = "#14162a"
CARD = "#1d2038"
TEXT = "#eceefa"
MUTED = "#9aa0bf"
LINE = "#2f3454"

APP_CSS = f"""
QWidget {{ color: {TEXT}; font-family: 'Segoe UI'; font-size: 10pt; }}
QDialog, QWidget#window {{ background: {BG}; }}
QLabel#title {{ font-size: 15pt; font-weight: 600; }}
QLabel#hint {{ color: {MUTED}; font-size: 9pt; }}
QFrame#card {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 12px; }}
QPushButton {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 8px; padding: 7px 14px; }}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:pressed {{ background: {LINE}; }}
QPushButton:disabled {{ color: {MUTED}; }}
QPushButton#primary {{ background: {ACCENT}; border-color: {ACCENT}; color: white; font-weight: 600; }}
QPushButton#primary:hover {{ background: #8d72ff; }}
QCheckBox {{ spacing: 9px; padding: 4px 0; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 1px solid {LINE}; background: {CARD}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QComboBox {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 8px; padding: 5px 10px; }}
QComboBox QAbstractItemView {{ background: {CARD}; border: 1px solid {LINE}; selection-background-color: {ACCENT}; }}
QMenu {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 10px; padding: 6px; }}
QMenu::item {{ padding: 7px 22px 7px 14px; border-radius: 6px; }}
QMenu::item:selected {{ background: {ACCENT}; color: white; }}
QMenu::separator {{ height: 1px; background: {LINE}; margin: 5px 8px; }}
QToolTip {{ background: {CARD}; color: {TEXT}; border: 1px solid {LINE}; border-radius: 6px; padding: 4px 8px; }}
QMessageBox {{ background: {BG}; }}
QLabel#section {{ font-weight: 600; color: {MUTED}; padding: 0 0 4px 2px; }}
QWidget#panel {{ background: transparent; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QToolButton {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 7px; padding: 5px 9px; }}
QToolButton:hover {{ border-color: {ACCENT}; }}
QToolButton:checked {{ background: {ACCENT}; border-color: {ACCENT}; color: white; }}
QToolButton::menu-indicator {{ image: none; width: 0; }}
QToolButton#group {{ background: transparent; border: none; font-weight: 600; font-size: 10.5pt;
                     padding: 8px 2px 4px 0; text-align: left; color: {TEXT}; }}
QToolButton#group:checked {{ background: transparent; color: {TEXT}; }}
QPushButton#swatch {{ text-align: left; padding: 5px 10px; font-family: Consolas, 'Segoe UI'; }}
QLineEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {{ background: {BG}; border: 1px solid {LINE};
                     border-radius: 7px; padding: 4px 8px; selection-background-color: {ACCENT}; }}
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {ACCENT}; }}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 16px; }}
QSlider::groove:horizontal {{ height: 4px; background: {LINE}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: white; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }}
QListWidget {{ background: {BG}; border: 1px solid {LINE}; border-radius: 8px; padding: 4px; outline: none; }}
QListWidget::item {{ padding: 6px 6px; border-radius: 6px; }}
QListWidget::item:selected {{ background: {ACCENT}; color: white; }}
QListWidget::item:hover:!selected {{ background: {LINE}; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {LINE}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {ACCENT}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QColorDialog, QFileDialog, QInputDialog {{ background: {BG}; }}
"""


def app_icon():
    pm = QPixmap(64, 64)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    g = QLinearGradient(QPointF(0, 0), QPointF(64, 64))
    g.setColorAt(0, QColor("#7b5cff"))
    g.setColorAt(1, QColor("#ff5ca8"))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(g)
    p.drawRoundedRect(4, 4, 26, 26, 8, 8)
    p.drawRoundedRect(34, 4, 26, 56, 8, 8)
    p.drawRoundedRect(4, 34, 26, 26, 8, 8)
    p.end()
    return QIcon(pm)
