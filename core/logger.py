"""Logging: small rotating file on the USB + an in-memory bus for the UI log panel."""
from __future__ import annotations

import collections
import logging
import sys
import time
from logging.handlers import RotatingFileHandler
from typing import Callable, Deque, List, Tuple

from core.paths import Paths

LogCallback = Callable[[str, str], None]


class LogBus(logging.Handler):
    """Keeps recent records and fans them out to subscribers (level, text)."""

    def __init__(self, capacity: int = 300) -> None:
        super().__init__(level=logging.INFO)
        self._listeners: List[LogCallback] = []
        self.history: Deque[Tuple[str, str]] = collections.deque(maxlen=capacity)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            stamp = time.strftime("%H:%M:%S", time.localtime(record.created))
            source = record.name.split(".")[-1]
            text = "%s %-9s %s" % (stamp, source, record.getMessage())
        except Exception:
            self.handleError(record)
            return
        entry = (record.levelname, text)
        self.history.append(entry)
        for callback in list(self._listeners):
            try:
                callback(*entry)
            except Exception:
                pass

    def subscribe(self, callback: LogCallback, replay: bool = True) -> None:
        if replay:
            for entry in list(self.history):
                callback(*entry)
        self._listeners.append(callback)

    def unsubscribe(self, callback: LogCallback) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)


bus = LogBus()


def setup(paths: Paths, writable: bool, debug: bool = False) -> logging.Logger:
    """Configure the 'ghostnode' logger. Idempotent."""
    logger = logging.getLogger("ghostnode")
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.propagate = False
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    if writable:
        try:
            # Small on purpose: USB drives are limited (256 KB x 3 files max).
            file_handler = RotatingFileHandler(
                paths.log_file, maxBytes=256 * 1024, backupCount=2,
                encoding="utf-8", delay=True,
            )
            file_handler.setFormatter(fmt)
            logger.addHandler(file_handler)
        except OSError:
            pass

    if sys.stderr is not None:  # windowed PyInstaller builds have no stderr
        stream = logging.StreamHandler(sys.stderr)
        stream.setFormatter(fmt)
        logger.addHandler(stream)

    logger.addHandler(bus)
    return logger
