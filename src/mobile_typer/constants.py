from __future__ import annotations

import logging


LOGGER = logging.getLogger("mobile_typer")
ALLOWED_KEYS = tuple(chr(code) for code in range(ord("a"), ord("r") + 1))
COMBO_WINDOW_MS = 700
EMERGENCY_STOP_KEY = "p"
WINDOW_BG = "#edf2f7"
PANEL_BG = "#ffffff"
TEXT_COLOR = "#0f172a"
MUTED_TEXT = "#475569"
ACCENT = "#1d4ed8"
PORT_WARNING = "#92400e"
PORT_WARNING_BG = "#fef3c7"
PORT_IN_USE_ERRNOS = {48, 98, 10013, 10048}


__all__ = [
    "LOGGER",
    "ALLOWED_KEYS",
    "COMBO_WINDOW_MS",
    "EMERGENCY_STOP_KEY",
    "WINDOW_BG",
    "PANEL_BG",
    "TEXT_COLOR",
    "MUTED_TEXT",
    "ACCENT",
    "PORT_WARNING",
    "PORT_WARNING_BG",
    "PORT_IN_USE_ERRNOS",
]
