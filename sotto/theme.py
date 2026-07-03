"""Sotto visual identity: near-black, soft off-white, one muted-violet accent."""

BG = "#101014"          # window background
SURFACE = "#17171D"     # cards, inputs
SURFACE_2 = "#1E1E26"   # hover
BORDER = "#26262E"
TEXT = "#EAEAF0"
MUTED = "#8A8A96"
ACCENT = "#9D8CFF"
ACCENT_DIM = "#6E62B8"
ERROR = "#E5645E"
OK = "#7BC98A"

RADIUS = 14

QSS = f"""
* {{ font-family: 'Segoe UI Variable Text', 'Segoe UI', sans-serif; font-size: 13px; }}
QWidget {{ background: {BG}; color: {TEXT}; }}
QLabel {{ background: transparent; }}
QLabel[muted="true"] {{ color: {MUTED}; }}
QLabel[h1="true"] {{ font-size: 17px; font-weight: 600; }}
QLineEdit, QComboBox, QSpinBox, QListWidget, QPlainTextEdit {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px;
    padding: 6px 10px; selection-background-color: {ACCENT_DIM};
}}
QLineEdit:focus, QComboBox:focus {{ border-color: {ACCENT_DIM}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{ image: none; border-left: 4px solid transparent;
    border-right: 4px solid transparent; border-top: 5px solid {MUTED}; }}
QComboBox QAbstractItemView {{ background: {SURFACE}; border: 1px solid {BORDER};
    selection-background-color: {SURFACE_2}; outline: none; }}
QPushButton {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px;
    padding: 7px 14px;
}}
QPushButton:hover {{ background: {SURFACE_2}; }}
QPushButton:pressed {{ background: {BORDER}; }}
QPushButton[accent="true"] {{ background: {ACCENT_DIM}; border-color: {ACCENT_DIM};
    color: white; font-weight: 600; }}
QPushButton[accent="true"]:hover {{ background: {ACCENT}; }}
QCheckBox {{ background: transparent; spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 5px;
    border: 1px solid {BORDER}; background: {SURFACE}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QListWidget::item {{ padding: 8px; border-radius: 6px; }}
QListWidget::item:selected {{ background: {SURFACE_2}; color: {TEXT}; }}
QScrollBar:vertical {{ background: transparent; width: 8px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QProgressBar {{ background: {SURFACE}; border: none; border-radius: 4px; height: 8px;
    text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: {ACCENT_DIM}; border-radius: 4px; }}
QToolTip {{ background: {SURFACE_2}; color: {TEXT}; border: 1px solid {BORDER}; }}
"""
