"""Reusable cyberdeck widgets: chamfered Panel, key/value list, font helper."""
from __future__ import annotations

from typing import Dict, Iterable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

from ui import theme


def style_font(widget: QWidget, size: float, bold: bool = False, spacing: float = 0.0) -> None:
    font = QFont(widget.font())
    font.setPointSizeF(size)
    font.setBold(bold)
    if spacing:
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    widget.setFont(font)


class Panel(QFrame):
    """Technical panel: chamfered corners, a filled title tab, corner ticks.
    Put content into `panel.body` (a QVBoxLayout)."""

    CUT = 12
    TAB_H = 20

    def __init__(self, title: str, accent: str = theme.YELLOW, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setObjectName("Panel")
        self._title = title.upper()
        self._accent = QColor(accent)
        self._accent_dim = QColor(accent)
        self._accent_dim.setAlpha(110)
        self._title_font = QFont(self.font())
        self._title_font.setPointSizeF(8.0)
        self._title_font.setBold(True)
        self._title_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.0)

        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(12, self.TAB_H + 12, 12, 12)
        self.body.setSpacing(8)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        w, h, c = self.width() - 1, self.height() - 1, self.CUT

        outline = QPainterPath()
        outline.moveTo(0, 0)
        outline.lineTo(w - c, 0)
        outline.lineTo(w, c)
        outline.lineTo(w, h)
        outline.lineTo(c, h)
        outline.lineTo(0, h - c)
        outline.closeSubpath()

        painter.fillPath(outline, QColor(theme.PANEL))
        painter.setPen(QPen(QColor(theme.LINE), 1))
        painter.drawPath(outline)

        painter.setFont(self._title_font)
        metrics = painter.fontMetrics()
        tab_w = metrics.horizontalAdvance(self._title) + 22
        painter.fillRect(0, 0, tab_w, self.TAB_H, self._accent)
        painter.setPen(QColor("#000000"))
        painter.drawText(11, (self.TAB_H + metrics.ascent() - metrics.descent()) // 2,
                         self._title)

        painter.setPen(QPen(self._accent_dim, 1))
        painter.drawLine(tab_w, 0, w - c, 0)
        painter.setPen(QPen(self._accent, 2))
        painter.drawLine(w - 16, h, w, h)
        painter.drawLine(w, h - 16, w, h)


class KVList(QWidget):
    """Two-column key/value readout used by the system-state panel."""

    def __init__(self, keys: Iterable[str], parent: QWidget = None) -> None:
        super().__init__(parent)
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(7)
        self._values: Dict[str, QLabel] = {}
        count = 0
        for row, key in enumerate(keys):
            key_label = QLabel(key.upper())
            key_label.setObjectName("KeyLabel")
            style_font(key_label, 9, spacing=1.0)
            value_label = QLabel("-")
            value_label.setObjectName("ValLabel")
            value_label.setWordWrap(True)
            style_font(value_label, 9, bold=True)
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(key_label, row, 0, Qt.AlignmentFlag.AlignTop)
            grid.addWidget(value_label, row, 1)
            self._values[key] = value_label
            count += 1
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(count, 1)

    def set_value(self, key: str, text: str, level: str = "ok") -> None:
        label = self._values[key]
        label.setText(text)
        label.setProperty("level", level)
        label.style().unpolish(label)
        label.style().polish(label)
