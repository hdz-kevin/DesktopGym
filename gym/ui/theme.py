"""Paleta y hoja de estilos de la aplicacion."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

BG = "#f4f5f7"
SURFACE = "#ffffff"
BORDER = "#e2e5ea"
TEXT = "#1c2430"
TEXT_MUTED = "#6b7684"
SIDEBAR_BG = "#151b26"
SIDEBAR_TEXT = "#9aa5b4"
SIDEBAR_ACTIVE = "#232c3d"

PRIMARY = "#2563eb"
PRIMARY_HOVER = "#1d4ed8"
SUCCESS = "#15803d"
SUCCESS_BG = "#dcfce7"
DANGER = "#b91c1c"
DANGER_BG = "#fee2e2"
WARNING = "#a16207"
WARNING_BG = "#fef3c7"
NEUTRAL_BG = "#eef1f5"

STYLESHEET = f"""
QWidget {{
    font-family: "Segoe UI", "SF Pro Text", "Inter", sans-serif;
    font-size: 14px;
    color: {TEXT};
}}
QMainWindow, #content {{ background: {BG}; }}

#sidebar {{ background: {SURFACE}; }}
#sidebarTitle {{ color: {TEXT}; font-size: 17px; font-weight: 700; }}
#sidebarSubtitle {{ color: {TEXT_MUTED}; font-size: 12px; }}
#sidebarSection {{
    color: #5c6879; font-size: 11px; font-weight: 700; padding: 8px 16px 4px 16px;
}}
QPushButton#navButton {{
    background: transparent; color: {SIDEBAR_TEXT}; border: none;
    text-align: left; padding: 10px 16px; border-radius: 8px; font-size: 14px;
}}
QPushButton#navButton:hover {{ background: {SIDEBAR_ACTIVE}; color: #ffffff; }}
QPushButton#navButton:checked {{
    background: {SIDEBAR_ACTIVE}; color: #ffffff; font-weight: 600;
}}
#navShortcut {{ color: #4a5568; font-size: 11px; }}

#pageTitle {{ font-size: 22px; font-weight: 700; }}
#pageSubtitle {{ color: {TEXT_MUTED}; font-size: 13px; }}

#card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px; }}
#statValue {{ font-size: 26px; font-weight: 700; }}
#statLabel {{ color: {TEXT_MUTED}; font-size: 12px; }}

QPushButton {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px;
    padding: 8px 14px; color: {TEXT};
}}
QPushButton:hover {{ background: {NEUTRAL_BG}; }}
QPushButton:disabled {{ color: #a5adb9; background: {NEUTRAL_BG}; }}
QPushButton#primary {{
    background: {PRIMARY}; color: #ffffff; border: 1px solid {PRIMARY}; font-weight: 600;
}}
QPushButton#primary:hover {{ background: {PRIMARY_HOVER}; }}
QPushButton#danger {{ background: {SURFACE}; color: {DANGER}; border: 1px solid #f5c2c2; }}
QPushButton#danger:hover {{ background: {DANGER_BG}; }}
QPushButton#ghost {{ background: transparent; border: none; color: {TEXT_MUTED}; }}
QPushButton#ghost:hover {{ color: {TEXT}; background: {NEUTRAL_BG}; }}

QPushButton#filterChip {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 16px; padding: 6px 14px;
    color: {TEXT_MUTED};
}}
QPushButton#filterChip:checked {{
    background: {PRIMARY}; color: #ffffff; border-color: {PRIMARY}; font-weight: 600;
}}

QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px;
    padding: 8px 10px; selection-background-color: {PRIMARY}; selection-color: #ffffff;
}}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QPlainTextEdit:focus {{ border: 1px solid {PRIMARY}; }}
QLineEdit[invalid="true"] {{ border: 1px solid {DANGER}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {SURFACE}; border: 1px solid {BORDER};
    selection-background-color: {PRIMARY}; selection-color: #ffffff; outline: none;
}}

QListWidget {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px;
    outline: none; padding: 4px;
}}
QListWidget::item {{ padding: 8px 10px; }}
QListWidget::item:selected {{
    background: #e5edff; color: {TEXT};
}}

QTableView {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px;
    gridline-color: transparent; selection-background-color: #e5edff;
    selection-color: {TEXT}; outline: none;
}}
QTableView::item {{ padding: 10px 8px; border-bottom: 1px solid #f0f2f5; }}
QHeaderView::section {{
    background: {SURFACE}; color: {TEXT_MUTED}; border: none;
    border-bottom: 1px solid {BORDER}; padding: 10px 8px; font-weight: 600; font-size: 12px;
}}
QTableView QTableCornerButton::section {{ background: {SURFACE}; border: none; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px; }}
QScrollBar::handle:vertical {{ background: #cbd2dc; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #aeb7c4; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 4px; }}
QScrollBar::handle:horizontal {{ background: #cbd2dc; border-radius: 5px; min-width: 30px; }}

#badgeSuccess {{
    background: {SUCCESS_BG}; color: {SUCCESS}; border-radius: 10px;
    padding: 3px 10px; font-size: 12px; font-weight: 600;
}}
#badgeDanger {{
    background: {DANGER_BG}; color: {DANGER}; border-radius: 10px;
    padding: 3px 10px; font-size: 12px; font-weight: 600;
}}
#badgeNeutral {{
    background: {NEUTRAL_BG}; color: {TEXT_MUTED}; border-radius: 10px;
    padding: 3px 10px; font-size: 12px; font-weight: 600;
}}
#badgeWarning {{
    background: {WARNING_BG}; color: {WARNING}; border-radius: 10px;
    padding: 3px 10px; font-size: 12px; font-weight: 600;
}}

#toastSuccess {{
    background: #16321f; color: #ffffff; border-radius: 10px; padding: 12px 16px; font-weight: 500;
}}
#toastError {{
    background: #3b1414; color: #ffffff; border-radius: 10px; padding: 12px 16px; font-weight: 500;
}}
#toastInfo {{
    background: {SIDEBAR_BG}; color: #ffffff; border-radius: 10px; padding: 12px 16px;
}}

#muted {{ color: {TEXT_MUTED}; }}
#errorText {{ color: {DANGER}; font-size: 12px; }}
#separator {{ background: {BORDER}; }}

QDialog {{ background: {BG}; }}
QLabel#formLabel {{ color: {TEXT_MUTED}; font-size: 12px; font-weight: 600; }}
QCheckBox {{ spacing: 8px; }}
"""


def apply_appearance(app: QApplication) -> None:
    """Fusion + tema claro. Sin esto, Qt hereda el modo oscuro del sistema."""
    app.setStyle("Fusion")
    app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    app.setStyleSheet(STYLESHEET)
