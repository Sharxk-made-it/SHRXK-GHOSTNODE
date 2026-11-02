"""Windows-only cosmetics. Every call is wrapped: failure just means a normal title bar.

Uses the DWM API on this one window only - no registry, no system settings.
"""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QWidget

# COLORREF is 0x00BBGGRR
_CAPTION_BG = 0x000A0707      # #07070A
_YELLOW = 0x000AEEFC          # #FCEE0A


def apply_dark_titlebar(window: QWidget) -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        hwnd = ctypes.c_void_p(int(window.winId()))
        dwm = ctypes.windll.dwmapi  # type: ignore[attr-defined]

        def set_attr(attribute: int, value: int) -> None:
            data = ctypes.c_int(value)
            dwm.DwmSetWindowAttribute(hwnd, ctypes.c_uint(attribute),
                                      ctypes.byref(data), ctypes.sizeof(data))

        set_attr(20, 1)            # DWMWA_USE_IMMERSIVE_DARK_MODE (Win10 20H1+/11)
        set_attr(19, 1)            # same flag on older Win10 builds
        set_attr(35, _CAPTION_BG)  # DWMWA_CAPTION_COLOR   (Win11)
        set_attr(34, _YELLOW)      # DWMWA_BORDER_COLOR    (Win11)
        set_attr(36, _YELLOW)      # DWMWA_TEXT_COLOR      (Win11)
    except Exception:
        pass
