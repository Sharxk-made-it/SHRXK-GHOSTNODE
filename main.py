"""GHOSTNODE - launcher.

Dev:        python main.py
Packaged:   GHOSTNODE.exe (built with build.bat / GhostNode.spec)
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True  # never litter the USB with __pycache__

import logging
import traceback


def _fatal(title: str, message: str) -> None:
    """Report a startup failure even in a windowed build (no console)."""
    try:
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)  # type: ignore[attr-defined]
            return
    except Exception:
        pass
    print("%s\n%s" % (title, message), file=sys.stderr)


def _install_excepthook(log: logging.Logger) -> None:
    def hook(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            return
        log.error("unhandled exception:\n%s",
                  "".join(traceback.format_exception(exc_type, exc, tb)))
    sys.excepthook = hook


def main() -> int:
    from core import logger, version
    from core.commands import CommandEngine, register_builtin
    from core.config import Config
    from core.context import AppContext
    from core.paths import resolve
    from core.registry import ModuleRegistry
    from modules.catalog import load_all

    paths = resolve()
    writable = paths.ensure()
    log = logger.setup(paths, writable)
    _install_excepthook(log)

    config = Config(paths.config_file if writable else None)
    config.load()

    registry = ModuleRegistry()
    load_all(registry)

    ctx = AppContext(paths=paths, config=config, registry=registry,
                     writable=writable, log=log)
    engine = CommandEngine(ctx)
    register_builtin(engine)
    for module in registry.all():
        module.register_commands(engine)
    ctx.engine = engine

    log.info("%s starting (packaged=%s, writable=%s)",
             version.APP_NAME, paths.frozen, writable)
    log.info("root: %s", paths.root)

    try:
        from PySide6.QtGui import QFont
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        log.error("PySide6 missing: %s", exc)
        _fatal(version.APP_NAME,
               "PySide6 is not installed.\n\nRun:  pip install -r requirements.txt")
        return 2

    from ui import theme
    from ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName(version.APP_EXE)
    app.setStyle("Fusion")  # consistent base for QSS on every Windows version

    families = theme.load_bundled_fonts(paths.assets / "fonts")
    family = theme.pick_font_family(families)
    base_font = QFont(family)
    base_font.setPointSizeF(10.0)
    app.setFont(base_font)
    app.setStyleSheet(theme.build_qss())
    log.info("font: %s", family)

    window = MainWindow(ctx, engine, family)
    # Original SHRXK boot animation (abstract glitch mark, not a copied logo).
    from ui.splash import BootSplash
    splash = BootSplash(family)
    def launch_main_window() -> None:
        splash.close()
        window.show()
    splash.finished.connect(launch_main_window)
    splash.show()
    code = app.exec()

    log.info("exit code %s", code)
    logging.shutdown()  # release the log file so the drive can be ejected
    return code


if __name__ == "__main__":
    sys.exit(main())
