"""Integrated terminal: output view + command line wired to the CommandEngine."""
from __future__ import annotations

from collections import deque
from typing import Deque, List

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QKeyEvent, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QVBoxLayout, QWidget

from core.commands import CommandEngine
from core.result import Line
from ui import theme
from ui.widgets import style_font

PROMPT = "ghostnode >"
HISTORY_LIMIT = 200  # in memory only: typed commands are never written to the USB


class CommandLine(QLineEdit):
    """QLineEdit with history (up/down), Escape to clear and a Tab signal."""

    tab_pressed = Signal()

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setObjectName("CmdLine")
        self._history: Deque[str] = deque(maxlen=HISTORY_LIMIT)
        self._index = 0
        self._draft = ""

    def remember(self, text: str) -> None:
        text = text.strip()
        if text and (not self._history or self._history[-1] != text):
            self._history.append(text)
        self._index = len(self._history)
        self._draft = ""

    def _step(self, delta: int) -> None:
        if not self._history:
            return
        if self._index == len(self._history):
            self._draft = self.text()
        self._index = max(0, min(len(self._history), self._index + delta))
        self.setText(self._history[self._index] if self._index < len(self._history)
                     else self._draft)

    def event(self, event: QEvent) -> bool:  # noqa: N802
        # Tab is swallowed by focus navigation unless intercepted here.
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Tab:
            self.tab_pressed.emit()
            return True
        return super().event(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        key = event.key()
        if key == Qt.Key.Key_Up:
            self._step(-1)
        elif key == Qt.Key.Key_Down:
            self._step(1)
        elif key == Qt.Key.Key_Escape:
            self.clear()
        else:
            super().keyPressEvent(event)


class TerminalWidget(QWidget):
    """Emits action(name, arg) for UI-level commands (exit, open, fx)."""

    action = Signal(str, str)

    def __init__(self, engine: CommandEngine, family: str, parent: QWidget = None) -> None:
        super().__init__(parent)
        self._engine = engine
        self._boot_queue: Deque[Line] = deque()
        self._boot_timer = QTimer(self)
        self._boot_timer.setInterval(45)
        self._boot_timer.timeout.connect(self._boot_step)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setUndoRedoEnabled(False)
        self.output.setMaximumBlockCount(1500)
        self.output.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        out_font = QFont(family)
        out_font.setPointSizeF(11.0)
        self.output.setFont(out_font)
        layout.addWidget(self.output, 1)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.prompt = QLabel(PROMPT)
        self.prompt.setObjectName("Prompt")
        style_font(self.prompt, 11, bold=True)
        self.input = CommandLine()
        in_font = QFont(family)
        in_font.setPointSizeF(11.0)
        self.input.setFont(in_font)
        self.input.setPlaceholderText("type a command - 'help' lists them")
        row.addWidget(self.prompt)
        row.addWidget(self.input, 1)
        layout.addLayout(row)

        self.input.returnPressed.connect(self._submit)
        self.input.tab_pressed.connect(self._complete)

    # ---- output ---------------------------------------------------------
    def print_line(self, text: str, level: str = "plain") -> None:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(theme.LEVEL_COLORS.get(level, theme.TEXT)))
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text + "\n", fmt)
        bar = self.output.verticalScrollBar()
        bar.setValue(bar.maximum())

    def print_lines(self, lines: List[Line]) -> None:
        for line in lines:
            self.print_line(line.text, line.level)

    def clear(self) -> None:
        self.output.clear()

    def focus_input(self) -> None:
        self.input.setFocus()

    # ---- commands -------------------------------------------------------
    def run_command(self, text: str, echo: bool = True) -> None:
        if echo:
            self.print_line("%s %s" % (PROMPT, text), "cmd")
        result = self._engine.execute(text)
        self.print_lines(result.lines)
        if result.action == "clear":
            self.clear()
        elif result.action:
            self.action.emit(result.action, result.arg)

    def _submit(self) -> None:
        text = self.input.text()
        self.input.remember(text)
        self.input.clear()
        if text.strip():
            self.run_command(text)

    def _complete(self) -> None:
        new_text, candidates = self._engine.complete(self.input.text())
        self.input.setText(new_text)
        if candidates:
            self.print_line("  " + "   ".join(candidates), "dim")

    # ---- boot sequence --------------------------------------------------
    def play_boot(self, lines: List[Line]) -> None:
        """Print lines one by one (input locked meanwhile)."""
        self._boot_queue = deque(lines)
        self.input.setEnabled(False)
        self._boot_timer.start()

    def _boot_step(self) -> None:
        if not self._boot_queue:
            self._boot_timer.stop()
            self.input.setEnabled(True)
            self.input.setFocus()
            return
        line = self._boot_queue.popleft()
        self.print_line(line.text, line.level)
