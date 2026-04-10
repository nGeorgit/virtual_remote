from __future__ import annotations

import argparse
import logging
import socket
import threading

from .constants import (
    ACCENT,
    ALLOWED_KEYS,
    COMBO_WINDOW_MS,
    EMERGENCY_STOP_KEY,
    LOGGER,
    MUTED_TEXT,
    PANEL_BG,
    PORT_IN_USE_ERRNOS,
    PORT_WARNING,
    PORT_WARNING_BG,
    TEXT_COLOR,
    WINDOW_BG,
)
from .key_sender import (
    DryRunKeySender,
    KeySender,
    KeypressError,
    LinuxX11KeySender,
    MacOsKeySender,
    UnsupportedPlatformError,
    WindowsKeySender,
    WindowsSendInput,
    WindowsSendInputKeyboard,
    WindowsSendInputUnion,
    XDoToolKeySender,
    select_key_sender,
)
from .network import discover_urls, fallback_ports, is_port_in_use_error
from .server import (
    AppState,
    MobileTyperHTTPServer,
    MobileTyperHandler,
    create_server,
    refresh_server_urls,
)
from .ui import (
    GuiLogHandler,
    MobileTyperWindow,
    build_qr_matrix,
    get_windows_autostart_command,
    is_stdout_console_available,
    is_windows_autostart_enabled,
    print_banner,
    render_page,
    render_terminal_qr,
    set_windows_autostart,
    show_error_dialog,
    supports_windows_autostart,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Serve a local webpage and API that send remote keypresses to this computer."
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Bind host. Use 0.0.0.0 to allow other devices on the same Wi-Fi.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to listen on.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Serve the API and page without sending real keypresses.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose request logging.",
    )
    parser.add_argument(
        "--no-gui",
        action="store_true",
        help="Run without the desktop QR window and print startup details to the console instead.",
    )
    parser.add_argument(
        "--strict-port",
        action="store_true",
        help="Fail instead of automatically switching to another free port when the requested port is busy.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="[%(levelname)s] %(message)s",
    )
    root_handler_level = logging.INFO if args.verbose else logging.WARNING
    for handler in logging.getLogger().handlers:
        handler.setLevel(root_handler_level)

    gui_log_handler: GuiLogHandler | None = None
    if not args.no_gui:
        LOGGER.setLevel(logging.INFO)
        gui_log_handler = GuiLogHandler()
        gui_log_handler.setFormatter(
            logging.Formatter("[%(levelname)s] %(message)s")
        )
        LOGGER.addHandler(gui_log_handler)

    try:
        key_sender = select_key_sender(dry_run=args.dry_run)
    except UnsupportedPlatformError as exc:
        show_error_dialog(f"Could not start a keypress backend: {exc}")
        return 1

    try:
        server = create_server(
            args.host,
            args.port,
            key_sender,
            strict_port=args.strict_port,
        )
    except OSError as exc:
        key_sender.close()
        show_error_dialog(f"Could not start the server: {exc}")
        return 1

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        if args.no_gui:
            print_banner(server)
            server_thread.join()
        else:
            app_window = MobileTyperWindow(server, log_handler=gui_log_handler)
            if is_stdout_console_available():
                print_banner(server)
            app_window.run()
    except KeyboardInterrupt:
        if is_stdout_console_available():
            print()
            print("Stopping server.")
    except Exception as exc:
        show_error_dialog(f"Mobile Typer failed to start its window: {exc}")
        return 1
    finally:
        server.shutdown()
        server.server_close()
        key_sender.close()
        server_thread.join(timeout=2)
        if gui_log_handler is not None:
            LOGGER.removeHandler(gui_log_handler)

    return 0


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
    "discover_urls",
    "is_port_in_use_error",
    "fallback_ports",
    "render_terminal_qr",
    "build_qr_matrix",
    "is_stdout_console_available",
    "show_error_dialog",
    "get_windows_autostart_command",
    "supports_windows_autostart",
    "is_windows_autostart_enabled",
    "set_windows_autostart",
    "render_page",
    "AppState",
    "MobileTyperHTTPServer",
    "MobileTyperWindow",
    "MobileTyperHandler",
    "create_server",
    "refresh_server_urls",
    "parse_args",
    "print_banner",
    "main",
]
