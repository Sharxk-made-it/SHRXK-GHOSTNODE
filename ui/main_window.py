"""Main window: header, module sidebar, terminal + event log, system-state panel."""
from __future__ import annotations

import logging
import time
from typing import Dict, Optional

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QIcon, QKeySequence, QShortcut, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QMainWindow, QPlainTextEdit, QSplitter, QStackedWidget,
                               QVBoxLayout, QWidget)

from core import diagnostics, logger, version
from core.commands import CommandEngine
from core.context import AppContext
from ui import theme
from ui.effects import GlitchLabel, ScanlineOverlay
from ui.terminal import TerminalWidget
from ui.widgets import KVList, Panel, style_font
from ui.winutil import apply_dark_titlebar

log = logging.getLogger("ghostnode.ui")


class LogBridge(QObject):
    """Thread-safe hop from the logging bus to the GUI thread."""
    message = Signal(str, str)


class MainWindow(QMainWindow):
    def __init__(self, ctx: AppContext, engine: CommandEngine, family: str) -> None:
        super().__init__()
        self.ctx = ctx
        self.engine = engine
        self.family = family
        self._pages: Dict[str, QWidget] = {}
        self._active_id = "terminal"
        self._tick_count = 0
        self._booted = False
        self._styled_titlebar = False

        self.setWindowTitle(version.APP_NAME)
        icon_path = ctx.paths.assets / "icons" / "ghostnode.ico"
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))
        self._apply_size()

        self.root = QWidget()
        self.root.setObjectName("Root")
        self.setCentralWidget(self.root)
        outer = QVBoxLayout(self.root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_header())
        outer.addWidget(self._build_body(), 1)
        outer.addWidget(self._build_footer())

        self.overlay = ScanlineOverlay(self.root)
        self.root.installEventFilter(self)

        self._bridge = LogBridge()
        self._bridge.message.connect(self._on_log)
        self._log_callback = lambda level, text: self._bridge.message.emit(level, text)
        logger.bus.subscribe(self._log_callback)

        self.terminal.action.connect(self._on_action)
        QShortcut(QKeySequence("Ctrl+L"), self).activated.connect(self.terminal.clear)

        self._clock = QTimer(self)
        self._clock.setInterval(1000)
        self._clock.timeout.connect(self._tick)
        self._clock.start()

        self.apply_effects()
        self.refresh_status()
        self._select_module("terminal")

    # ---- construction ---------------------------------------------------
    def _apply_size(self) -> None:
        cfg = self.ctx.config
        screen = QGuiApplication.primaryScreen()
        avail = screen.availableGeometry()
        width = int(cfg.get("ui.window.width", 1280))
        height = int(cfg.get("ui.window.height", 780))
        width = max(980, min(width, avail.width() - 40))
        height = max(600, min(height, avail.height() - 40))
        self.setMinimumSize(980, 600)
        self.resize(width, height)
        # Always centre on the primary screen: the same USB visits many PCs.
        self.move(avail.x() + (avail.width() - width) // 2,
                  avail.y() + (avail.height() - height) // 2)

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("Header")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(18, 12, 18, 10)

        left = QVBoxLayout()
        left.setSpacing(0)
        self.title = GlitchLabel(version.APP_NAME, 24, self.family)
        subtitle = QLabel(version.SUBTITLE.upper())
        subtitle.setObjectName("Subtitle")
        style_font(subtitle, 9, spacing=4.0)
        subtitle.setContentsMargins(8, 0, 0, 0)
        left.addWidget(self.title)
        left.addWidget(subtitle)

        right = QVBoxLayout()
        right.setSpacing(2)
        self.clock = QLabel("--:--:--")
        self.clock.setObjectName("Clock")
        style_font(self.clock, 18, bold=True, spacing=2.0)
        self.clock.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.date = QLabel("")
        self.date.setObjectName("Date")
        style_font(self.date, 9, spacing=2.0)
        self.date.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.blink = QLabel("SYS.READY")
        self.blink.setObjectName("StatusBlink")
        style_font(self.blink, 9, bold=True, spacing=3.0)
        self.blink.setAlignment(Qt.AlignmentFlag.AlignRight)
        right.addWidget(self.clock)
        right.addWidget(self.date)
        right.addWidget(self.blink)

        layout.addLayout(left)
        layout.addStretch(1)
        layout.addLayout(right)
        return header

    def _build_body(self) -> QWidget:
        body = QWidget()
        layout = QHBoxLayout(body)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        layout.addWidget(self._build_sidebar())
        layout.addWidget(self._build_center(), 1)
        layout.addWidget(self._build_status_panel())
        return body

    def _build_sidebar(self) -> QWidget:
        panel = Panel("Modules")
        panel.setFixedWidth(236)

        self.module_list = QListWidget()
        self.module_list.setObjectName("ModuleList")
        self.module_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        style_font(self.module_list, 10)
        for module in self.ctx.registry.all():
            tag = "READY" if module.is_ready() else "PLANNED"
            item = QListWidgetItem("%02d  %s\n      [%s]" % (module.order, module.name.upper(), tag))
            item.setData(Qt.ItemDataRole.UserRole, module.id)
            item.setToolTip(module.summary)
            self.module_list.addItem(item)
        self.module_list.itemClicked.connect(self._on_module_clicked)
        panel.body.addWidget(self.module_list, 1)

        hint = QLabel("click a module or type\nopen <id> in the terminal")
        hint.setObjectName("Hint")
        style_font(hint, 8)
        panel.body.addWidget(hint)
        return panel

    def _build_center(self) -> QWidget:
        self.terminal = TerminalWidget(self.engine, self.family)
        term_panel = Panel("Terminal // Ghostnode")
        term_panel.body.addWidget(self.terminal)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setUndoRedoEnabled(False)
        self.log_view.setMaximumBlockCount(500)
        log_font = QFont(self.family)
        log_font.setPointSizeF(9.0)
        self.log_view.setFont(log_font)
        log_panel = Panel("Event log", accent=theme.RED)
        log_panel.body.addWidget(self.log_view)
        log_panel.setMinimumHeight(110)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(term_panel)
        splitter.addWidget(log_panel)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([560, 150])

        self.stack = QStackedWidget()
        self.stack.addWidget(splitter)  # index 0 = home (terminal + log)
        self._home = splitter
        return self.stack

    def _build_status_panel(self) -> QWidget:
        panel = Panel("System state")
        panel.setFixedWidth(260)
        self._status_keys = ["mode", "host", "drive", "space", "storage",
                             "privileges", "modules", "effects", "uptime"]
        self.status = KVList(self._status_keys)
        panel.body.addWidget(self.status, 1)
        return panel

    def _build_footer(self) -> QWidget:
        footer = QFrame()
        footer.setObjectName("Footer")
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(18, 6, 18, 6)
        credit = QLabel(version.CREDIT)
        credit.setObjectName("Credit")
        style_font(credit, 8, bold=True, spacing=4.0)
        info = QLabel("PORTABLE  //  WIN64")
        info.setObjectName("FooterInfo")
        style_font(info, 8, spacing=2.0)
        layout.addWidget(credit)
        layout.addStretch(1)
        layout.addWidget(info)
        return footer

    # ---- events ---------------------------------------------------------
    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if obj is self.root and event.type() == QEvent.Type.Resize:
            self.overlay.setGeometry(self.root.rect())
            self.overlay.raise_()
        return super().eventFilter(obj, event)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.overlay.setGeometry(self.root.rect())
        self.overlay.raise_()
        if not self._styled_titlebar:
            self._styled_titlebar = True
            apply_dark_titlebar(self)
        if not self._booted:
            self._booted = True
            QTimer.singleShot(200, self._start_boot)

    def closeEvent(self, event) -> None:  # noqa: N802
        cfg = self.ctx.config
        if not self.isMaximized() and not self.isFullScreen():
            cfg.set("ui.window.width", self.width(), save=False)
            cfg.set("ui.window.height", self.height(), save=False)
        cfg.save()
        log.info("shutdown - safe to eject the drive")
        self._clock.stop()
        self.overlay.set_enabled(False)
        logger.bus.unsubscribe(self._log_callback)
        event.accept()

    # ---- behaviour ------------------------------------------------------
    def _start_boot(self) -> None:
        log.info("%s ready", version.APP_NAME)
        self.terminal.play_boot(diagnostics.boot_report(self.ctx))

    def apply_effects(self) -> None:
        cfg = self.ctx.config
        self.overlay.set_enabled(bool(cfg.get("ui.scanlines", True)))
        self.title.set_glitch_enabled(bool(cfg.get("ui.glitch", True)))
        self.refresh_status()

    def refresh_status(self) -> None:
        ctx = self.ctx
        host = diagnostics.host_summary()
        st = self.status
        st.set_value("mode", "PACKAGED" if ctx.paths.frozen else "DEVELOPMENT",
                     "ok" if ctx.paths.frozen else "warn")
        st.set_value("host", "%s %s" % (host["os"], host["arch"]))

        kind = diagnostics.drive_kind(ctx.paths.root)
        st.set_value("drive", kind.upper(), "ok" if kind == "removable" else "dim")
        usage = diagnostics.disk_usage(ctx.paths.root)
        if usage:
            st.set_value("space", "%s free / %s" % (
                diagnostics.human_bytes(usage[2]), diagnostics.human_bytes(usage[0])),
                "err" if usage[2] < 10 * 1024 * 1024 else "ok")
        else:
            st.set_value("space", "UNKNOWN", "warn")

        st.set_value("storage", "READ/WRITE" if ctx.writable else "READ-ONLY",
                     "ok" if ctx.writable else "err")
        admin = diagnostics.is_admin()
        st.set_value("privileges", "ADMIN" if admin else "STANDARD USER",
                     "warn" if admin else "ok")
        reg = ctx.registry
        st.set_value("modules", "%d / %d READY" % (reg.ready_count(), len(reg)))
        scan = "ON" if ctx.config.get("ui.scanlines", True) else "OFF"
        glitch = "ON" if ctx.config.get("ui.glitch", True) else "OFF"
        st.set_value("effects", "SCAN %s | GLITCH %s" % (scan, glitch))
        st.set_value("uptime", diagnostics.fmt_duration(ctx.uptime()))

    def _tick(self) -> None:
        self._tick_count += 1
        self.clock.setText(time.strftime("%H:%M:%S"))
        self.date.setText(time.strftime("%Y-%m-%d"))
        self.status.set_value("uptime", diagnostics.fmt_duration(self.ctx.uptime()))
        self.blink.setProperty("blink", "on" if self._tick_count % 2 else "off")
        self.blink.style().unpolish(self.blink)
        self.blink.style().polish(self.blink)
        if self._tick_count % 30 == 0:
            self.refresh_status()

    def _on_log(self, level: str, text: str) -> None:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(theme.LOG_COLORS.get(level, theme.TEXT)))
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text + "\n", fmt)
        bar = self.log_view.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _on_module_clicked(self, item: QListWidgetItem) -> None:
        module_id = item.data(Qt.ItemDataRole.UserRole)
        self.terminal.run_command("open %s" % module_id)
        self._select_module(self._active_id)  # selection follows the active module

    def _select_module(self, module_id: str) -> None:
        self.module_list.blockSignals(True)
        for row in range(self.module_list.count()):
            item = self.module_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == module_id:
                self.module_list.setCurrentRow(row)
                break
        self.module_list.blockSignals(False)

    def _on_action(self, action: str, arg: str) -> None:
        if action == "exit":
            self.close()
        elif action == "open":
            self._activate_module(arg)
        elif action == "fx":
            self.apply_effects()

    def _activate_module(self, module_id: str) -> None:
        module = self.ctx.registry.get(module_id)
        if module is None:
            return
        if module_id == "terminal":
            self.stack.setCurrentWidget(self._home)
            self.terminal.focus_input()
        else:
            page = self._pages.get(module_id)
            if page is None:
                widget = module.create_widget(self.ctx)
                if widget is None:
                    self.terminal.print_line(
                        "[%s] has no interface yet." % module_id, "warn")
                    return
                page = Panel(module.name)
                page.body.addWidget(widget)
                self.stack.addWidget(page)
                self._pages[module_id] = page
            self.stack.setCurrentWidget(page)
        self._active_id = module_id
        self._select_module(module_id)
        log.info("module active: %s", module_id)
