"""Palette, font selection and the QSS stylesheet.

Identity: near-black / carbon backgrounds, neon yellow as the primary colour,
red as the accent. Font sizes are set in code (not QSS) so letter-spacing and
sizes stay under control of the widgets that need them.
"""
from __future__ import annotations

from pathlib import Path
from string import Template
from typing import List, Optional

from PySide6.QtGui import QFontDatabase

# ---- palette --------------------------------------------------------------
BG = "#07070A"
CARBON = "#0F0F12"
PANEL = "#121215"
PANEL_HI = "#1C1C21"
LINE = "#2B2B31"
YELLOW = "#FCEE0A"
YELLOW_DIM = "#8F8707"
RED = "#FF003C"
ORANGE = "#FF9F1C"
TEXT = "#DAD7C3"
TEXT_DIM = "#7C7A6C"
WHITE = "#F4F2E4"

LEVEL_COLORS = {
    "plain": TEXT,
    "info": TEXT,
    "ok": YELLOW,
    "warn": ORANGE,
    "err": RED,
    "dim": TEXT_DIM,
    "accent": RED,
    "cmd": WHITE,
}

LOG_COLORS = {
    "DEBUG": TEXT_DIM,
    "INFO": TEXT,
    "WARNING": ORANGE,
    "ERROR": RED,
    "CRITICAL": RED,
}

# First installed match wins. Drop a .ttf/.otf into assets/fonts/ to override.
FONT_PREFERENCE = (
    "Share Tech Mono", "JetBrains Mono", "Cascadia Mono",
    "Consolas", "Lucida Console", "Courier New",
)


def load_bundled_fonts(fonts_dir: Path) -> List[str]:
    """Register fonts shipped in assets/fonts/ (process-local, nothing is installed)."""
    families: List[str] = []
    if not fonts_dir.is_dir():
        return families
    for path in sorted(fonts_dir.iterdir()):
        if path.suffix.lower() in (".ttf", ".otf"):
            font_id = QFontDatabase.addApplicationFont(str(path))
            if font_id != -1:
                families.extend(QFontDatabase.applicationFontFamilies(font_id))
    return families


def pick_font_family(loaded: Optional[List[str]] = None) -> str:
    if loaded:
        return loaded[0]
    available = set(QFontDatabase.families())
    for name in FONT_PREFERENCE:
        if name in available:
            return name
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()


_QSS = Template("""
QMainWindow { background-color: $BG; }
QLabel { background: transparent; color: $TEXT; }

QFrame#Header { background-color: $BG; border: none; border-bottom: 1px solid $LINE; }
QFrame#Footer { background-color: $BG; border: none; border-top: 1px solid $LINE; }

QLabel#Subtitle { color: $TEXT_DIM; }
QLabel#Clock { color: $YELLOW; }
QLabel#Date { color: $TEXT_DIM; }
QLabel#StatusBlink { color: $YELLOW; }
QLabel#StatusBlink[blink="off"] { color: $RED; }
QLabel#Credit { color: $YELLOW_DIM; }
QLabel#FooterInfo { color: $TEXT_DIM; }
QLabel#Hint { color: $TEXT_DIM; }
QLabel#KeyLabel { color: $TEXT_DIM; }
QLabel#ValLabel { color: $YELLOW; }
QLabel#ValLabel[level="warn"] { color: $ORANGE; }
QLabel#ValLabel[level="err"] { color: $RED; }
QLabel#ValLabel[level="dim"] { color: $TEXT_DIM; }
QLabel#Prompt { color: $YELLOW; }

QPlainTextEdit {
    background-color: $BG;
    color: $TEXT;
    border: 1px solid $LINE;
    padding: 6px;
    selection-background-color: $YELLOW;
    selection-color: #000000;
}

QLineEdit#CmdLine {
    background-color: $BG;
    color: $WHITE;
    border: none;
    border-bottom: 1px solid $YELLOW_DIM;
    padding: 6px 4px;
    selection-background-color: $YELLOW;
    selection-color: #000000;
}
QLineEdit#CmdLine:focus { border-bottom: 1px solid $YELLOW; }
QLineEdit#CmdLine:disabled { color: $TEXT_DIM; border-bottom: 1px solid $LINE; }

QListWidget#ModuleList {
    background: transparent;
    border: none;
    outline: 0;
    color: $TEXT;
}
QListWidget#ModuleList::item {
    padding: 8px 8px;
    margin: 2px 0;
    border-left: 3px solid $LINE;
}
QListWidget#ModuleList::item:hover { background-color: $PANEL_HI; border-left: 3px solid $YELLOW_DIM; }
QListWidget#ModuleList::item:selected {
    background-color: $YELLOW;
    color: #000000;
    border-left: 3px solid $RED;
}

QSplitter::handle { background: transparent; }
QSplitter::handle:vertical { height: 10px; }

QScrollBar:vertical { background: $BG; width: 8px; margin: 0; }
QScrollBar::handle:vertical { background: $YELLOW_DIM; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: $YELLOW; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QScrollBar:horizontal { background: $BG; height: 8px; margin: 0; }
QScrollBar::handle:horizontal { background: $YELLOW_DIM; min-width: 24px; }
QScrollBar::handle:horizontal:hover { background: $YELLOW; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }

QToolTip { background-color: $BG; color: $YELLOW; border: 1px solid $YELLOW; padding: 4px; }

QMessageBox { background-color: $CARBON; }
QPushButton {
    background: transparent; color: $YELLOW; border: 1px solid $YELLOW;
    padding: 6px 18px; min-width: 70px;
}
QPushButton:hover { background-color: $YELLOW; color: #000000; }
""")


def build_qss() -> str:
    return _QSS.substitute(
        BG=BG, CARBON=CARBON, PANEL_HI=PANEL_HI, LINE=LINE, YELLOW=YELLOW,
        YELLOW_DIM=YELLOW_DIM, RED=RED, ORANGE=ORANGE, TEXT=TEXT,
        TEXT_DIM=TEXT_DIM, WHITE=WHITE,
    )
