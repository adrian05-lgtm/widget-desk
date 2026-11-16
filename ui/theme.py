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
