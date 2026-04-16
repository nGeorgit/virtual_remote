from __future__ import annotations

import ctypes
import html
import logging
import platform
import subprocess
import sys
from collections import deque
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from .constants import (
    ACCENT,
    COMBO_WINDOW_MS,
    EMERGENCY_STOP_KEY,
    MUTED_TEXT,
    PANEL_BG,
    PORT_WARNING,
    PORT_WARNING_BG,
    TEXT_COLOR,
    WINDOW_BG,
)
from .key_sender import UnsupportedPlatformError

if TYPE_CHECKING:
    from .server import MobileTyperHTTPServer


DESKTOP_APP_TITLE = "Mobile Remote"


class GuiLogHandler(logging.Handler):
    def __init__(self, *, max_records: int = 250) -> None:
        super().__init__(level=logging.INFO)
        self._records: deque[str] = deque(maxlen=max_records)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
        except Exception:
            self.handleError(record)
            return

        self.acquire()
        try:
            self._records.append(message)
        finally:
            self.release()

    def snapshot(self) -> Tuple[str, ...]:
        self.acquire()
        try:
            return tuple(self._records)
        finally:
            self.release()

    def clear(self) -> None:
        self.acquire()
        try:
            self._records.clear()
        finally:
            self.release()


def render_terminal_qr(data: str) -> Optional[str]:
    matrix = build_qr_matrix(data)
    if matrix is None:
        return None

    black = "\x1b[40m  \x1b[0m"
    white = "\x1b[47m  \x1b[0m"
    return "\n".join(
        "".join(black if cell else white for cell in row)
        for row in matrix
    )


def build_qr_matrix(data: str) -> Optional[List[List[bool]]]:
    try:
        import qrcode
    except ImportError:
        return None

    qr = qrcode.QRCode(border=4)
    qr.add_data(data)
    qr.make(fit=True)
    return qr.get_matrix()


def is_stdout_console_available() -> bool:
    return bool(getattr(sys.stdout, "isatty", lambda: False)())


def show_error_dialog(message: str, *, title: str = DESKTOP_APP_TITLE) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(title, message, parent=root)
        root.destroy()
        return
    except Exception:
        pass

    if platform.system() == "Windows":
        try:
            ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
            return
        except Exception:
            pass

    print(message, file=sys.stderr)


def get_windows_autostart_command() -> Optional[str]:
    if platform.system() != "Windows":
        return None

    if getattr(sys, "frozen", False):
        return subprocess.list2cmdline([sys.executable])

    argv0 = Path(sys.argv[0]).resolve()
    if argv0.suffix.lower() == ".py":
        return subprocess.list2cmdline([sys.executable, str(argv0)])

    return None


def supports_windows_autostart() -> bool:
    return get_windows_autostart_command() is not None


def is_windows_autostart_enabled() -> bool:
    command = get_windows_autostart_command()
    if command is None:
        return False

    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_READ,
        ) as key:
            value, _ = winreg.QueryValueEx(key, "MobileTyper")
    except FileNotFoundError:
        return False
    except OSError:
        return False

    return value == command


def set_windows_autostart(enabled: bool) -> None:
    command = get_windows_autostart_command()
    if command is None:
        raise UnsupportedPlatformError(
            "Windows auto-start is only available for this app on Windows."
        )

    import winreg

    with winreg.CreateKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
    ) as key:
        if enabled:
            winreg.SetValueEx(key, "MobileTyper", 0, winreg.REG_SZ, command)
            return

        try:
            winreg.DeleteValue(key, "MobileTyper")
        except FileNotFoundError:
            return


_REMOTE_CONTROL_SPECS: Tuple[Dict[str, object], ...] = (
    {"key": "a", "column": 1, "row": 1, "accent": "scarlet", "top_icon": "target", "bottom_icon": "swirl", "top_asset_height": "2.05rem", "down_asset_height": "1.55rem"},
    {"key": "b", "column": 2, "row": 1, "accent": "crimson", "top_icon": "ladder", "bottom_icon": "bolt", "top_asset_width": "100%", "top_asset_height": "2.6rem", "top_asset_justify": "flex-start", "down_asset_height": "1.65rem"},
    {"key": "c", "column": 3, "row": 1, "accent": "magenta", "top_icon": "steps", "bottom_icon": "bolt", "top_asset_width": "100%", "top_asset_height": "2.6rem", "top_asset_justify": "flex-end", "down_asset_height": "1.65rem"},
    {"key": "d", "column": 4, "row": 1, "accent": "violet", "top_icon": "wave", "bottom_icon": "screen", "top_asset_height": "1.9rem", "down_asset_height": "1.45rem"},
    {"key": "e", "column": 5, "row": 1, "accent": "silver", "top_text": "2nd", "top_asset_height": "2.6rem", "top_asset_scale": "1.42"},
    {"key": "f", "column": 2, "row": 2, "accent": "cobalt", "top_icon": "ladder", "bottom_icon": "card", "top_asset_height": "2.2rem", "down_asset_height": "1.55rem"},
    {"key": "g", "column": 4, "row": 2, "accent": "cobalt", "top_icon": "screen", "bottom_icon": "card", "top_asset_height": "2.2rem", "down_asset_height": "1.55rem"},
    {"key": "h", "column": 1, "row": 3, "accent": "lime", "top_icon": "truck", "bottom_icon": "screen", "top_asset_height": "2.25rem", "down_asset_height": "1.45rem"},
    {"key": "i", "column": 3, "row": 3, "accent": "amber", "top_icon": "car", "bottom_icon": "screen", "top_asset_height": "2.25rem", "down_asset_height": "1.45rem"},
    {"key": "j", "column": 5, "row": 3, "accent": "amber", "top_text": "(P)", "top_asset_height": "2.15rem", "down_asset_height": "1.45rem", "bottom_icon": "screen"},
    {"key": "k", "column": 1, "row": 4, "accent": "scarlet", "top_icon": "bottle", "bottom_icon": "screen", "top_asset_height": "1.95rem", "down_asset_height": "1.45rem"},
    {"key": "l", "column": 2, "row": 4, "accent": "burgundy", "top_text": "1000", "top_asset_height": "2.4rem", "top_asset_scale": "1.4"},
    {"key": "m", "column": 3, "row": 4, "accent": "burgundy", "top_text": "100", "top_asset_height": "2.4rem", "top_asset_scale": "1.38"},
    {"key": "n", "column": 4, "row": 4, "accent": "berry", "top_text": "10", "top_asset_height": "2.4rem", "top_asset_scale": "1.36"},
    {"key": "o", "column": 5, "row": 4, "accent": "berry", "top_text": "1", "top_asset_height": "2.4rem", "top_asset_scale": "1.36"},
    {"key": "p", "column": 1, "row": 5, "row_span": 2, "accent": "scarlet", "top_text": "STOP", "top_asset_height": "2.75rem", "top_asset_scale": "1.38"},
    {"key": "q", "column": 3, "row": 5, "row_span": 2, "accent": "emerald", "top_text": "CLR", "bottom_text": "CA", "top_asset_height": "2.7rem", "top_asset_scale": "1.36", "down_asset_height": "2.1rem", "down_asset_scale": "1.28"},
    {"key": "r", "column": 5, "row": 5, "row_span": 2, "accent": "emerald", "top_text": "JI", "top_asset_height": "2.45rem"},
)


def _build_remote_control_specs(allowed_keys: Tuple[str, ...]) -> List[Dict[str, object]]:
    known_specs = {str(spec["key"]): spec for spec in _REMOTE_CONTROL_SPECS}
    controls: List[Dict[str, object]] = []

    for key in allowed_keys:
        spec = known_specs.get(key)
        if spec is None:
            continue
        button_spec = dict(spec)
        button_spec["label"] = key.upper()
        controls.append(button_spec)

    return controls


def _render_remote_icon(kind: Optional[str]) -> str:
    if not kind:
        return ""

    icons = {
        "target": (
            '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="7"></circle>'
            '<circle cx="12" cy="12" r="2.2"></circle>'
            '<path d="M12 3.5v2.2M12 18.3v2.2M3.5 12h2.2M18.3 12h2.2"></path></svg>'
        ),
        "ladder": (
            '<svg viewBox="0 0 24 24"><path d="M8 4.5v15M16 4.5v15M8 7.5h8M8 11.5h8M8 15.5h8"></path></svg>'
        ),
        "steps": (
            '<svg viewBox="0 0 24 24"><path d="M5 17.5h4v-4h4v-4h6"></path>'
            '<path d="M7 6.5h12"></path></svg>'
        ),
        "wave": (
            '<svg viewBox="0 0 24 24"><path d="M3.5 13c2.2 0 2.2-3 4.5-3s2.2 3 4.5 3 2.2-3 4.5-3 2.2 3 3.5 3"></path></svg>'
        ),
        "bolt": (
            '<svg viewBox="0 0 24 24"><path d="M13.5 3.5 7.5 12h4l-1 8.5 6-9h-4l1-8Z"></path></svg>'
        ),
        "screen": (
            '<svg viewBox="0 0 24 24"><rect x="4.5" y="5.5" width="15" height="10" rx="1.8"></rect>'
            '<path d="M9 19.5h6M12 15.5v4"></path></svg>'
        ),
        "card": (
            '<svg viewBox="0 0 24 24"><rect x="5" y="5" width="11" height="14" rx="1.6"></rect>'
            '<path d="M9.5 8.5h3M8 12.5h5"></path><path d="M11 7l6 2.5v9"></path></svg>'
        ),
        "truck": (
            '<svg viewBox="0 0 24 24"><path d="M4.5 8.5h9v6h-9zM13.5 10h3l2 2.4v2.1h-5"></path>'
            '<circle cx="8" cy="16.5" r="1.6"></circle><circle cx="16.5" cy="16.5" r="1.6"></circle></svg>'
        ),
        "car": (
            '<svg viewBox="0 0 24 24"><path d="M6 14.5h12l-1.4-4.2H7.4L6 14.5Z"></path>'
            '<circle cx="8.2" cy="16.5" r="1.5"></circle><circle cx="15.8" cy="16.5" r="1.5"></circle></svg>'
        ),
        "bottle": (
            '<svg viewBox="0 0 24 24"><path d="M10 4.5h4M10.8 4.5v3l-2.3 3v8h7v-8l-2.3-3v-3"></path></svg>'
        ),
        "swirl": (
            '<svg viewBox="0 0 24 24"><path d="M8 8.5a4.2 4.2 0 1 1 0 7.2"></path>'
            '<path d="M8.2 6 5 8.5l3.2 2.5"></path><path d="M16 15.5a4.2 4.2 0 1 1 0-7.2"></path>'
            '<path d="m15.8 18 3.2-2.5-3.2-2.5"></path></svg>'
        ),
    }
    svg = icons.get(kind)
    if svg is None:
        return ""
    return f'<span class="button-icon" aria-hidden="true">{svg}</span>'


def _iter_icon_dirs() -> List[Path]:
    candidates: List[Path] = []

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "icons")

    candidates.append(Path(__file__).resolve().parents[2] / "icons")
    candidates.append(Path(sys.executable).resolve().parent / "icons")
    return candidates


@lru_cache(maxsize=None)
def _load_remote_svg_asset(asset_name: str) -> str:
    for icon_dir in _iter_icon_dirs():
        asset_path = icon_dir / asset_name
        if not asset_path.is_file():
            continue
        try:
            return asset_path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
    return ""


def _render_remote_svg_asset(key: str, position: str) -> str:
    svg = _load_remote_svg_asset(f"{key.upper()}_{position}")
    if not svg:
        return ""
    return (
        f'<span class="button-asset button-asset--{html.escape(position)}" '
        f'aria-hidden="true">{svg}</span>'
    )


def _spec_has_secondary_action(spec: Dict[str, object]) -> bool:
    key = str(spec["key"]).lower()
    if key == "e":
        return False
    if _load_remote_svg_asset(f"{key.upper()}_down"):
        return True
    if str(spec.get("bottom_text", "")).strip():
        return True
    return bool(str(spec.get("bottom_icon", "")).strip())


def _get_remote_control_spec(key: str) -> Optional[Dict[str, object]]:
    normalized = key.lower()
    for spec in _REMOTE_CONTROL_SPECS:
        if str(spec["key"]).lower() == normalized:
            button_spec = dict(spec)
            button_spec["label"] = normalized.upper()
            return button_spec
    return None


def _render_remote_button(
    spec: Dict[str, object],
    *,
    interactive: bool = True,
    extra_classes: Tuple[str, ...] = (),
    style_override: Optional[str] = None,
) -> str:
    key = html.escape(str(spec["key"]))
    label = html.escape(str(spec["label"]))
    accent = html.escape(str(spec["accent"]))
    is_secondary_modifier = key.lower() == "e"
    has_secondary = _spec_has_secondary_action(spec)
    column = int(spec["column"])
    row = int(spec["row"])
    row_span = int(spec.get("row_span", 1))
    top_text = str(spec.get("top_text", "")).strip()
    bottom_text = str(spec.get("bottom_text", "")).strip()
    top_icon = _render_remote_icon(str(spec.get("top_icon", "")) or None)
    bottom_icon = _render_remote_icon(str(spec.get("bottom_icon", "")) or None)
    top_asset = _render_remote_svg_asset(str(spec["key"]), "top")
    bottom_asset = _render_remote_svg_asset(str(spec["key"]), "down")

    if top_asset:
        top_markup = top_asset
    elif top_text:
        top_markup = (
            f'<span class="button-caption button-caption-top">{html.escape(top_text)}</span>'
        )
    else:
        top_markup = top_icon
    if not top_markup:
        top_markup = '<span class="button-spacer" aria-hidden="true"></span>'

    footer_parts = []
    if not is_secondary_modifier:
        if bottom_asset:
            footer_parts.append(bottom_asset)
        else:
            if bottom_text:
                footer_parts.append(
                    f'<span class="button-caption button-caption-bottom">{html.escape(bottom_text)}</span>'
                )
            if bottom_icon:
                footer_parts.append(bottom_icon)
        footer_parts.append('<span class="button-port" aria-hidden="true"></span>')
    bottom_markup = "".join(footer_parts)

    classes = ["remote-button", f"accent-{accent}"]
    if has_secondary:
        classes.append("remote-button--has-secondary")
    if is_secondary_modifier:
        classes.append("remote-button--modifier")
    classes.extend(extra_classes)
    css_vars = []
    for spec_key, css_var in (
        ("top_asset_width", "--top-asset-width"),
        ("top_asset_height", "--top-asset-height"),
        ("top_asset_justify", "--top-asset-justify"),
        ("top_asset_scale", "--top-asset-scale"),
        ("top_asset_shift_x", "--top-asset-shift-x"),
        ("down_asset_width", "--down-asset-width"),
        ("down_asset_height", "--down-asset-height"),
        ("down_asset_justify", "--down-asset-justify"),
        ("down_asset_scale", "--down-asset-scale"),
        ("down_asset_shift_x", "--down-asset-shift-x"),
    ):
        value = spec.get(spec_key)
        if value:
            css_vars.append(f"{css_var}: {value};")
    style_parts: List[str] = []
    if style_override is not None:
        if style_override:
            style_parts.append(style_override)
    elif interactive:
        style_parts.append(f"grid-column: {column}; grid-row: {row};")
    if row_span > 1:
        classes.append("remote-button--tall")
        if style_override is None and interactive:
            style_parts = [f"grid-column: {column}; grid-row: {row} / span {row_span};"]
    style_parts.extend(css_vars)
    style_attr = f' style="{" ".join(style_parts)}"' if style_parts else ""

    band_markup = (
        '<span class="button-band button-band--switch" aria-hidden="true">'
        '<span class="button-switch-track">'
        '<span class="button-switch-state button-switch-state--off">Off</span>'
        '<span class="button-switch-state button-switch-state--on">On</span>'
        f'<span class="button-switch-thumb"><span class="button-switch-thumb-face">{label}</span></span>'
        "</span>"
        "</span>"
        if is_secondary_modifier
        else f'<span class="button-band"><span class="button-letter">{label}</span></span>'
    )
    aria_label = (
        "Toggle the 2nd switch for the next key press"
        if is_secondary_modifier
        else f"Send {label}"
    )
    if interactive:
        switch_attrs = ' role="switch" aria-checked="false"' if is_secondary_modifier else ""
        return (
            f'<button type="button" class="{" ".join(classes)}"{style_attr} '
            f'data-key="{key}" data-label="{label}" '
            f'data-has-secondary="{"true" if has_secondary else "false"}" '
            f'data-is-secondary-modifier="{"true" if is_secondary_modifier else "false"}" '
            f'aria-label="{aria_label}"{switch_attrs}>'
            '<span class="button-inner">'
            f'<span class="button-top">{top_markup}</span>'
            f"{band_markup}"
            f'<span class="button-bottom">{bottom_markup}</span>'
            "</span>"
            "</button>"
        )

    return (
        f'<span class="{" ".join(classes)}"{style_attr} aria-hidden="true">'
        '<span class="button-inner">'
        f'<span class="button-top">{top_markup}</span>'
        f"{band_markup}"
        f'<span class="button-bottom">{bottom_markup}</span>'
        "</span>"
        "</span>"
    )


def _render_guide_button_ref(
    key: str,
    *,
    secondary_armed: bool = False,
    secondary_target: bool = False,
) -> str:
    spec = _get_remote_control_spec(key)
    if spec is None:
        return ""
    row_span = int(spec.get("row_span", 1))
    is_secondary_modifier = key.lower() == "e"
    wrapper_class = "guide-button-ref-wrap"
    if row_span > 1:
        wrapper_class += " guide-button-ref-wrap--tall"
    if is_secondary_modifier:
        wrapper_class += " guide-button-ref-wrap--modifier-equal"
        control_html = _render_guide_modifier_button_ref(secondary_armed=secondary_armed)
        return f'<span class="{wrapper_class}" aria-hidden="true">{control_html}</span>'

    guide_spec = dict(spec)
    extra_classes = ["guide-button-ref__control"]
    if secondary_armed:
        extra_classes.append("is-armed")
    if secondary_target:
        extra_classes.append("guide-button-ref__control--secondary-target")
    control_html = _render_remote_button(
        guide_spec,
        interactive=False,
        extra_classes=tuple(extra_classes),
        style_override="",
    )
    return f'<span class="{wrapper_class}" aria-hidden="true">{control_html}</span>'


def _render_guide_modifier_button_ref(*, secondary_armed: bool) -> str:
    classes = [
        "remote-button",
        "accent-silver",
        "guide-button-ref__control",
        "guide-button-ref__control--guide-modifier-card",
    ]
    if secondary_armed:
        classes.append("is-armed")

    state_label = "ON" if secondary_armed else "OFF"
    state_class = (
        "guide-modifier-card__state guide-modifier-card__state--on"
        if secondary_armed
        else "guide-modifier-card__state guide-modifier-card__state--off"
    )

    return (
        f'<span class="{" ".join(classes)}" aria-hidden="true">'
        '<span class="button-inner">'
        '<span class="button-top">'
        '<span class="button-caption button-caption-top guide-modifier-card__caption">2nd</span>'
        "</span>"
        '<span class="button-band"><span class="button-letter">E</span></span>'
        '<span class="button-bottom guide-modifier-card__bottom">'
        f'<span class="{state_class}">{state_label}</span>'
        "</span>"
        "</span>"
        "</span>"
    )


def _render_guide_button_cluster(*keys: str, separator: Optional[str] = None) -> str:
    cluster_parts: List[str] = []
    separator_text = separator
    if separator_text is None and len(keys) > 1:
        separator_text = "+"
    is_secondary_sequence = len(keys) > 1 and keys[0].lower() == "e"
    cluster_classes = ["guide-button-cluster"]
    if any(key.lower() == "e" for key in keys):
        cluster_classes.append("guide-button-cluster--with-modifier")

    for index, key in enumerate(keys):
        if index and separator_text:
            separator_class = "guide-button-separator"
            if separator_text != "+":
                separator_class += " guide-button-separator--step"
            cluster_parts.append(
                f'<span class="{separator_class}" aria-hidden="true">'
                f"{html.escape(separator_text)}</span>"
            )
        cluster_parts.append(
            _render_guide_button_ref(
                key,
                secondary_armed=is_secondary_sequence and index == 0,
                secondary_target=is_secondary_sequence and index == 1,
            )
        )

    buttons_html = "".join(cluster_parts)
    return (
        f'<div class="{" ".join(cluster_classes)}" aria-hidden="true">'
        f"{buttons_html}"
        "</div>"
    )


def _render_guide_command_entry(
    title: str,
    keys: Tuple[str, ...],
    *,
    detail: str = "",
    note: str = "",
    separator: Optional[str] = None,
) -> str:
    cluster_html = _render_guide_button_cluster(*keys, separator=separator)
    detail_html = (
        f'<p class="guide-command-detail">{html.escape(detail)}</p>' if detail else ""
    )
    note_html = (
        f'<p class="guide-command-note">{html.escape(note)}</p>' if note else ""
    )
    return (
        '<article class="guide-command">'
        f"{cluster_html}"
        '<div class="guide-command-copy">'
        f'<h4 class="guide-command-title">{html.escape(title)}</h4>'
        f"{detail_html}"
        f"{note_html}"
        "</div>"
        "</article>"
    )


def _render_guide_manual_section(
    title: str,
    meta: str,
    entries: Tuple[Dict[str, object], ...],
    *,
    intro: str = "",
    notes: Tuple[str, ...] = (),
) -> str:
    intro_html = (
        f'<p class="guide-section-intro">{html.escape(intro)}</p>' if intro else ""
    )
    entries_html = "".join(
        _render_guide_command_entry(
            str(entry["title"]),
            tuple(str(key) for key in entry["keys"]),
            detail=str(entry.get("detail", "")),
            note=str(entry.get("note", "")),
            separator=(
                None
                if entry.get("separator") is None
                else str(entry.get("separator"))
            ),
        )
        for entry in entries
    )
    notes_html = "".join(
        f'<p class="guide-section-note">{html.escape(note)}</p>' for note in notes
    )
    return (
        '<details class="guide-section">'
        '<summary class="guide-summary">'
        f'<span class="guide-summary-title">{html.escape(title)}</span>'
        f'<span class="guide-summary-meta">{html.escape(meta)}</span>'
        "</summary>"
        '<div class="guide-section-body">'
        f"{intro_html}"
        f'<div class="guide-command-list">{entries_html}</div>'
        f"{notes_html}"
        "</div>"
        "</details>"
    )


def _render_manual_command_sections() -> str:
    testing_programs = (
        {
            "title": "Individual wheel-testing, left",
            "keys": ("b",),
            "note": "MB 6000 and MS 6200 only.",
        },
        {
            "title": "Individual wheel-testing, right",
            "keys": ("c",),
            "note": "MB 6000 and MS 6200 only.",
        },
        {
            "title": "Regular mode",
            "keys": ("b", "c"),
            "detail": "Press both buttons in any order.",
            "note": "MB 6000 and MS 6200 only.",
        },
        {
            "title": "Automatic mode on",
            "keys": ("a",),
            "note": "MB 6000 and MS 6200 only.",
        },
        {
            "title": '"SUPERAUTOMATIC" on',
            "keys": ("e", "a"),
        },
        {
            "title": "All-wheel-drive test, left-hand side",
            "keys": ("e", "b"),
            "note": "MB 6000 only.",
        },
        {
            "title": "All-wheel-drive test, right-hand side",
            "keys": ("e", "c"),
            "note": "MB 6000 only.",
        },
        {
            "title": "Imbalance measurement",
            "keys": ("d",),
            "note": "MB 6000 only.",
        },
        {
            "title": "Interrupt measurement",
            "keys": ("p",),
        },
        {
            "title": 'Automatic mode off / "SUPERAUTOMATIC" off',
            "keys": ("p",),
        },
    )
    gross_weight = (
        {
            "title": "Enter gross weight",
            "keys": ("k", "l", "m", "n", "r"),
            "detail": (
                "The manual shows this as the weight-entry workflow. The value opens in "
                "an auxiliary window, and the current value is shown if one is already "
                "entered or a weigher is fitted."
            ),
            "note": "MB 6000 only.",
            "separator": "->",
        },
    )
    store_functions = (
        {
            "title": "Front axle",
            "keys": ("h",),
            "note": "MB 6000, MS 6200, MSS 6300 only.",
        },
        {
            "title": "Rear axle",
            "keys": ("i",),
            "note": "MB 6000, MS 6200, MSS 6300 only.",
        },
        {
            "title": "Parking brake",
            "keys": ("j",),
            "note": "MB 6000 only.",
        },
    )
    repeat_displays = (
        {
            "title": "Gross weight",
            "keys": ("e", "k"),
            "note": "MB 6000 and MS 6200 only.",
        },
        {
            "title": "Max. values, front axle",
            "keys": ("e", "h"),
            "note": "MB 6000, MS 6200, MSS 6300 only.",
        },
        {
            "title": "Max. values, rear axle",
            "keys": ("e", "i"),
            "note": "MB 6000, MS 6200, MSS 6300 only.",
        },
        {
            "title": "Max. values, parking brake",
            "keys": ("e", "j"),
            "note": "MB 6000 only.",
        },
        {
            "title": "Imbalance",
            "keys": ("e", "d"),
            "detail": (
                "If several imbalance measurements are made, measurement 1 is shown "
                "first. Repeating the same command advances to measurement 2 and later "
                "measurements. Only the imbalance values for the axle last tested are "
                "shown."
            ),
            "note": "MB 6000 only.",
        },
        {
            "title": "Frequency of resonance",
            "keys": ("e", "d"),
            "note": "MS 6200 only.",
        },
    )
    printout = (
        {
            "title": "Standard printout with concluding evaluation",
            "keys": ("f",),
        },
        {
            "title": "Standard printout",
            "keys": ("e", "f"),
        },
        {
            "title": "Graphic printout",
            "keys": ("g",),
        },
        {
            "title": "Concluding evaluation",
            "keys": ("e", "g"),
        },
    )
    clear_functions = (
        {
            "title": "Erase last measurement",
            "keys": ("q",),
        },
        {
            "title": "Erase complete memory",
            "keys": ("e", "q"),
        },
    )

    sections = (
        _render_guide_manual_section(
            "Testing programs",
            "Manual 5.1.1",
            testing_programs,
            intro="Infrared remote commands for selecting the measurement program.",
        ),
        _render_guide_manual_section(
            "Entering gross weight",
            "Manual 5.1.2",
            gross_weight,
            intro="The manual shows this as a short entry workflow rather than a single button.",
        ),
        _render_guide_manual_section(
            "Store functions",
            "Manual 5.1.3",
            store_functions,
            intro="Use these to assign and save the measured result.",
        ),
        _render_guide_manual_section(
            "Repeat displays",
            "Manual 5.1.4",
            repeat_displays,
            intro="These commands recall stored values and repeat result displays.",
        ),
        _render_guide_manual_section(
            "Printout",
            "Manual 5.1.5",
            printout,
            intro="The desired printout language is selected in the configuration routine.",
            notes=(
                "For national specification Switzerland (configuration stage 11, no. 1), "
                "the printout for braking forces is reduced by a factor of 0.83.",
                "For national specification Netherlands (configuration stage 11, no. 2), "
                "the printout for braking effect is expressed as braking deceleration in m/s^2.",
            ),
        ),
        _render_guide_manual_section(
            "Clear functions",
            "Manual 5.1.6",
            clear_functions,
            notes=(
                "Stored values can always be overwritten by entering a new value for the "
                "same assignment, or by storing again for the same axle.",
                "The entire memory is also erased if one or more printouts are made and a "
                "new measurement is stored.",
            ),
        ),
    )
    return "".join(sections)


def _render_guide_trigger() -> str:
    return (
        '<button type="button" class="guide-trigger" '
        'style="grid-column: 4; grid-row: 5 / span 2;" '
        'data-guide-trigger="true" '
        'aria-controls="remote-guide" '
        'aria-label="Open the remote guide. Tap twice to open.">'
        '<span class="guide-trigger__inner">'
        '<span class="guide-trigger__eyebrow">Guide</span>'
        '<span class="guide-trigger__face" aria-hidden="true">?</span>'
        '<span class="guide-trigger__hint">2 taps</span>'
        "</span>"
        "</button>"
    )


def _render_remote_guide() -> str:
    combo_buttons = _render_guide_button_cluster("b", "c")
    second_buttons = _render_guide_button_cluster("e", "a")
    stop_buttons = _render_guide_button_cluster("p")
    manual_sections_html = _render_manual_command_sections()

    return f"""
  <aside
    id="remote-guide"
    class="guide-overlay"
    role="dialog"
    aria-modal="true"
    aria-labelledby="guide-title"
    hidden
  >
    <div class="guide-panel">
      <header class="guide-header">
        <div class="guide-header-copy">
          <p class="guide-kicker">Remote Guide</p>
          <h2 id="guide-title" class="guide-title">How the remote works</h2>
        </div>
        <button type="button" id="guide-close" class="guide-close" aria-label="Close remote guide">
          Close
        </button>
      </header>
      <div class="guide-body">
        <details class="guide-section">
          <summary class="guide-summary">
            <span class="guide-summary-title">Single buttons and combos</span>
            <span class="guide-summary-meta">One press or a grouped sequence</span>
          </summary>
          <div class="guide-section-body">
            <p>
              A single press waits briefly before it is sent. If you tap another button
              during that short delay, the remote groups them into one combo and restarts
              the timer from the latest tap.
            </p>
            <div class="guide-example">
              {combo_buttons}
              <div class="guide-example-copy">
                <h4>Combo example</h4>
                <p>
                  Press one button, then another before the wait ends. When the timer
                  expires, the computer sends the full sequence together.
                </p>
              </div>
            </div>
          </div>
        </details>
        <details class="guide-section">
          <summary class="guide-summary">
            <span class="guide-summary-title">The secondary switch</span>
            <span class="guide-summary-meta">Arms one secondary action</span>
          </summary>
          <div class="guide-section-body">
            <p>
              This switch changes the next compatible press only. After that secondary
              action is sent, the switch returns to its normal off state automatically.
            </p>
            <div class="guide-example">
              {second_buttons}
              <div class="guide-example-copy">
                <h4>How it behaves</h4>
                <p>
                  Arm the switch first, then press a compatible button. The next action
                  uses the secondary behavior once and the remote immediately resets.
                </p>
              </div>
            </div>
          </div>
        </details>
        <details class="guide-section">
          <summary class="guide-summary">
            <span class="guide-summary-title">Emergency stop</span>
            <span class="guide-summary-meta">Always sent right away</span>
          </summary>
          <div class="guide-section-body">
            <p>
              The stop control bypasses the combo wait window, clears anything still
              pending, and ignores the secondary switch.
            </p>
            <div class="guide-example">
              {stop_buttons}
              <div class="guide-example-copy">
                <h4>Immediate send</h4>
                <p>
                  Use this when the stop command must go out instantly, even if another
                  combo was still building.
                </p>
              </div>
            </div>
          </div>
        </details>
        {manual_sections_html}
        <section class="guide-manual-footer" aria-labelledby="guide-manual-title">
          <h3 id="guide-manual-title" class="guide-manual-title">Original manual</h3>
          <p class="guide-manual-note">
            Open the full PDF manual in a new tab for the complete original reference.
          </p>
          <a
            href="/manual.pdf"
            target="_blank"
            rel="noopener"
            class="guide-manual-button"
            aria-label="Open the full PDF manual in a new tab"
          >
            Open full PDF manual
          </a>
        </section>
      </div>
    </div>
  </aside>
""".strip()


def render_page(allowed_keys: Tuple[str, ...], urls: List[str], backend_name: str) -> str:
    controls = _build_remote_control_specs(allowed_keys)
    buttons_html = "\n".join(_render_remote_button(spec) for spec in controls)
    guide_trigger_html = _render_guide_trigger()
    guide_html = _render_remote_guide()
    primary_url = urls[0] if urls else "http://localhost"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="theme-color" content="#0a0e15" />
  <title>Mobile Typer Remote</title>
  <style>
    :root {{
      --scene-1: #05070c;
      --scene-2: #0d1320;
      --scene-3: #1c1d25;
      --deck-1: #04070d;
      --deck-2: #0f131d;
      --deck-edge: rgba(232, 197, 118, 0.3);
      --deck-shadow: 0 28px 60px rgba(0, 0, 0, 0.46);
      --button-face-1: #171a25;
      --button-face-2: #0d1118;
      --button-edge: rgba(226, 206, 148, 0.48);
      --button-text: #f5f4ea;
      --button-muted: rgba(238, 229, 201, 0.82);
      --button-port-1: #adb2ad;
      --button-port-2: #747b7d;
      --chip-success: #c9ffcf;
      --chip-error: #ffe1e7;
      --chip-busy: #fff2c2;
      --chip-bg: rgba(9, 14, 23, 0.9);
    }}

    * {{
      box-sizing: border-box;
    }}

    html {{
      -webkit-text-size-adjust: 100%;
    }}

    body {{
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 0.1rem;
      background:
        radial-gradient(circle at top center, rgba(255, 198, 95, 0.08), transparent 16rem),
        radial-gradient(circle at 50% 115%, rgba(82, 101, 178, 0.24), transparent 20rem),
        linear-gradient(180deg, var(--scene-3), var(--scene-1) 32%, var(--scene-2));
      color: var(--button-text);
      font-family: "Trebuchet MS", "Arial Narrow", "Segoe UI", sans-serif;
    }}

    body.guide-open {{
      overflow: hidden;
    }}

    button {{
      font: inherit;
    }}

    .sr-only {{
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }}

    .remote-scene {{
      width: min(100%, 30rem);
      min-height: calc(100svh - 0.2rem);
      display: flex;
      flex-direction: column;
      align-items: stretch;
      justify-content: stretch;
      gap: 0.7rem;
    }}

    .button-deck {{
      width: 100%;
      flex: 1 1 auto;
      display: flex;
      align-self: stretch;
      border-radius: 1.6rem;
      padding: 0.28rem;
      background:
        radial-gradient(circle at top center, rgba(255, 225, 132, 0.08), transparent 13rem),
        linear-gradient(180deg, var(--deck-1), var(--deck-2));
      border: 1px solid var(--deck-edge);
      box-shadow: var(--deck-shadow);
      position: relative;
    }}

    .button-deck::before {{
      content: "";
      position: absolute;
      inset: 0.18rem;
      border-radius: 1.28rem;
      border: 1px solid rgba(255, 241, 199, 0.08);
      pointer-events: none;
    }}

    .keypad-grid {{
      flex: 1 1 auto;
      height: 100%;
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      grid-template-rows: repeat(6, minmax(5.8rem, 1fr));
      row-gap: 0.72rem;
      column-gap: 0.98rem;
      position: relative;
      z-index: 1;
      align-content: stretch;
    }}

    .guide-trigger {{
      appearance: none;
      align-self: stretch;
      justify-self: stretch;
      position: relative;
      border: 1px solid rgba(255, 248, 226, 0.14);
      border-radius: 1.16rem;
      padding: 0.18rem;
      background:
        linear-gradient(180deg, rgba(255, 250, 220, 0.05), transparent 18%),
        linear-gradient(180deg, rgba(22, 27, 38, 0.9), rgba(8, 10, 15, 0.98));
      color: rgba(255, 245, 214, 0.46);
      box-shadow:
        0 0 0 1px rgba(255, 248, 226, 0.03),
        0 0 18px rgba(0, 0, 0, 0.22);
      opacity: 0.54;
      transition:
        opacity 140ms ease,
        color 140ms ease,
        border-color 140ms ease,
        box-shadow 140ms ease,
        background 140ms ease,
        transform 140ms ease;
      touch-action: manipulation;
      overflow: hidden;
      z-index: 1;
    }}

    .guide-trigger::before {{
      content: "";
      position: absolute;
      inset: 0;
      background:
        linear-gradient(124deg, rgba(255, 255, 255, 0.08), transparent 34%, transparent 70%, rgba(255, 255, 255, 0.03));
      opacity: 0.52;
      pointer-events: none;
    }}

    .guide-trigger__inner {{
      position: relative;
      z-index: 1;
      height: 100%;
      border-radius: 0.96rem;
      border: 1px solid rgba(255, 248, 226, 0.08);
      padding: 0.78rem 0.28rem 0.7rem;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: space-between;
      gap: 0.7rem;
      background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.03), transparent 24%),
        linear-gradient(180deg, rgba(17, 21, 31, 0.94), rgba(8, 10, 16, 0.98));
    }}

    .guide-trigger:hover,
    .guide-trigger:focus-visible {{
      opacity: 0.86;
      color: rgba(255, 250, 228, 0.82);
      border-color: rgba(255, 248, 226, 0.26);
      transform: translateY(1px);
    }}

    .guide-trigger:focus-visible {{
      outline: 2px solid rgba(255, 241, 196, 0.82);
      outline-offset: 2px;
    }}

    .guide-trigger.is-armed {{
      opacity: 1;
      transform: translateY(1px);
      color: rgba(255, 252, 242, 0.96);
      border-color: rgba(255, 248, 226, 0.3);
      background:
        linear-gradient(180deg, rgba(38, 45, 58, 0.98), rgba(14, 17, 25, 0.98));
      box-shadow:
        0 0 0 1px rgba(255, 248, 226, 0.05),
        0 0 18px rgba(245, 223, 153, 0.14);
    }}

    .guide-trigger.is-armed .guide-trigger__inner {{
      border-color: rgba(255, 248, 226, 0.12);
      background:
        linear-gradient(180deg, rgba(28, 34, 45, 0.98), rgba(10, 13, 20, 0.98));
    }}

    .guide-trigger__eyebrow,
    .guide-trigger__hint {{
      color: rgba(255, 238, 197, 0.46);
      font-size: 0.62rem;
      font-weight: 800;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      text-align: center;
      line-height: 1.1;
    }}

    .guide-trigger__face {{
      width: 100%;
      flex: 1 1 auto;
      display: grid;
      place-items: center;
      font-size: 2.2rem;
      font-weight: 900;
      letter-spacing: 0.02em;
      line-height: 1;
    }}

    .guide-trigger.is-armed .guide-trigger__eyebrow,
    .guide-trigger.is-armed .guide-trigger__hint {{
      color: rgba(255, 244, 211, 0.78);
    }}

    .remote-button {{
      --band-start: #9a2333;
      --band-end: #70101d;
      --accent-glow: rgba(189, 49, 68, 0.34);
      --top-asset-width: 88%;
      --top-asset-height: 2.2rem;
      --top-asset-justify: center;
      --top-asset-scale: 1;
      --top-asset-shift-x: 0rem;
      --down-asset-width: 78%;
      --down-asset-height: 1.72rem;
      --down-asset-justify: center;
      --down-asset-scale: 1;
      --down-asset-shift-x: 0rem;
      appearance: none;
      position: relative;
      border: 1px solid var(--button-edge);
      border-radius: 1.08rem;
      padding: 0.18rem;
      background:
        linear-gradient(180deg, rgba(255, 250, 220, 0.12), transparent 18%),
        linear-gradient(180deg, rgba(38, 44, 58, 0.96), rgba(9, 11, 18, 0.98));
      color: var(--button-text);
      touch-action: manipulation;
      box-shadow: 0 0 0 1px rgba(255, 248, 222, 0.03), 0 0 18px rgba(0, 0, 0, 0.34);
      transition: transform 90ms ease, box-shadow 90ms ease, filter 90ms ease;
      overflow: hidden;
    }}

    .remote-button::before {{
      content: "";
      position: absolute;
      inset: 0;
      background:
        linear-gradient(124deg, rgba(255, 255, 255, 0.18), transparent 30%, transparent 72%, rgba(255, 255, 255, 0.06));
      pointer-events: none;
      opacity: 0.48;
    }}

    .remote-button:hover,
    .remote-button:active,
    .remote-button.is-firing {{
      transform: translateY(1px);
      box-shadow: 0 0 0 1px rgba(255, 248, 222, 0.06), 0 0 20px var(--accent-glow);
      filter: brightness(1.02);
    }}

    .remote-button--modifier.is-armed {{
      transform: translateY(1px);
      border-color: rgba(244, 247, 255, 0.42);
      background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.86), rgba(208, 216, 230, 0.96));
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.48),
        0 0 0 1px rgba(237, 241, 251, 0.16),
        0 0 24px rgba(232, 238, 255, 0.34);
      filter: brightness(1.04);
      color: #1e293b;
    }}

    .remote-button--modifier.is-armed::before {{
      background:
        linear-gradient(124deg, rgba(255, 255, 255, 0.72), transparent 36%, transparent 68%, rgba(157, 169, 189, 0.16));
      opacity: 0.8;
    }}

    .remote-button--modifier.is-armed .button-inner {{
      border-color: rgba(124, 137, 162, 0.26);
      background:
        linear-gradient(180deg, rgba(247, 250, 255, 0.98), rgba(218, 225, 236, 0.96));
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.9),
        inset 0 -1px 0 rgba(139, 150, 170, 0.16);
    }}

    .remote-button.is-pending {{
      box-shadow:
        0 0 0 1px rgba(255, 248, 222, 0.08),
        0 0 28px rgba(245, 223, 153, 0.2),
        0 0 22px var(--accent-glow);
      filter: brightness(1.05) saturate(1.08);
    }}

    .remote-button.is-pending .button-inner {{
      border-color: rgba(255, 248, 226, 0.18);
    }}

    .remote-button--modifier.is-armed .button-band {{
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.6),
        inset 0 -1px 0 rgba(131, 143, 165, 0.16),
        0 0 18px rgba(230, 236, 255, 0.28);
    }}

    .remote-button--modifier.is-armed .button-band--switch {{
      background:
        radial-gradient(circle at 50% 14%, rgba(255, 255, 255, 0.42), transparent 34%),
        linear-gradient(180deg, rgba(231, 236, 245, 0.98), rgba(198, 208, 223, 0.98));
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.82),
        inset 0 -1px 0 rgba(130, 142, 162, 0.12),
        0 0 18px rgba(230, 236, 255, 0.22);
    }}

    .remote-button--modifier.is-armed .button-switch-track {{
      border-color: rgba(255, 255, 255, 0.46);
      background:
        linear-gradient(180deg, rgba(244, 248, 255, 0.98), rgba(215, 224, 238, 0.94));
      box-shadow:
        inset 0 1px 2px rgba(255, 255, 255, 0.38),
        inset 0 -1px 3px rgba(116, 127, 149, 0.18);
    }}

    .remote-button--modifier .button-band--switch {{
      position: relative;
      flex: 1 1 auto;
      min-height: 3.75rem;
      padding: 0.08rem;
      border-radius: 1.08rem;
      display: flex;
      align-items: stretch;
      justify-content: stretch;
      background:
        radial-gradient(circle at 50% 14%, rgba(255, 248, 226, 0.08), transparent 34%),
        linear-gradient(180deg, rgba(16, 21, 31, 0.98), rgba(7, 9, 14, 0.98));
      box-shadow:
        inset 0 2px 8px rgba(0, 0, 0, 0.38),
        inset 0 -1px 0 rgba(255, 255, 255, 0.05),
        0 0 18px rgba(207, 213, 239, 0.14);
      overflow: hidden;
    }}

    .button-switch-track {{
      position: relative;
      width: 100%;
      flex: 1 1 auto;
      min-height: 100%;
      margin: 0;
      border-radius: 0.94rem;
      border: 1px solid rgba(255, 248, 226, 0.14);
      background:
        linear-gradient(180deg, rgba(6, 9, 14, 0.98), rgba(19, 25, 36, 0.92));
      box-shadow:
        inset 0 1px 2px rgba(255, 255, 255, 0.04),
        inset 0 -1px 3px rgba(0, 0, 0, 0.32);
      overflow: hidden;
    }}

    .button-switch-state {{
      position: absolute;
      left: 50%;
      z-index: 1;
      width: calc(100% - 0.55rem);
      transform: translateX(-50%);
      font-size: 0.62rem;
      font-weight: 800;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      text-align: center;
      text-shadow: 0 1px 0 rgba(0, 0, 0, 0.34);
      transition: color 120ms ease, opacity 120ms ease, filter 120ms ease;
      pointer-events: none;
    }}

    .button-switch-state--off {{
      top: 0.42rem;
      color: rgba(255, 248, 226, 0.92);
      opacity: 1;
    }}

    .button-switch-state--on {{
      bottom: 0.42rem;
      color: rgba(233, 239, 255, 0.92);
      opacity: 0;
    }}

    .button-switch-thumb {{
      position: absolute;
      top: 0.18rem;
      left: 0.18rem;
      right: 0.18rem;
      height: calc(50% - 0.27rem);
      display: grid;
      place-items: center;
      border-radius: 0.86rem;
      border: 1px solid rgba(255, 248, 226, 0.2);
      background:
        linear-gradient(180deg, #f3f0e3, #cbd1e0);
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.68),
        0 0.18rem 0.4rem rgba(0, 0, 0, 0.36);
      transition:
        transform 140ms ease,
        border-color 140ms ease,
        background 140ms ease,
        box-shadow 140ms ease;
      transform: translateY(calc(100% + 0.16rem));
    }}

    .button-switch-thumb-face {{
      color: #1b202c;
      font-size: 1.08rem;
      font-weight: 900;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      text-shadow: 0 1px 0 rgba(255, 255, 255, 0.22);
    }}

    .remote-button--modifier .button-inner {{
      padding-bottom: 0.22rem;
      justify-content: flex-start;
      gap: 0.24rem;
    }}

    .remote-button--modifier .button-top {{
      min-height: 1.18rem;
    }}

    .remote-button--modifier .button-caption-top {{
      min-height: 0;
      font-size: 0.88rem;
      letter-spacing: 0.1em;
    }}

    .remote-button--modifier .button-bottom {{
      display: none;
    }}

    .remote-button--modifier.is-armed .button-switch-state--off {{
      opacity: 0;
    }}

    .remote-button--modifier.is-armed .button-switch-state--on {{
      opacity: 1;
      color: #121212;
      text-shadow: none;
    }}

    .remote-button--modifier.is-armed .button-switch-thumb {{
      transform: translateY(0);
      border-color: rgba(247, 250, 255, 0.26);
      background:
        linear-gradient(180deg, #f8fbff, #d8e1f6);
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.82),
        0 0.2rem 0.4rem rgba(52, 63, 96, 0.34);
    }}

    .remote-button--modifier.is-armed .button-caption-top,
    .remote-button--modifier.is-armed .button-switch-thumb-face {{
      color: #121212;
      text-shadow: none;
    }}

    .remote-button--modifier.is-armed .button-asset--top svg,
    .remote-button--modifier.is-armed .button-asset--top svg * {{
      fill: #121212;
      stroke: #121212;
    }}

    .remote-scene[data-secondary-armed="true"] .remote-button--has-secondary {{
      transform: translateY(1px);
      box-shadow:
        inset 0 2px 9px rgba(0, 0, 0, 0.34),
        0 0 0 1px rgba(237, 241, 251, 0.06),
        0 0 22px rgba(207, 213, 239, 0.16);
      filter: brightness(1.02) saturate(0.86);
    }}

    .remote-scene[data-secondary-armed="true"] .remote-button--has-secondary .button-inner {{
      border-color: rgba(236, 240, 250, 0.12);
      background:
        linear-gradient(180deg, rgba(17, 21, 31, 0.98), rgba(8, 10, 16, 0.98));
      box-shadow:
        inset 0 2px 10px rgba(0, 0, 0, 0.38),
        inset 0 -1px 0 rgba(255, 255, 255, 0.03);
    }}

    .remote-scene[data-secondary-armed="true"] .remote-button--has-secondary .button-bottom {{
      background:
        radial-gradient(circle at top center, rgba(232, 236, 245, 0.18), transparent 5rem),
        linear-gradient(180deg, rgba(89, 96, 115, 0.3), rgba(18, 20, 28, 0.18));
      box-shadow:
        inset 0 0 0 1px rgba(230, 235, 246, 0.16),
        inset 0 2px 8px rgba(17, 20, 29, 0.24),
        0 0 16px rgba(207, 213, 239, 0.12);
    }}

    .remote-scene[data-secondary-armed="true"] .remote-button--has-secondary .button-asset--down,
    .remote-scene[data-secondary-armed="true"] .remote-button--has-secondary .button-caption-bottom,
    .remote-scene[data-secondary-armed="true"] .remote-button--has-secondary .button-bottom .button-icon {{
      color: #ffffff;
      opacity: 1;
      filter:
        brightness(1.28)
        saturate(1.18)
        drop-shadow(0 0 0.65rem rgba(245, 249, 255, 0.5));
    }}

    .remote-scene[data-secondary-armed="true"] .remote-button--has-secondary .button-asset--top,
    .remote-scene[data-secondary-armed="true"] .remote-button--has-secondary .button-caption-top,
    .remote-scene[data-secondary-armed="true"] .remote-button--has-secondary .button-top .button-icon {{
      opacity: 0.28;
      filter: saturate(0.62) brightness(0.8);
    }}

    .remote-scene[data-secondary-armed="true"] .remote-button:not(.remote-button--has-secondary):not(.remote-button--modifier) {{
      filter: saturate(0.84) brightness(0.94);
      opacity: 0.88;
    }}

    .remote-button:focus-visible {{
      outline: 2px solid rgba(255, 241, 196, 0.82);
      outline-offset: 2px;
    }}

    .remote-button--tall {{
      border-radius: 1.16rem;
    }}

    .button-inner {{
      position: relative;
      z-index: 1;
      height: 100%;
      border-radius: 0.92rem;
      border: 1px solid rgba(255, 249, 228, 0.09);
      padding: 0.42rem 0.24rem 0.3rem;
      display: flex;
      flex-direction: column;
      align-items: stretch;
      justify-content: space-between;
      gap: 0.32rem;
      background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.03), transparent 24%),
        linear-gradient(180deg, rgba(24, 28, 40, 0.94), rgba(11, 14, 21, 0.98));
    }}

    .button-top,
    .button-bottom {{
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 0.24rem;
      min-height: 1.6rem;
    }}

    .button-top {{
      min-height: 2rem;
    }}

    .button-bottom {{
      position: relative;
      border-radius: 0.72rem;
      transition: background 120ms ease, box-shadow 120ms ease, opacity 120ms ease, filter 120ms ease;
    }}

    .button-spacer {{
      display: block;
      min-height: 1.15rem;
    }}

    .button-icon {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 1.55rem;
      height: 1.55rem;
      color: var(--button-muted);
    }}

    .button-asset {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      line-height: 0;
    }}

    .button-asset--top {{
      width: var(--top-asset-width);
      height: var(--top-asset-height);
      justify-content: var(--top-asset-justify);
    }}

    .button-asset--down {{
      width: var(--down-asset-width);
      height: var(--down-asset-height);
      justify-content: var(--down-asset-justify);
    }}

    .button-asset svg {{
      display: block;
      width: auto;
      height: 100%;
      max-width: 100%;
      max-height: 100%;
    }}

    .button-asset--top svg {{
      transform: translateX(var(--top-asset-shift-x)) scale(var(--top-asset-scale));
      transform-origin: center;
    }}

    .button-asset--down svg {{
      transform: translateX(var(--down-asset-shift-x)) scale(var(--down-asset-scale));
      transform-origin: center;
    }}

    .button-icon svg {{
      width: 100%;
      height: 100%;
      fill: none;
      stroke: currentColor;
      stroke-width: 1.7;
      stroke-linecap: round;
      stroke-linejoin: round;
    }}

    .button-caption {{
      color: var(--button-muted);
      font-size: 0.82rem;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      text-align: center;
      line-height: 1;
    }}

    .button-caption-top {{
      min-height: 1.25rem;
      display: grid;
      place-items: center;
    }}

    .button-caption-bottom {{
      font-size: 0.78rem;
      margin-bottom: 0.04rem;
    }}

    .button-band {{
      min-height: 2.05rem;
      display: grid;
      place-items: center;
      border-radius: 999px;
      border: 1px solid rgba(255, 248, 226, 0.16);
      background: linear-gradient(180deg, var(--band-start), var(--band-end));
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.18), 0 0 16px var(--accent-glow);
    }}

    .button-letter {{
      color: #fffaf2;
      font-size: 1.52rem;
      font-weight: 800;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      text-shadow: 0 1px 0 rgba(0, 0, 0, 0.35);
    }}

    .remote-button--tall .button-inner {{
      padding-top: 0.5rem;
      padding-bottom: 0.4rem;
    }}

    .remote-button--tall .button-caption-top {{
      min-height: 1.55rem;
      font-size: 0.98rem;
    }}

    .remote-button--tall .button-asset--top {{
      width: min(92%, calc(var(--top-asset-width) + 4%));
      height: max(2.4rem, var(--top-asset-height));
    }}

    .remote-button--tall .button-asset--down {{
      width: min(84%, calc(var(--down-asset-width) + 4%));
      height: max(1.95rem, var(--down-asset-height));
    }}

    .remote-button--tall .button-letter {{
      font-size: 1.72rem;
    }}

    .button-port {{
      width: 48%;
      height: 0.58rem;
      border-radius: 999px;
      border: 1px solid rgba(250, 249, 238, 0.14);
      background: linear-gradient(180deg, var(--button-port-1), var(--button-port-2));
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.16);
    }}

    .accent-scarlet {{
      --band-start: #c01128;
      --band-end: #850716;
      --accent-glow: rgba(213, 28, 54, 0.34);
    }}

    .accent-crimson {{
      --band-start: #bc132d;
      --band-end: #89131f;
      --accent-glow: rgba(208, 34, 67, 0.32);
    }}

    .accent-magenta {{
      --band-start: #b42e68;
      --band-end: #7a1f48;
      --accent-glow: rgba(196, 61, 129, 0.3);
    }}

    .accent-violet {{
      --band-start: #a778c5;
      --band-end: #7f5a9a;
      --accent-glow: rgba(180, 130, 218, 0.32);
    }}

    .accent-silver {{
      --band-start: #c3c5da;
      --band-end: #9298ac;
      --accent-glow: rgba(207, 213, 239, 0.28);
    }}

    .accent-cobalt {{
      --band-start: #2e69dc;
      --band-end: #1949a8;
      --accent-glow: rgba(65, 120, 239, 0.34);
    }}

    .accent-lime {{
      --band-start: #c9cf39;
      --band-end: #8b9823;
      --accent-glow: rgba(207, 220, 66, 0.3);
    }}

    .accent-amber {{
      --band-start: #d6ca43;
      --band-end: #9f8a20;
      --accent-glow: rgba(228, 215, 81, 0.32);
    }}

    .accent-burgundy {{
      --band-start: #8f1430;
      --band-end: #5e081d;
      --accent-glow: rgba(160, 22, 54, 0.28);
    }}

    .accent-berry {{
      --band-start: #8e1f49;
      --band-end: #621232;
      --accent-glow: rgba(160, 41, 91, 0.28);
    }}

    .accent-emerald {{
      --band-start: #14a34a;
      --band-end: #0a7030;
      --accent-glow: rgba(31, 190, 91, 0.3);
    }}

    .status-chip {{
      --status-progress-turn: 0turn;
      --status-label-scale: 1;
      position: fixed;
      left: calc(env(safe-area-inset-left, 0px) + 0.9rem);
      top: calc(env(safe-area-inset-top, 0px) + 0.9rem);
      width: 4rem;
      height: 4rem;
      padding: 0.2rem;
      border-radius: 50%;
      background:
        conic-gradient(
          from -90deg,
          currentColor 0turn var(--status-progress-turn),
          rgba(255, 245, 214, 0.12) var(--status-progress-turn) 1turn
        );
      color: var(--chip-busy);
      box-shadow: 0 14px 30px rgba(0, 0, 0, 0.32);
      opacity: 0;
      transform: translateY(0.55rem) scale(0.96);
      transition: opacity 140ms ease, transform 140ms ease, color 140ms ease;
      pointer-events: none;
      z-index: 3;
    }}

    .status-chip.is-visible {{
      opacity: 1;
      transform: translateY(0) scale(1);
    }}

    .status-chip__face {{
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 50%;
      border: 1px solid rgba(255, 238, 190, 0.14);
      background: var(--chip-bg);
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.06),
        inset 0 -1px 0 rgba(0, 0, 0, 0.28);
    }}

    .status-chip__label {{
      color: inherit;
      font-size: calc(1.06rem * var(--status-label-scale));
      font-weight: 900;
      letter-spacing: calc(0.08em * var(--status-label-scale));
      text-transform: uppercase;
      line-height: 1;
      transform: translateX(0.04em);
    }}

    .status-chip[data-tone="ok"] {{
      color: var(--chip-success);
    }}

    .status-chip[data-tone="error"] {{
      color: var(--chip-error);
    }}

    .status-chip[data-tone="busy"] {{
      color: var(--chip-busy);
    }}

    .guide-overlay[hidden] {{
      display: none;
    }}

    .guide-overlay {{
      --guide-pad-top: max(0.7rem, env(safe-area-inset-top, 0px));
      --guide-pad-right: max(0.7rem, env(safe-area-inset-right, 0px));
      --guide-pad-bottom: max(0.7rem, env(safe-area-inset-bottom, 0px));
      --guide-pad-left: max(0.7rem, env(safe-area-inset-left, 0px));
      position: fixed;
      inset: 0;
      z-index: 8;
      overflow-y: auto;
      overflow-x: hidden;
      overscroll-behavior: contain;
      -webkit-overflow-scrolling: touch;
      padding:
        var(--guide-pad-top)
        var(--guide-pad-right)
        var(--guide-pad-bottom)
        var(--guide-pad-left);
      background:
        radial-gradient(circle at top center, rgba(255, 196, 87, 0.12), transparent 16rem),
        linear-gradient(180deg, rgba(4, 7, 12, 0.98), rgba(9, 13, 22, 0.99));
    }}

    .guide-panel {{
      width: min(100%, 48rem);
      margin: 0 auto;
      min-height: calc(100vh - var(--guide-pad-top) - var(--guide-pad-bottom));
      min-height: calc(100dvh - var(--guide-pad-top) - var(--guide-pad-bottom));
      display: flex;
      flex-direction: column;
      background:
        linear-gradient(180deg, rgba(14, 19, 30, 0.98), rgba(5, 8, 13, 0.98));
      border: 1px solid rgba(255, 236, 184, 0.14);
      box-shadow: 0 24px 54px rgba(0, 0, 0, 0.42);
    }}

    .guide-header {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 1rem;
      padding: 1.15rem 1.1rem 0.95rem;
      border-bottom: 1px solid rgba(255, 236, 184, 0.12);
      background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.03), rgba(255, 255, 255, 0));
    }}

    .guide-header-copy {{
      min-width: 0;
    }}

    .guide-kicker {{
      margin: 0 0 0.36rem;
      color: rgba(255, 230, 171, 0.7);
      font-size: 0.74rem;
      font-weight: 800;
      letter-spacing: 0.18em;
      text-transform: uppercase;
    }}

    .guide-title {{
      margin: 0;
      color: #fffaf2;
      font-size: clamp(1.5rem, 4vw, 2.1rem);
      line-height: 1.06;
    }}

    .guide-close {{
      appearance: none;
      border: 1px solid rgba(255, 244, 211, 0.18);
      border-radius: 999px;
      padding: 0.76rem 0.96rem;
      background:
        linear-gradient(180deg, rgba(43, 50, 65, 0.92), rgba(16, 20, 30, 0.96));
      color: #fff8ea;
      font-size: 0.76rem;
      font-weight: 800;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.08),
        0 0 16px rgba(0, 0, 0, 0.18);
      touch-action: manipulation;
    }}

    .guide-close:focus-visible {{
      outline: 2px solid rgba(255, 241, 196, 0.82);
      outline-offset: 2px;
    }}

    .guide-body {{
      flex: 1 1 auto;
      overflow: visible;
      padding: 1rem 1.1rem 1.5rem;
      display: grid;
      gap: 0.88rem;
    }}

    .guide-intro {{
      border-radius: 1.15rem;
      border: 1px solid rgba(255, 240, 198, 0.12);
      padding: 1rem 1rem 1.02rem;
      background:
        radial-gradient(circle at top left, rgba(255, 201, 96, 0.08), transparent 12rem),
        linear-gradient(180deg, rgba(20, 27, 40, 0.96), rgba(10, 14, 23, 0.98));
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.04),
        0 10px 24px rgba(0, 0, 0, 0.18);
    }}

    .guide-intro-kicker {{
      margin: 0 0 0.4rem;
      color: rgba(255, 226, 165, 0.76);
      font-size: 0.72rem;
      font-weight: 800;
      letter-spacing: 0.18em;
      text-transform: uppercase;
    }}

    .guide-intro-text {{
      margin: 0;
      max-width: 42rem;
      color: rgba(245, 239, 224, 0.92);
      font-size: 0.98rem;
      line-height: 1.58;
    }}

    .guide-section {{
      margin: 0;
      overflow: hidden;
      border-radius: 1.15rem;
      border: 1px solid rgba(255, 240, 198, 0.12);
      background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.03), rgba(255, 255, 255, 0)),
        linear-gradient(180deg, rgba(16, 21, 33, 0.96), rgba(10, 14, 23, 0.98));
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.04),
        0 10px 24px rgba(0, 0, 0, 0.18);
    }}

    .guide-section[open] {{
      border-color: rgba(255, 240, 198, 0.18);
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.05),
        0 12px 26px rgba(0, 0, 0, 0.22);
    }}

    .guide-summary {{
      list-style: none;
      cursor: pointer;
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 0.32rem 0.9rem;
      align-items: center;
      padding: 0.98rem 1rem;
    }}

    .guide-summary::-webkit-details-marker {{
      display: none;
    }}

    .guide-summary:focus-visible {{
      outline: 2px solid rgba(255, 241, 196, 0.82);
      outline-offset: -2px;
    }}

    .guide-summary::after {{
      content: "+";
      grid-column: 2;
      grid-row: 1 / span 2;
      width: 1.9rem;
      height: 1.9rem;
      display: grid;
      place-items: center;
      border-radius: 50%;
      border: 1px solid rgba(255, 244, 211, 0.16);
      background:
        linear-gradient(180deg, rgba(45, 52, 66, 0.94), rgba(16, 20, 30, 0.96));
      color: rgba(255, 245, 214, 0.88);
      font-size: 1.1rem;
      font-weight: 800;
      line-height: 1;
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.08),
        0 0 14px rgba(0, 0, 0, 0.14);
    }}

    .guide-section[open] .guide-summary::after {{
      content: "-";
    }}

    .guide-summary-title {{
      margin: 0;
      color: #fff7eb;
      font-size: 1.02rem;
      font-weight: 800;
      line-height: 1.2;
    }}

    .guide-summary-meta {{
      color: rgba(255, 231, 180, 0.7);
      font-size: 0.76rem;
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }}

    .guide-section-body {{
      padding: 0 1rem 1rem;
      display: grid;
      gap: 0.84rem;
    }}

    .guide-section-body p {{
      margin: 0;
      max-width: 42rem;
      color: rgba(245, 239, 224, 0.9);
      font-size: 0.97rem;
      line-height: 1.55;
    }}

    .guide-section-intro {{
      color: rgba(245, 239, 224, 0.9);
    }}

    .guide-section-note {{
      color: rgba(255, 224, 166, 0.78);
      font-size: 0.85rem;
      line-height: 1.5;
    }}

    .guide-command-list {{
      display: grid;
      gap: 0.72rem;
    }}

    .guide-command {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 0.92rem;
      align-items: flex-start;
      padding: 0.88rem;
      border-radius: 1rem;
      border: 1px solid rgba(255, 244, 211, 0.1);
      background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.03), rgba(255, 255, 255, 0)),
        linear-gradient(180deg, rgba(17, 22, 33, 0.96), rgba(9, 12, 19, 0.98));
    }}

    .guide-command-copy {{
      min-width: 0;
      display: grid;
      gap: 0.28rem;
    }}

    .guide-command-title {{
      margin: 0;
      color: #fff7eb;
      font-size: 0.98rem;
      font-weight: 800;
      line-height: 1.3;
    }}

    .guide-command-detail {{
      color: rgba(245, 239, 224, 0.92);
    }}

    .guide-command-note {{
      color: rgba(255, 224, 166, 0.78);
      font-size: 0.84rem;
      line-height: 1.5;
    }}

    .guide-example {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 0.96rem;
      align-items: flex-start;
      padding: 0.88rem;
      border-radius: 1rem;
      border: 1px solid rgba(255, 244, 211, 0.1);
      background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.03), rgba(255, 255, 255, 0)),
        linear-gradient(180deg, rgba(17, 22, 33, 0.96), rgba(9, 12, 19, 0.98));
    }}

    .guide-example-copy {{
      min-width: 0;
      display: grid;
      gap: 0.34rem;
    }}

    .guide-example-copy h4 {{
      margin: 0;
      color: rgba(255, 232, 183, 0.82);
      font-size: 0.72rem;
      font-weight: 800;
      letter-spacing: 0.18em;
      text-transform: uppercase;
    }}

    .guide-example-copy p {{
      margin: 0;
      max-width: none;
    }}

    .guide-manual-footer {{
      display: grid;
      gap: 0.72rem;
      padding: 1rem;
      border-radius: 1rem;
      border: 1px solid rgba(255, 240, 198, 0.14);
      background:
        radial-gradient(circle at top left, rgba(255, 196, 87, 0.09), transparent 12rem),
        linear-gradient(180deg, rgba(18, 24, 37, 0.98), rgba(9, 12, 20, 0.98));
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.04),
        0 10px 24px rgba(0, 0, 0, 0.18);
    }}

    .guide-manual-title {{
      margin: 0;
      color: #fff7eb;
      font-size: 1rem;
      font-weight: 800;
      line-height: 1.25;
    }}

    .guide-manual-note {{
      margin: 0;
      color: rgba(245, 239, 224, 0.88);
      font-size: 0.9rem;
      line-height: 1.5;
    }}

    .guide-manual-button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 100%;
      min-height: 3.2rem;
      padding: 0.92rem 1.1rem;
      border: 1px solid rgba(255, 236, 184, 0.18);
      border-radius: 999px;
      background:
        linear-gradient(180deg, rgba(255, 199, 90, 0.26), rgba(163, 104, 27, 0.22)),
        linear-gradient(180deg, rgba(39, 45, 60, 0.96), rgba(15, 19, 29, 0.98));
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.08),
        0 12px 28px rgba(0, 0, 0, 0.22);
      color: #fff8ea;
      font-size: 0.8rem;
      font-weight: 800;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      text-decoration: none;
      touch-action: manipulation;
    }}

    .guide-manual-button:hover,
    .guide-manual-button:focus-visible {{
      border-color: rgba(255, 244, 211, 0.36);
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.1),
        0 14px 30px rgba(0, 0, 0, 0.24);
    }}

    .guide-manual-button:focus-visible {{
      outline: 2px solid rgba(255, 241, 196, 0.82);
      outline-offset: 2px;
    }}

    .guide-button-cluster {{
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-start;
      align-items: flex-start;
      gap: 0.48rem;
      padding-bottom: 0.18rem;
      flex: 0 0 auto;
    }}

    .guide-button-cluster--with-modifier {{
      gap: 0.76rem;
      margin-bottom: 1.1rem;
    }}

    .guide-button-separator {{
      width: 1.3rem;
      min-height: calc(5.95rem * 0.6);
      position: relative;
      z-index: 2;
      display: grid;
      place-items: center;
      color: rgba(255, 230, 171, 0.82);
      font-size: 0.98rem;
      font-weight: 800;
      line-height: 1;
      flex: 0 0 auto;
    }}

    .guide-button-separator--step {{
      width: 1.8rem;
      font-size: 0.78rem;
      letter-spacing: 0.08em;
    }}

    .guide-button-ref-wrap {{
      --guide-ref-scale: 0.6;
      --guide-ref-width: 5.4rem;
      --guide-ref-height: 7.3rem;
      position: relative;
      display: inline-block;
      vertical-align: top;
      width: calc(var(--guide-ref-width) * var(--guide-ref-scale));
      height: calc(var(--guide-ref-height) * var(--guide-ref-scale));
      flex: 0 0 auto;
      overflow: visible;
    }}

    .guide-button-ref-wrap--tall {{
      --guide-ref-height: 12.5rem;
    }}

    .guide-button-ref-wrap--modifier-equal {{
      margin-right: 0;
    }}

    .guide-button-ref__control {{
      position: absolute;
      top: 0;
      left: 0;
      display: block;
      width: var(--guide-ref-width);
      height: var(--guide-ref-height);
      transform: scale(var(--guide-ref-scale));
      transform-origin: top left;
      pointer-events: none;
    }}

    .guide-button-ref__control--modifier {{
      height: var(--guide-ref-height);
    }}

    .guide-button-ref__control--guide-modifier-card {{
      border-color: rgba(244, 247, 255, 0.42);
      background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.88), rgba(214, 222, 235, 0.97));
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.52),
        0 0 0 1px rgba(237, 241, 251, 0.16),
        0 0 14px rgba(232, 238, 255, 0.18);
      color: #1e293b;
      filter: brightness(1.02);
    }}

    .guide-button-ref__control--guide-modifier-card::before {{
      background:
        linear-gradient(124deg, rgba(255, 255, 255, 0.74), transparent 36%, transparent 68%, rgba(157, 169, 189, 0.16));
      opacity: 0.78;
    }}

    .guide-button-ref__control--guide-modifier-card .button-inner {{
      border-color: rgba(124, 137, 162, 0.24);
      padding: 0.34rem 0.2rem 0.24rem;
      gap: 0.18rem;
      background:
        linear-gradient(180deg, rgba(247, 250, 255, 0.99), rgba(220, 227, 238, 0.97));
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.92),
        inset 0 -1px 0 rgba(139, 150, 170, 0.16);
    }}

    .guide-button-ref__control--guide-modifier-card .button-top {{
      min-height: 1rem;
    }}

    .guide-button-ref__control--guide-modifier-card .guide-modifier-card__caption {{
      min-height: 0;
      color: #151c28;
      font-size: 0.8rem;
      font-weight: 900;
      letter-spacing: 0.06em;
      text-shadow: none;
    }}

    .guide-button-ref__control--guide-modifier-card .button-band {{
      min-height: 1.78rem;
      border-color: rgba(255, 255, 255, 0.44);
      background:
        linear-gradient(180deg, rgba(240, 244, 251, 0.98), rgba(206, 216, 232, 0.98));
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.88),
        inset 0 -1px 0 rgba(130, 142, 162, 0.14),
        0 0 12px rgba(230, 236, 255, 0.16);
    }}

    .guide-button-ref__control--guide-modifier-card .button-letter {{
      color: #1a2230;
      font-size: 1rem;
      text-shadow: none;
    }}

    .guide-button-ref__control--guide-modifier-card .guide-modifier-card__bottom {{
      min-height: 0.88rem;
      gap: 0;
    }}

    .guide-modifier-card__state {{
      color: #202838;
      font-size: 0.52rem;
      font-weight: 900;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      text-shadow: none;
    }}

    .guide-modifier-card__state--off {{
      opacity: 0.72;
    }}

    .guide-button-ref__control--modifier.remote-button--modifier.is-armed {{
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.48),
        0 0 0 1px rgba(237, 241, 251, 0.16),
        0 0 14px rgba(232, 238, 255, 0.2);
    }}

    .guide-button-ref__control--secondary-target {{
      transform: scale(var(--guide-ref-scale)) translateY(1px);
      box-shadow:
        inset 0 2px 9px rgba(0, 0, 0, 0.34),
        0 0 0 1px rgba(237, 241, 251, 0.06),
        0 0 22px rgba(207, 213, 239, 0.16);
      filter: brightness(1.02) saturate(0.86);
    }}

    .guide-button-ref__control--secondary-target .button-inner {{
      border-color: rgba(236, 240, 250, 0.12);
      background:
        linear-gradient(180deg, rgba(17, 21, 31, 0.98), rgba(8, 10, 16, 0.98));
      box-shadow:
        inset 0 2px 10px rgba(0, 0, 0, 0.38),
        inset 0 -1px 0 rgba(255, 255, 255, 0.03);
    }}

    .guide-button-ref__control--secondary-target .button-bottom {{
      background:
        radial-gradient(circle at top center, rgba(232, 236, 245, 0.18), transparent 5rem),
        linear-gradient(180deg, rgba(89, 96, 115, 0.3), rgba(18, 20, 28, 0.18));
      box-shadow:
        inset 0 0 0 1px rgba(230, 235, 246, 0.16),
        inset 0 2px 8px rgba(17, 20, 29, 0.24),
        0 0 16px rgba(207, 213, 239, 0.12);
    }}

    .guide-button-cluster--with-modifier .guide-button-ref__control--secondary-target .button-bottom {{
      background:
        radial-gradient(circle at top center, rgba(246, 241, 220, 0.24), transparent 5rem),
        linear-gradient(180deg, rgba(108, 116, 137, 0.42), rgba(22, 25, 35, 0.24));
      box-shadow:
        inset 0 0 0 1px rgba(236, 240, 248, 0.2),
        inset 0 2px 8px rgba(17, 20, 29, 0.22),
        0 0 18px rgba(214, 221, 246, 0.16);
    }}

    .guide-button-ref__control--secondary-target .button-asset--down,
    .guide-button-ref__control--secondary-target .button-caption-bottom,
    .guide-button-ref__control--secondary-target .button-bottom .button-icon {{
      color: #ffffff;
      opacity: 1;
      filter:
        brightness(1.28)
        saturate(1.18)
        drop-shadow(0 0 0.65rem rgba(245, 249, 255, 0.5));
    }}

    .guide-button-cluster--with-modifier .guide-button-ref__control--secondary-target .button-asset--down,
    .guide-button-cluster--with-modifier .guide-button-ref__control--secondary-target .button-caption-bottom,
    .guide-button-cluster--with-modifier .guide-button-ref__control--secondary-target .button-bottom .button-icon {{
      color: #fffbea;
      filter:
        brightness(1.4)
        saturate(1.24)
        drop-shadow(0 0 0.7rem rgba(248, 244, 226, 0.56));
    }}

    .guide-button-ref__control--secondary-target .button-asset--top,
    .guide-button-ref__control--secondary-target .button-caption-top,
    .guide-button-ref__control--secondary-target .button-top .button-icon {{
      opacity: 0.28;
      filter: saturate(0.62) brightness(0.8);
    }}

    @media (max-width: 420px) {{
      body {{
        padding: 0.04rem;
      }}

      .remote-scene {{
        min-height: calc(100svh - 0.08rem);
      }}

      .button-deck {{
        padding: 0.16rem;
      }}

      .keypad-grid {{
        grid-template-rows: repeat(6, minmax(5.15rem, 1fr));
        row-gap: 0.52rem;
        column-gap: 0.76rem;
      }}

      .button-letter {{
        font-size: 1.36rem;
      }}

      .remote-button--tall .button-letter {{
        font-size: 1.56rem;
      }}

      .guide-trigger__inner {{
        padding: 0.7rem 0.22rem 0.62rem;
      }}

      .guide-trigger__face {{
        font-size: 1.9rem;
      }}

      .guide-header {{
        padding: 1rem 0.92rem 0.82rem;
      }}

      .guide-body {{
        padding: 0.92rem;
      }}

      .guide-summary {{
        padding: 0.9rem 0.88rem;
      }}

      .guide-section-body {{
        padding: 0 0.88rem 0.92rem;
      }}

      .guide-command {{
        padding: 0.82rem;
      }}

      .guide-example {{
        padding: 0.82rem;
      }}

      .guide-manual-footer {{
        padding: 0.82rem;
      }}

      .guide-button-cluster {{
        gap: 0.58rem;
      }}

      .guide-button-separator {{
        width: 1rem;
        min-height: calc(5.95rem * 0.56);
      }}

      .guide-button-separator--step {{
        width: 1.45rem;
      }}

      .guide-button-ref-wrap {{
        --guide-ref-scale: 0.56;
      }}

      .guide-button-ref__control--guide-modifier-card .button-inner {{
        padding: 0.3rem 0.18rem 0.22rem;
      }}

      .guide-button-ref__control--guide-modifier-card .guide-modifier-card__caption {{
        font-size: 0.76rem;
      }}

      .guide-button-ref__control--guide-modifier-card .button-band {{
        min-height: 1.64rem;
      }}

      .guide-button-ref__control--guide-modifier-card .button-letter {{
        font-size: 0.94rem;
      }}

      .guide-modifier-card__state {{
        font-size: 0.48rem;
      }}
    }}
  </style>
</head>
<body>
  <main
    class="remote-scene"
    data-primary-url="{html.escape(primary_url)}"
    data-backend="{html.escape(backend_name)}"
    data-secondary-armed="false"
  >
    <h1 class="sr-only">Mobile Typer hardware remote</h1>
    <section class="button-deck" aria-label="Virtual remote control buttons">
      <div class="keypad-grid">
        {buttons_html}
        {guide_trigger_html}
      </div>
    </section>
    <div id="status-chip" class="status-chip" data-tone="busy" aria-hidden="true">
      <div class="status-chip__face">
        <span id="status-label" class="status-chip__label"></span>
      </div>
    </div>
    <div id="status-announcer" class="sr-only" aria-live="polite" aria-atomic="true"></div>
  </main>
  {guide_html}

  <script>
    const comboWindowMs = {COMBO_WINDOW_MS};
    const guideTapWindowMs = 700;
    const emergencyStopKey = "{EMERGENCY_STOP_KEY}";
    const remoteScene = document.querySelector(".remote-scene");
    const controls = [...document.querySelectorAll("[data-key]")];
    const secondaryControl = controls.find(
      (control) => control.dataset.isSecondaryModifier === "true"
    );
    const guideTrigger = document.querySelector("[data-guide-trigger]");
    const guideOverlay = document.getElementById("remote-guide");
    const guideCloseButton = document.getElementById("guide-close");
    const statusChip = document.getElementById("status-chip");
    const statusLabel = document.getElementById("status-label");
    const statusAnnouncer = document.getElementById("status-announcer");
    let hideStatusTimer = null;
    let statusCountdownFrame = null;
    let secondaryArmed = false;
    let pendingControls = [];
    let pendingTimer = null;
    let guideTapTimer = null;

    function getControlLabel(control) {{
      return control.dataset.label || control.dataset.key.toUpperCase();
    }}

    function isEmergencyStopControl(control) {{
      return control.dataset.key === emergencyStopKey;
    }}

    function getSequenceLabel(controlSequence) {{
      return controlSequence.map((control) => getControlLabel(control)).join("");
    }}

    function getSequenceAnnouncement(controlSequence) {{
      return controlSequence.map((control) => getControlLabel(control)).join(" + ");
    }}

    function clearStatusCountdown() {{
      if (statusCountdownFrame) {{
        window.cancelAnimationFrame(statusCountdownFrame);
        statusCountdownFrame = null;
      }}
      statusChip.style.setProperty("--status-progress-turn", "0turn");
    }}

    function startStatusCountdown(durationMs) {{
      clearStatusCountdown();
      if (!durationMs || durationMs <= 0) {{
        return;
      }}

      const startedAt = window.performance.now();
      statusChip.style.setProperty("--status-progress-turn", "1turn");

      function tick(now) {{
        const elapsed = now - startedAt;
        const progress = Math.max(0, 1 - elapsed / durationMs);
        statusChip.style.setProperty("--status-progress-turn", progress + "turn");
        if (progress > 0) {{
          statusCountdownFrame = window.requestAnimationFrame(tick);
          return;
        }}
        statusCountdownFrame = null;
      }}

      statusCountdownFrame = window.requestAnimationFrame(tick);
    }}

    function hideStatus() {{
      if (hideStatusTimer) {{
        window.clearTimeout(hideStatusTimer);
        hideStatusTimer = null;
      }}
      clearStatusCountdown();
      statusChip.classList.remove("is-visible");
    }}

    function clearGuideTapState() {{
      if (guideTapTimer) {{
        window.clearTimeout(guideTapTimer);
        guideTapTimer = null;
      }}
      if (!guideTrigger) {{
        return;
      }}
      guideTrigger.classList.remove("is-armed");
    }}

    function armGuideTrigger() {{
      if (!guideTrigger) {{
        return;
      }}
      clearGuideTapState();
      guideTrigger.classList.add("is-armed");
      statusAnnouncer.textContent = "Guide ready. Tap again to open.";
      guideTapTimer = window.setTimeout(() => {{
        clearGuideTapState();
      }}, guideTapWindowMs);
    }}

    function openGuide() {{
      if (!guideOverlay || !guideCloseButton) {{
        return;
      }}
      clearGuideTapState();
      clearPendingControls();
      clearSecondary();
      hideStatus();
      guideOverlay.hidden = false;
      document.body.classList.add("guide-open");
      if (remoteScene) {{
        remoteScene.setAttribute("aria-hidden", "true");
      }}
      statusAnnouncer.textContent = "Remote guide opened.";
      guideCloseButton.focus();
    }}

    function closeGuide() {{
      if (!guideOverlay || guideOverlay.hidden) {{
        return;
      }}
      clearGuideTapState();
      guideOverlay.hidden = true;
      document.body.classList.remove("guide-open");
      if (remoteScene) {{
        remoteScene.removeAttribute("aria-hidden");
      }}
      statusAnnouncer.textContent = "Remote guide closed.";
      if (guideTrigger) {{
        guideTrigger.focus();
      }}
    }}

    function handleGuideTriggerClick() {{
      if (!guideTrigger) {{
        return;
      }}
      if (guideOverlay && !guideOverlay.hidden) {{
        return;
      }}
      if (guideTrigger.classList.contains("is-armed")) {{
        openGuide();
        return;
      }}
      armGuideTrigger();
    }}

    function setStatus(label, tone, announceMessage, options) {{
      const settings = options || {{}};
      const hideAfterMs =
        settings.hideAfterMs === undefined
          ? tone === "error"
            ? 2600
            : 900
          : settings.hideAfterMs;
      const countdownMs = settings.countdownMs || 0;
      const labelLength = Math.max(1, label.length);
      const labelScale =
        labelLength <= 2 ? 1 : labelLength <= 4 ? 0.8 : 0.66;

      statusLabel.textContent = label;
      statusChip.style.setProperty("--status-label-scale", String(labelScale));
      statusChip.dataset.tone = tone || "busy";
      statusChip.classList.add("is-visible");
      statusAnnouncer.textContent = announceMessage || label;
      if (hideStatusTimer) {{
        window.clearTimeout(hideStatusTimer);
        hideStatusTimer = null;
      }}
      if (countdownMs > 0) {{
        startStatusCountdown(countdownMs);
      }} else {{
        clearStatusCountdown();
      }}
      if (hideAfterMs !== null) {{
        hideStatusTimer = window.setTimeout(() => {{
          hideStatus();
        }}, hideAfterMs);
      }}
    }}

    function pulseControl(control) {{
      control.classList.remove("is-firing");
      void control.offsetWidth;
      control.classList.add("is-firing");
      window.setTimeout(() => {{
        control.classList.remove("is-firing");
      }}, 170);
    }}

    function restartPendingTimer() {{
      if (pendingTimer) {{
        window.clearTimeout(pendingTimer);
      }}
      pendingTimer = window.setTimeout(() => {{
        void flushPendingSequence();
      }}, comboWindowMs);
    }}

    function clearPendingControls() {{
      if (pendingTimer) {{
        window.clearTimeout(pendingTimer);
        pendingTimer = null;
      }}
      if (!pendingControls.length) {{
        return;
      }}
      for (const control of pendingControls) {{
        control.classList.remove("is-pending");
      }}
      pendingControls = [];
    }}

    function showPendingStatus(controlSequence) {{
      const label = getSequenceLabel(controlSequence);
      setStatus(
        label,
        "busy",
        label + " waiting to send or extend a combo.",
        {{ hideAfterMs: null, countdownMs: comboWindowMs }}
      );
    }}

    function addPendingControl(control) {{
      pendingControls.push(control);
      control.classList.add("is-pending");
      showPendingStatus(pendingControls);
      restartPendingTimer();
    }}

    async function postPress(payload) {{
      const response = await fetch("/api/press", {{
        method: "POST",
        headers: {{
          "Content-Type": "application/json"
        }},
        body: JSON.stringify(payload)
      }});

      const responsePayload = await response.json();
      if (!response.ok) {{
        throw new Error(responsePayload.error || "Request failed");
      }}
      return responsePayload;
    }}

    function syncSecondaryControl() {{
      if (remoteScene) {{
        remoteScene.dataset.secondaryArmed = secondaryArmed ? "true" : "false";
      }}
      if (!secondaryControl) {{
        return;
      }}
      secondaryControl.classList.toggle("is-armed", secondaryArmed);
      secondaryControl.setAttribute("aria-checked", secondaryArmed ? "true" : "false");
    }}

    function toggleSecondary() {{
      secondaryArmed = !secondaryArmed;
      syncSecondaryControl();
      setStatus(
        "E",
        secondaryArmed ? "busy" : "ok",
        secondaryArmed
          ? "2nd switch on. It turns off after the next key press."
          : "2nd switch off. Top actions are active.",
        {{ hideAfterMs: 850 }}
      );
      if (navigator.vibrate) {{
        navigator.vibrate(12);
      }}
    }}

    function clearSecondary() {{
      if (!secondaryArmed) {{
        return;
      }}
      secondaryArmed = false;
      syncSecondaryControl();
    }}

    async function sendSingleControl(control) {{
      const key = control.dataset.key;
      const label = getControlLabel(control);
      const isSecondaryModifier = control.dataset.isSecondaryModifier === "true";
      const hasSecondary = control.dataset.hasSecondary === "true";

      if (isSecondaryModifier) {{
        pulseControl(control);
        toggleSecondary();
        return;
      }}

      const secondaryWasArmed = secondaryArmed;
      const useSecondary = secondaryWasArmed && hasSecondary;
      const announceLabel = useSecondary ? "secondary " + label : label;
      pulseControl(control);
      setStatus(label, "busy", "Sending " + announceLabel + ".", {{ hideAfterMs: null }});

      try {{
        await postPress({{ key, use_secondary: useSecondary }});

        if (navigator.vibrate) {{
          navigator.vibrate(useSecondary ? [12, 32, 12] : 12);
        }}

        if (secondaryWasArmed) {{
          clearSecondary();
          setStatus(
            label,
            "ok",
            "Sent " + announceLabel + ". 2nd switch is off.",
            {{ hideAfterMs: 850 }}
          );
        }} else {{
          setStatus(label, "ok", "Sent " + announceLabel + ".", {{ hideAfterMs: 850 }});
        }}
      }} catch (error) {{
        const message = error && error.message ? error.message : "Request failed";
        setStatus("ERR", "error", "Error sending " + announceLabel + ": " + message, {{
          hideAfterMs: 2600
        }});
      }}
    }}

    async function sendEmergencyStopControl(control) {{
      const label = getControlLabel(control);
      pulseControl(control);
      setStatus(label, "busy", "Sending emergency stop " + label + ".", {{ hideAfterMs: null }});

      try {{
        await postPress({{ key: control.dataset.key }});

        if (navigator.vibrate) {{
          navigator.vibrate([12, 20, 12, 20, 12]);
        }}

        setStatus(label, "ok", "Sent emergency stop " + label + ".", {{ hideAfterMs: 850 }});
      }} catch (error) {{
        const message = error && error.message ? error.message : "Request failed";
        setStatus("ERR", "error", "Error sending emergency stop " + label + ": " + message, {{
          hideAfterMs: 2600
        }});
      }}
    }}

    async function sendComboControls(controlSequence) {{
      const statusText = getSequenceLabel(controlSequence);
      const announceText = getSequenceAnnouncement(controlSequence);
      for (const control of controlSequence) {{
        pulseControl(control);
      }}
      setStatus(statusText, "busy", "Sending " + announceText + ".", {{ hideAfterMs: null }});

      try {{
        await postPress({{
          keys: controlSequence.map((control) => control.dataset.key)
        }});

        if (navigator.vibrate) {{
          navigator.vibrate([12, 32, 12]);
        }}

        setStatus(statusText, "ok", "Sent " + announceText + ".", {{ hideAfterMs: 850 }});
      }} catch (error) {{
        const message = error && error.message ? error.message : "Request failed";
        setStatus("ERR", "error", "Error sending " + announceText + ": " + message, {{
          hideAfterMs: 2600
        }});
      }}
    }}

    async function flushPendingSequence() {{
      const controlSequence = pendingControls.slice();
      if (!controlSequence.length) {{
        return;
      }}
      clearPendingControls();
      if (controlSequence.length === 1) {{
        await sendSingleControl(controlSequence[0]);
        return;
      }}
      await sendComboControls(controlSequence);
    }}

    async function handleControlClick(control) {{
      const isSecondaryModifier = control.dataset.isSecondaryModifier === "true";
      const key = control.dataset.key;
      clearGuideTapState();

      if (key === emergencyStopKey) {{
        clearPendingControls();
        clearSecondary();
        await sendEmergencyStopControl(control);
        return;
      }}

      if (isSecondaryModifier) {{
        if (pendingControls.length) {{
          await flushPendingSequence();
        }}
        pulseControl(control);
        toggleSecondary();
        return;
      }}

      if (pendingControls.length) {{
        if (pendingControls.includes(control)) {{
          await flushPendingSequence();
          await handleControlClick(control);
          return;
        }}
        addPendingControl(control);
        return;
      }}

      if (secondaryArmed) {{
        await sendSingleControl(control);
        return;
      }}

      addPendingControl(control);
    }}

    syncSecondaryControl();
    if (guideTrigger) {{
      guideTrigger.addEventListener("click", () => {{
        handleGuideTriggerClick();
      }});
    }}
    if (guideCloseButton) {{
      guideCloseButton.addEventListener("click", () => {{
        closeGuide();
      }});
    }}
    document.addEventListener("keydown", (event) => {{
      if (event.key === "Escape") {{
        closeGuide();
      }}
    }});
    for (const control of controls) {{
      control.addEventListener("click", () => {{
        void handleControlClick(control);
      }});
    }}
  </script>
</body>
</html>
"""


class MobileTyperWindow:
    def __init__(
        self,
        server: MobileTyperHTTPServer,
        *,
        log_handler: Optional[GuiLogHandler] = None,
    ) -> None:
        import tkinter as tk

        self._tk = tk
        self._server = server
        self._log_handler = log_handler
        self._root = tk.Tk()
        self._root.title(DESKTOP_APP_TITLE)
        self._root.configure(bg=WINDOW_BG)
        self._root.protocol("WM_DELETE_WINDOW", self._handle_close)
        self._root.minsize(430, 860)

        self._primary_url = server.state.urls[0] if server.state.urls else "http://localhost"
        self._status_var: Optional[object] = None
        self._url_var: Optional[object] = None
        self._port_notice_var: Optional[object] = None
        self._qr_canvas: Optional[object] = None
        self._urls_frame: Optional[object] = None
        self._autostart_var: Optional[object] = None
        self._log_text: Optional[object] = None
        self._log_refresh_job: Optional[object] = None
        self._last_log_snapshot: Tuple[str, ...] = ()
        self._build_ui()
        self._schedule_log_refresh()

    def run(self) -> None:
        self._root.mainloop()

    def _build_ui(self) -> None:
        tk = self._tk

        outer = tk.Frame(self._root, bg=WINDOW_BG, padx=20, pady=20)
        outer.pack(fill="both", expand=True)

        panel = tk.Frame(
            outer,
            bg=PANEL_BG,
            highlightbackground="#cbd5e1",
            highlightthickness=1,
            bd=0,
            padx=22,
            pady=22,
        )
        panel.pack(fill="both", expand=True)

        title = tk.Label(
            panel,
            text=DESKTOP_APP_TITLE,
            font=("Segoe UI", 22, "bold"),
            bg=PANEL_BG,
            fg=TEXT_COLOR,
        )
        title.pack(anchor="w")

        subtitle = tk.Label(
            panel,
            text="Scan the QR code on your phone, then keep the target app focused on this computer.",
            font=("Segoe UI", 10),
            bg=PANEL_BG,
            fg=MUTED_TEXT,
            justify="left",
            wraplength=360,
        )
        subtitle.pack(anchor="w", pady=(6, 14))

        if self._server.state.port_notice:
            self._port_notice_var = tk.StringVar(value=self._server.state.port_notice)
            port_notice = tk.Label(
                panel,
                textvariable=self._port_notice_var,
                font=("Segoe UI", 9, "bold"),
                bg=PORT_WARNING_BG,
                fg=PORT_WARNING,
                justify="left",
                wraplength=360,
                padx=10,
                pady=8,
            )
            port_notice.pack(fill="x", pady=(0, 14))

        qr_frame = tk.Frame(panel, bg="#f8fafc", padx=14, pady=14)
        qr_frame.pack(anchor="center", pady=(0, 14))

        qr_canvas = tk.Canvas(
            qr_frame,
            width=300,
            height=300,
            bg="#ffffff",
            highlightthickness=0,
            bd=0,
        )
        qr_canvas.pack()
        self._qr_canvas = qr_canvas
        self._draw_qr(qr_canvas, self._primary_url)

        backend = tk.Label(
            panel,
            text=f"Backend: {self._server.state.key_sender.backend_name}",
            font=("Segoe UI", 10, "bold"),
            bg=PANEL_BG,
            fg=TEXT_COLOR,
        )
        backend.pack(anchor="w")

        self._status_var = tk.StringVar(
            value="Server is running. Use the remote from your phone."
        )
        status = tk.Label(
            panel,
            textvariable=self._status_var,
            font=("Segoe UI", 10),
            bg=PANEL_BG,
            fg=MUTED_TEXT,
            justify="left",
            wraplength=360,
        )
        status.pack(anchor="w", pady=(4, 14))

        primary_label = tk.Label(
            panel,
            text="Primary phone URL",
            font=("Segoe UI", 9, "bold"),
            bg=PANEL_BG,
            fg=TEXT_COLOR,
        )
        primary_label.pack(anchor="w")

        self._url_var = tk.StringVar(value=self._primary_url)
        url_entry = tk.Entry(
            panel,
            textvariable=self._url_var,
            font=("Consolas", 11),
            bd=0,
            relief="flat",
            readonlybackground="#f8fafc",
            fg=ACCENT,
            justify="left",
        )
        url_entry.configure(state="readonly")
        url_entry.pack(fill="x", pady=(6, 8), ipady=10)

        button_row = tk.Frame(panel, bg=PANEL_BG)
        button_row.pack(fill="x", pady=(0, 14))

        copy_button = tk.Button(
            button_row,
            text="Copy URL",
            font=("Segoe UI", 10, "bold"),
            bg=ACCENT,
            fg="#ffffff",
            activebackground="#1e40af",
            activeforeground="#ffffff",
            relief="flat",
            padx=14,
            pady=10,
            command=self._copy_primary_url,
        )
        copy_button.pack(side="left")

        refresh_button = tk.Button(
            button_row,
            text="Refresh Network",
            font=("Segoe UI", 10),
            bg="#dbeafe",
            fg=TEXT_COLOR,
            activebackground="#bfdbfe",
            activeforeground=TEXT_COLOR,
            relief="flat",
            padx=14,
            pady=10,
            command=self._refresh_network,
        )
        refresh_button.pack(side="left", padx=(8, 0))

        close_button = tk.Button(
            button_row,
            text="Stop Server",
            font=("Segoe UI", 10),
            bg="#e2e8f0",
            fg=TEXT_COLOR,
            activebackground="#cbd5e1",
            activeforeground=TEXT_COLOR,
            relief="flat",
            padx=14,
            pady=10,
            command=self._handle_close,
        )
        close_button.pack(side="right")

        if supports_windows_autostart():
            self._autostart_var = tk.BooleanVar(value=is_windows_autostart_enabled())
            autostart_toggle = tk.Checkbutton(
                panel,
                text="Start with Windows",
                variable=self._autostart_var,
                command=self._toggle_autostart,
                bg=PANEL_BG,
                fg=TEXT_COLOR,
                activebackground=PANEL_BG,
                activeforeground=TEXT_COLOR,
                selectcolor="#dbeafe",
                font=("Segoe UI", 10),
            )
            autostart_toggle.pack(anchor="w", pady=(0, 14))

        urls_title = tk.Label(
            panel,
            text="All detected local URLs",
            font=("Segoe UI", 9, "bold"),
            bg=PANEL_BG,
            fg=TEXT_COLOR,
        )
        urls_title.pack(anchor="w")

        urls_frame = tk.Frame(panel, bg="#f8fafc", padx=12, pady=10)
        urls_frame.pack(fill="x", pady=(6, 0))
        self._urls_frame = urls_frame
        self._render_url_labels()

        firewall_note = tk.Label(
            panel,
            text="If your phone cannot connect, keep both devices on the same Wi-Fi and allow the app through Windows Firewall.",
            font=("Segoe UI", 9),
            bg=PANEL_BG,
            fg=MUTED_TEXT,
            justify="left",
            wraplength=360,
        )
        firewall_note.pack(anchor="w", pady=(14, 0))

        if self._log_handler is not None:
            log_header = tk.Frame(panel, bg=PANEL_BG)
            log_header.pack(fill="x", pady=(14, 0))

            log_title = tk.Label(
                log_header,
                text="Backend log",
                font=("Segoe UI", 9, "bold"),
                bg=PANEL_BG,
                fg=TEXT_COLOR,
            )
            log_title.pack(side="left")

            clear_logs_button = tk.Button(
                log_header,
                text="Clear",
                font=("Segoe UI", 9),
                bg="#e2e8f0",
                fg=TEXT_COLOR,
                activebackground="#cbd5e1",
                activeforeground=TEXT_COLOR,
                relief="flat",
                padx=10,
                pady=6,
                command=self._clear_logs,
            )
            clear_logs_button.pack(side="right")

            copy_logs_button = tk.Button(
                log_header,
                text="Copy Logs",
                font=("Segoe UI", 9, "bold"),
                bg="#dbeafe",
                fg=TEXT_COLOR,
                activebackground="#bfdbfe",
                activeforeground=TEXT_COLOR,
                relief="flat",
                padx=10,
                pady=6,
                command=self._copy_logs,
            )
            copy_logs_button.pack(side="right", padx=(0, 8))

            log_note = tk.Label(
                panel,
                text="Recent send activity and backend errors appear here.",
                font=("Segoe UI", 9),
                bg=PANEL_BG,
                fg=MUTED_TEXT,
                justify="left",
                wraplength=360,
            )
            log_note.pack(anchor="w", pady=(6, 0))

            log_frame = tk.Frame(panel, bg="#0f172a")
            log_frame.pack(fill="both", expand=True, pady=(6, 0))

            log_scrollbar = tk.Scrollbar(log_frame)
            log_scrollbar.pack(side="right", fill="y")

            log_text = tk.Text(
                log_frame,
                height=10,
                font=("Consolas", 9),
                bg="#0f172a",
                fg="#e2e8f0",
                insertbackground="#e2e8f0",
                relief="flat",
                bd=0,
                wrap="word",
                yscrollcommand=log_scrollbar.set,
                padx=10,
                pady=10,
            )
            log_text.pack(fill="both", expand=True)
            log_scrollbar.configure(command=log_text.yview)
            log_text.configure(state="disabled")
            self._log_text = log_text
            self._refresh_log_view(force=True)

    def _render_url_labels(self) -> None:
        if self._urls_frame is None:
            return

        tk = self._tk
        for child in self._urls_frame.winfo_children():
            child.destroy()

        for url in self._server.state.urls:
            label = tk.Label(
                self._urls_frame,
                text=url,
                font=("Consolas", 10),
                bg="#f8fafc",
                fg=TEXT_COLOR,
                anchor="w",
                justify="left",
            )
            label.pack(anchor="w")

    def _draw_qr(self, canvas: object, data: str) -> None:
        matrix = build_qr_matrix(data)
        if matrix is None:
            canvas.create_text(
                150,
                150,
                text="QR code dependency is missing.",
                width=240,
                fill=TEXT_COLOR,
                font=("Segoe UI", 12),
            )
            return

        size = min(int(canvas["width"]), int(canvas["height"]))
        modules = len(matrix)
        cell = max(1, size // modules)
        offset = (size - (modules * cell)) // 2

        canvas.delete("all")
        canvas.create_rectangle(0, 0, size, size, fill="#ffffff", outline="")
        for row_index, row in enumerate(matrix):
            for col_index, cell_enabled in enumerate(row):
                if not cell_enabled:
                    continue
                x0 = offset + (col_index * cell)
                y0 = offset + (row_index * cell)
                x1 = x0 + cell
                y1 = y0 + cell
                canvas.create_rectangle(x0, y0, x1, y1, fill="#000000", outline="")

    def _copy_primary_url(self) -> None:
        self._root.clipboard_clear()
        self._root.clipboard_append(self._primary_url)
        self._root.update_idletasks()
        if self._status_var is not None:
            self._status_var.set("Primary URL copied to the clipboard.")

    def _copy_logs(self) -> None:
        if self._log_handler is None:
            return

        log_text = "\n".join(self._log_handler.snapshot()) or "No backend logs yet."
        self._root.clipboard_clear()
        self._root.clipboard_append(log_text)
        self._root.update_idletasks()
        if self._status_var is not None:
            self._status_var.set("Backend log copied to the clipboard.")

    def _clear_logs(self) -> None:
        if self._log_handler is None:
            return

        self._log_handler.clear()
        self._refresh_log_view(force=True)
        if self._status_var is not None:
            self._status_var.set("Backend log cleared.")

    def _refresh_network(self) -> None:
        from .server import refresh_server_urls

        refresh_server_urls(self._server)
        self._primary_url = (
            self._server.state.urls[0] if self._server.state.urls else "http://localhost"
        )
        if self._url_var is not None:
            self._url_var.set(self._primary_url)
        if self._qr_canvas is not None:
            self._draw_qr(self._qr_canvas, self._primary_url)
        self._render_url_labels()
        if self._status_var is not None:
            self._status_var.set(
                f"Network details refreshed. Current port: {self._server.state.actual_port}."
            )

    def _schedule_log_refresh(self) -> None:
        if self._log_handler is None:
            return

        self._refresh_log_view()
        self._log_refresh_job = self._root.after(300, self._schedule_log_refresh)

    def _refresh_log_view(self, *, force: bool = False) -> None:
        if self._log_handler is None or self._log_text is None:
            return

        snapshot = self._log_handler.snapshot()
        if not force and snapshot == self._last_log_snapshot:
            return

        self._last_log_snapshot = snapshot
        body = "\n".join(snapshot) if snapshot else "Waiting for backend log output..."

        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.insert("1.0", body)
        self._log_text.configure(state="disabled")
        self._log_text.see("end")

    def _toggle_autostart(self) -> None:
        if self._autostart_var is None:
            return

        enabled = bool(self._autostart_var.get())
        try:
            set_windows_autostart(enabled)
        except Exception as exc:
            self._autostart_var.set(not enabled)
            show_error_dialog(f"Could not change Start with Windows: {exc}")
            return

        if self._status_var is not None:
            if enabled:
                self._status_var.set(
                    "Mobile Remote will start automatically when you log in."
                )
            else:
                self._status_var.set("Start with Windows has been disabled.")

    def _handle_close(self) -> None:
        if self._log_refresh_job is not None:
            try:
                self._root.after_cancel(self._log_refresh_job)
            except Exception:
                pass
            self._log_refresh_job = None
        self._root.destroy()


def print_banner(server: MobileTyperHTTPServer) -> None:
    print()
    print(f"{DESKTOP_APP_TITLE} is running.")
    print(f"Backend: {server.state.key_sender.backend_name}")

    if server.state.urls:
        qr_url = server.state.urls[0]
        qr_art = render_terminal_qr(qr_url)
        if qr_art:
            print("Scan this QR code on your phone:")
            print(f"  {qr_url}")
            print()
            print(qr_art)
            print()
        else:
            print("QR code output is unavailable because the qrcode dependency is missing.")
            print(f"Primary URL: {qr_url}")

    if server.state.port_notice:
        print(server.state.port_notice)
        print()

    print("Open this URL on your phone:")
    for url in server.state.urls:
        print(f"  {url}")
    print()
    print("Keep the target app focused on this computer.")
    print("Press Ctrl+C to stop.")
    print()


__all__ = [
    "DESKTOP_APP_TITLE",
    "GuiLogHandler",
    "render_terminal_qr",
    "build_qr_matrix",
    "is_stdout_console_available",
    "show_error_dialog",
    "get_windows_autostart_command",
    "supports_windows_autostart",
    "is_windows_autostart_enabled",
    "set_windows_autostart",
    "render_page",
    "MobileTyperWindow",
    "print_banner",
]
