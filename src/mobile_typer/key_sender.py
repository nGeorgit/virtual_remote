from __future__ import annotations

import ctypes
import ctypes.util
import os
import platform
import shutil
import subprocess
import threading
from collections.abc import Sequence
from typing import List, Optional, Protocol, Tuple

from .constants import LOGGER


WindowsWord = ctypes.c_uint16
WindowsDword = ctypes.c_uint32
WindowsLong = ctypes.c_int32
WindowsUlongPtr = ctypes.c_size_t


class WindowsSendInputKeyboard(ctypes.Structure):
    _fields_ = [
        ("wVk", WindowsWord),
        ("wScan", WindowsWord),
        ("dwFlags", WindowsDword),
        ("time", WindowsDword),
        ("dwExtraInfo", WindowsUlongPtr),
    ]


class WindowsSendInputMouse(ctypes.Structure):
    _fields_ = [
        ("dx", WindowsLong),
        ("dy", WindowsLong),
        ("mouseData", WindowsDword),
        ("dwFlags", WindowsDword),
        ("time", WindowsDword),
        ("dwExtraInfo", WindowsUlongPtr),
    ]


class WindowsSendInputHardware(ctypes.Structure):
    _fields_ = [
        ("uMsg", WindowsDword),
        ("wParamL", WindowsWord),
        ("wParamH", WindowsWord),
    ]


class WindowsSendInputUnion(ctypes.Union):
    _fields_ = [
        ("mi", WindowsSendInputMouse),
        ("ki", WindowsSendInputKeyboard),
        ("hi", WindowsSendInputHardware),
    ]


class WindowsSendInput(ctypes.Structure):
    _anonymous_ = ("union",)
    _fields_ = [
        ("type", WindowsDword),
        ("union", WindowsSendInputUnion),
    ]


class KeypressError(RuntimeError):
    """Raised when a backend cannot inject a keypress."""


class UnsupportedPlatformError(RuntimeError):
    """Raised when no usable backend exists for the current platform."""


def _coerce_combo_keys(keys: Sequence[str]) -> Tuple[str, ...]:
    key_sequence = tuple(keys)
    if not key_sequence:
        raise KeypressError("Combo press requires at least one key.")
    return key_sequence


class KeySender(Protocol):
    backend_name: str

    def press(self, key: str) -> None:
        ...

    def press_combo(self, keys: Sequence[str]) -> None:
        ...

    def press_chord(self, modifier: str, key: str) -> None:
        ...

    def close(self) -> None:
        ...


class DryRunKeySender:
    backend_name = "dry-run"

    def press(self, key: str) -> None:
        LOGGER.info("dry-run keypress for %s", key)

    def press_combo(self, keys: Sequence[str]) -> None:
        key_sequence = _coerce_combo_keys(keys)
        LOGGER.info("dry-run key combo for %s", " + ".join(key_sequence))

    def press_chord(self, modifier: str, key: str) -> None:
        LOGGER.info("dry-run key chord for %s + %s", modifier, key)

    def close(self) -> None:
        return None


class LinuxX11KeySender:
    backend_name = "linux-x11-xtest"

    def __init__(self) -> None:
        display_name = os.environ.get("DISPLAY")
        if not display_name:
            raise UnsupportedPlatformError(
                "DISPLAY is not set. Start this from an X11 desktop session."
            )

        x11_path = ctypes.util.find_library("X11")
        xtst_path = ctypes.util.find_library("Xtst")
        if not x11_path or not xtst_path:
            raise UnsupportedPlatformError(
                "Missing X11/XTest libraries. Install libx11 and libxtst."
            )

        self._x11 = ctypes.CDLL(x11_path)
        self._xtst = ctypes.CDLL(xtst_path)
        self._lock = threading.Lock()

        self._x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self._x11.XOpenDisplay.restype = ctypes.c_void_p
        self._x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        self._x11.XCloseDisplay.restype = ctypes.c_int
        self._x11.XStringToKeysym.argtypes = [ctypes.c_char_p]
        self._x11.XStringToKeysym.restype = ctypes.c_ulong
        self._x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        self._x11.XKeysymToKeycode.restype = ctypes.c_uint
        self._x11.XFlush.argtypes = [ctypes.c_void_p]
        self._x11.XFlush.restype = ctypes.c_int

        self._xtst.XTestFakeKeyEvent.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_int,
            ctypes.c_ulong,
        ]
        self._xtst.XTestFakeKeyEvent.restype = ctypes.c_int

        self._display = self._x11.XOpenDisplay(None)
        if not self._display:
            raise UnsupportedPlatformError(
                f"Could not open the X11 display {display_name!r}."
            )

    def _resolve_keycode(self, key: str) -> int:
        keysym = self._x11.XStringToKeysym(key.encode("utf-8"))
        if keysym == 0:
            raise KeypressError(f"Could not resolve keysym for {key!r}.")

        keycode = self._x11.XKeysymToKeycode(self._display, keysym)
        if keycode == 0:
            raise KeypressError(f"Could not resolve keycode for {key!r}.")
        return keycode

    def _send_key_event(self, keycode: int, is_press: bool) -> None:
        if self._xtst.XTestFakeKeyEvent(self._display, keycode, int(is_press), 0) == 0:
            action = "press" if is_press else "release"
            raise KeypressError(f"Failed to {action} keycode {keycode}.")

    def _send_combo_keycodes(self, keycodes: Sequence[int]) -> None:
        with self._lock:
            for keycode in keycodes:
                self._send_key_event(keycode, True)
            for keycode in reversed(keycodes):
                self._send_key_event(keycode, False)
            self._x11.XFlush(self._display)

    def press(self, key: str) -> None:
        self.press_combo((key,))

    def press_combo(self, keys: Sequence[str]) -> None:
        key_sequence = _coerce_combo_keys(keys)
        keycodes = tuple(self._resolve_keycode(key) for key in key_sequence)
        self._send_combo_keycodes(keycodes)

    def press_chord(self, modifier: str, key: str) -> None:
        self.press_combo((modifier, key))

    def close(self) -> None:
        if self._display:
            self._x11.XCloseDisplay(self._display)
            self._display = None


class XDoToolKeySender:
    backend_name = "xdotool"

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def _run_xdotool(self, *args: str) -> None:
        try:
            subprocess.run(
                ["xdotool", *args],
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise UnsupportedPlatformError("xdotool is not installed.") from exc
        except subprocess.CalledProcessError as exc:
            details = " ".join(args)
            raise KeypressError(
                exc.stderr.strip() or f"xdotool failed for {details!r}."
            ) from exc

    def press(self, key: str) -> None:
        self.press_combo((key,))

    def press_combo(self, keys: Sequence[str]) -> None:
        key_sequence = _coerce_combo_keys(keys)
        pressed_count = 0
        released_count = 0
        with self._lock:
            try:
                for index, key in enumerate(key_sequence):
                    if index == 0:
                        self._run_xdotool("keydown", "--clearmodifiers", key)
                    else:
                        self._run_xdotool("keydown", key)
                    pressed_count += 1
                for key in reversed(key_sequence):
                    self._run_xdotool("keyup", key)
                    released_count += 1
            except (KeypressError, UnsupportedPlatformError):
                remaining_keys = key_sequence[: pressed_count - released_count]
                for key in reversed(remaining_keys):
                    try:
                        self._run_xdotool("keyup", key)
                    except (KeypressError, UnsupportedPlatformError):
                        pass
                raise

    def press_chord(self, modifier: str, key: str) -> None:
        self.press_combo((modifier, key))

    def close(self) -> None:
        return None


class MacOsKeySender:
    backend_name = "osascript"

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def _send_keystroke(self, key: str) -> None:
        script = f'tell application "System Events" to keystroke "{key}"'
        try:
            subprocess.run(
                ["osascript", "-e", script],
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise UnsupportedPlatformError("osascript is not available.") from exc
        except subprocess.CalledProcessError as exc:
            raise KeypressError(
                exc.stderr.strip() or f"osascript failed for {key!r}."
            ) from exc

    def press(self, key: str) -> None:
        self.press_combo((key,))

    def press_combo(self, keys: Sequence[str]) -> None:
        key_sequence = _coerce_combo_keys(keys)
        with self._lock:
            for key in key_sequence:
                self._send_keystroke(key)

    def press_chord(self, modifier: str, key: str) -> None:
        # System Events can reliably chord modifier keys like Shift, but not
        # arbitrary letter keys. Fall back to the sequential behavior on macOS.
        self.press_combo((modifier, key))

    def close(self) -> None:
        return None


class WindowsKeySender:
    backend_name = "win32-sendinput"
    INPUT_KEYBOARD = 1
    KEYEVENTF_KEYUP = 0x0002

    def __init__(self) -> None:
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._lock = threading.Lock()
        self._user32.SendInput.argtypes = [
            ctypes.c_uint,
            ctypes.POINTER(WindowsSendInput),
            ctypes.c_int,
        ]
        self._user32.SendInput.restype = ctypes.c_uint
        self._user32.MapVirtualKeyW.argtypes = [ctypes.c_uint, ctypes.c_uint]
        self._user32.MapVirtualKeyW.restype = ctypes.c_uint
        self._user32.VkKeyScanW.argtypes = [ctypes.c_wchar]
        self._user32.VkKeyScanW.restype = ctypes.c_short
        self._user32.GetForegroundWindow.argtypes = []
        self._user32.GetForegroundWindow.restype = ctypes.c_void_p
        self._user32.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
        self._user32.GetWindowTextLengthW.restype = ctypes.c_int
        self._user32.GetWindowTextW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_wchar_p,
            ctypes.c_int,
        ]
        self._user32.GetWindowTextW.restype = ctypes.c_int

    def _resolve_virtual_key(self, key: str) -> int:
        virtual_key = int(self._user32.VkKeyScanW(key))
        if virtual_key == -1:
            raise KeypressError(f"Could not resolve virtual key for {key!r}.")
        return virtual_key & 0xFF

    def _build_key_input(self, key: str, *, is_keyup: bool = False) -> WindowsSendInput:
        virtual_key = self._resolve_virtual_key(key)
        scan_code = int(self._user32.MapVirtualKeyW(virtual_key, 0))
        flags = self.KEYEVENTF_KEYUP if is_keyup else 0
        return WindowsSendInput(
            type=self.INPUT_KEYBOARD,
            ki=WindowsSendInputKeyboard(
                wVk=virtual_key,
                wScan=scan_code,
                dwFlags=flags,
                time=0,
                dwExtraInfo=0,
            ),
        )

    def _describe_foreground_window(self) -> Optional[str]:
        handle = self._user32.GetForegroundWindow()
        if not handle:
            return None

        handle_value = int(handle)
        title_length = int(self._user32.GetWindowTextLengthW(handle))
        if title_length <= 0:
            return f"handle 0x{handle_value:X}"

        title_buffer = ctypes.create_unicode_buffer(title_length + 1)
        copied = int(
            self._user32.GetWindowTextW(handle, title_buffer, len(title_buffer))
        )
        if copied <= 0:
            return f"handle 0x{handle_value:X}"

        return f"{title_buffer.value!r} (handle 0x{handle_value:X})"

    def _send_inputs(self, *inputs: WindowsSendInput) -> None:
        sequence = (WindowsSendInput * len(inputs))(*inputs)
        sent = self._user32.SendInput(
            len(inputs),
            sequence,
            ctypes.sizeof(WindowsSendInput),
        )
        if sent != len(inputs):
            error = ctypes.get_last_error()
            message_parts = [f"SendInput failed with error code {error}."]
            foreground_window = self._describe_foreground_window()
            if foreground_window:
                message_parts.append(f"Foreground window: {foreground_window}.")
            if error in {0, 5}:
                message_parts.append(
                    "Windows often returns this when the target app is running as "
                    "Administrator or otherwise blocking injected input."
                )
            raise KeypressError(" ".join(message_parts))

    def press(self, key: str) -> None:
        self.press_combo((key,))

    def press_combo(self, keys: Sequence[str]) -> None:
        key_sequence = _coerce_combo_keys(keys)
        inputs: List[WindowsSendInput] = []
        for key in key_sequence:
            inputs.append(self._build_key_input(key))
        for key in reversed(key_sequence):
            inputs.append(self._build_key_input(key, is_keyup=True))
        with self._lock:
            self._send_inputs(*inputs)

    def press_chord(self, modifier: str, key: str) -> None:
        self.press_combo((modifier, key))

    def close(self) -> None:
        return None


def select_key_sender(*, dry_run: bool = False) -> KeySender:
    if dry_run:
        return DryRunKeySender()

    system = platform.system()
    if system == "Linux":
        backend_errors: List[str] = []
        try:
            return LinuxX11KeySender()
        except UnsupportedPlatformError as exc:
            backend_errors.append(str(exc))

        if shutil.which("xdotool"):
            return XDoToolKeySender()

        details = " ".join(backend_errors).strip()
        raise UnsupportedPlatformError(
            "No usable Linux keypress backend found. "
            f"{details} Install xdotool or run this in an X11 session."
        )

    if system == "Darwin":
        return MacOsKeySender()

    if system == "Windows":
        return WindowsKeySender()

    raise UnsupportedPlatformError(f"Unsupported operating system: {system}.")


__all__ = [
    "WindowsSendInputKeyboard",
    "WindowsSendInputUnion",
    "WindowsSendInput",
    "KeypressError",
    "UnsupportedPlatformError",
    "KeySender",
    "DryRunKeySender",
    "LinuxX11KeySender",
    "XDoToolKeySender",
    "MacOsKeySender",
    "WindowsKeySender",
    "select_key_sender",
]
