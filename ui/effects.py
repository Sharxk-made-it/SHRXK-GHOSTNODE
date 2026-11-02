"""Visual effects: CRT scanline overlay and a glitching title."""
from __future__ import annotations

import random

from PySide6.QtCore import QRect, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetrics, QLinearGradient,
                           QPainter, QPixmap)
from PySide6.QtWidgets import QSizePolicy, QWidget

from ui import theme


class ScanlineOverlay(QWidget):
    """Transparent layer over the whole window: fine scanlines plus a slow
    brighter band sweeping downwards. Ignores the mouse, repaints only the
    strip the band moved through (cheap)."""

    BAND_H = 110
    STEP_PX = 3.0
    TICK_MS = 40

    def __init__(self, parent: QWidget, line_alpha: int = 34) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._tile = self._make_tile(line_alpha)
        self._y = float(-self.BAND_H)
        self._timer = QTimer(self)
        self._timer.setInterval(self.TICK_MS)
        self._timer.timeout.connect(self._advance)

    @staticmethod
    def _make_tile(alpha: int) -> QPixmap:
        tile = QPixmap(2, 3)
        tile.fill(QColor(0, 0, 0, 0))
        painter = QPainter(tile)
        painter.fillRect(0, 0, 2, 1, QColor(0, 0, 0, alpha))
        painter.end()
        return tile

    def set_enabled(self, enabled: bool) -> None:
        if enabled:
            self.show()
            self.raise_()
            self._timer.start()
        else:
            self._timer.stop()
            self.hide()

    def _advance(self) -> None:
        height = self.height()
        if height <= 0:
            return
        old = QRect(0, int(self._y), self.width(), self.BAND_H)
        self._y += self.STEP_PX
        if self._y > height:
            self._y = float(-self.BAND_H)
        new = QRect(0, int(self._y), self.width(), self.BAND_H)
        self.update(old.united(new))

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.drawTiledPixmap(self.rect(), self._tile)
        gradient = QLinearGradient(0.0, self._y, 0.0, self._y + self.BAND_H)
        gradient.setColorAt(0.0, QColor(252, 238, 10, 0))
        gradient.setColorAt(0.5, QColor(252, 238, 10, 16))
        gradient.setColorAt(1.0, QColor(252, 238, 10, 0))
        painter.fillRect(QRectF(0.0, self._y, float(self.width()), float(self.BAND_H)),
                         QBrush(gradient))


class GlitchLabel(QWidget):
    """Title text that occasionally glitches: red/amber ghost layers and a
    horizontally displaced slice, in short bursts every few seconds."""

    def __init__(self, text: str, point_size: float, family: str,
                 bg: str = theme.BG, parent: QWidget = None) -> None:
        super().__init__(parent)
        self._text = text
        self._bg = QColor(bg)
        self._font = QFont(family)
        self._font.setPointSizeF(point_size)
        self._font.setBold(True)
        self._font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3.0)

        self._enabled = True
        self._glitching = False
        self._ticks = 0
        self._red_dx = 0
        self._ghost_dx = 0
        self._slice = (0, 0, 0)  # y, height, dx

        self._idle = QTimer(self)
        self._idle.setSingleShot(True)
        self._idle.timeout.connect(self._begin_burst)
        self._burst = QTimer(self)
        self._burst.setInterval(45)
        self._burst.timeout.connect(self._burst_tick)

        hint = self.sizeHint()
        self.setFixedHeight(hint.height())
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self._schedule()

    def sizeHint(self) -> QSize:  # noqa: N802
        metrics = QFontMetrics(self._font)
        return QSize(metrics.horizontalAdvance(self._text) + 20, metrics.height() + 10)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return self.sizeHint()

    # ---- control --------------------------------------------------------
    def set_glitch_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        if enabled:
            if not self._idle.isActive() and not self._burst.isActive():
                self._schedule()
        else:
            self._idle.stop()
            self._burst.stop()
            self._glitching = False
            self.update()

    def _schedule(self) -> None:
        if self._enabled:
            self._idle.start(random.randint(2500, 7000))

    def _begin_burst(self) -> None:
        self._ticks = random.randint(3, 6)
        self._glitching = True
        self._burst.start()

    def _burst_tick(self) -> None:
        if self._ticks <= 0:
            self._burst.stop()
            self._glitching = False
            self.update()
            self._schedule()
            return
        self._ticks -= 1
        height = max(self.height(), 12)
        self._red_dx = random.randint(-6, -2)
        self._ghost_dx = random.randint(2, 6)
        slice_h = random.randint(4, max(5, height // 3))
        self._slice = (random.randint(0, max(0, height - slice_h)), slice_h,
                       random.randint(-12, 12))
        self.update()

    # ---- paint ----------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setFont(self._font)
        metrics = painter.fontMetrics()
        x = 8
        y = (self.height() + metrics.ascent() - metrics.descent()) // 2

        if self._glitching:
            painter.setPen(QColor(theme.RED))
            painter.drawText(x + self._red_dx, y, self._text)
            painter.setPen(QColor(theme.YELLOW_DIM))
            painter.drawText(x + self._ghost_dx, y, self._text)

        painter.setPen(QColor(theme.YELLOW))
        painter.drawText(x, y, self._text)

        if self._glitching and self._slice[1] > 0:
            slice_y, slice_h, slice_dx = self._slice
            painter.save()
            painter.setClipRect(0, slice_y, self.width(), slice_h)
            painter.fillRect(0, slice_y, self.width(), slice_h, self._bg)
            painter.setPen(QColor(theme.YELLOW))
            painter.drawText(x + slice_dx, y, self._text)
            painter.restore()
