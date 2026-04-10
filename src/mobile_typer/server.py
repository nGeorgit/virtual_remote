from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .constants import ALLOWED_KEYS, EMERGENCY_STOP_KEY, LOGGER
from .key_sender import KeySender, KeypressError, UnsupportedPlatformError
from .network import discover_urls, fallback_ports, is_port_in_use_error
from .ui import render_page


@dataclass(slots=True)
class AppState:
    key_sender: KeySender
    allowed_keys: tuple[str, ...] = ALLOWED_KEYS
    secondary_modifier: str = "e"
    urls: list[str] = field(default_factory=list)
    requested_host: str = "0.0.0.0"
    requested_port: int = 8000
    actual_port: int = 8000
    port_notice: str | None = None


@dataclass(frozen=True, slots=True)
class PressRequest:
    key: str | None = None
    keys: tuple[str, ...] = ()
    use_secondary: bool = False

    @property
    def is_combo(self) -> bool:
        return bool(self.keys)

    @property
    def has_emergency_stop(self) -> bool:
        return self.key == EMERGENCY_STOP_KEY or EMERGENCY_STOP_KEY in self.keys


def _allowed_keys_error(allowed_keys: tuple[str, ...]) -> str:
    return f"Only these keys are allowed: {', '.join(allowed_keys)}."


def _iter_manual_pdf_paths() -> tuple[Path, ...]:
    candidates: list[Path] = []

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "manual.pdf")

    candidates.append(Path(__file__).resolve().parents[2] / "manual.pdf")
    candidates.append(Path(sys.executable).resolve().parent / "manual.pdf")
    return tuple(candidates)


def _find_manual_pdf() -> Path | None:
    for candidate in _iter_manual_pdf_paths():
        if candidate.is_file():
            return candidate
    return None


def _parse_press_request(
    payload: object, allowed_keys: tuple[str, ...]
) -> tuple[PressRequest | None, str | None]:
    if not isinstance(payload, dict):
        return None, "Body must be a JSON object."

    has_key = "key" in payload
    has_keys = "keys" in payload
    if has_key and has_keys:
        return None, "Provide either 'key' or 'keys', not both."

    if has_keys:
        if "use_secondary" in payload:
            return None, "'use_secondary' is only valid for single key presses."

        raw_keys = payload.get("keys")
        if not isinstance(raw_keys, list):
            return None, "'keys' must be an array of allowed keys."

        keys = tuple(str(value).lower() for value in raw_keys)
        if EMERGENCY_STOP_KEY in keys:
            return PressRequest(keys=keys), None
        if len(keys) < 2:
            return None, "Combo presses require at least two keys."
        if len(set(keys)) != len(keys):
            return None, "Combo presses require distinct keys."
        if any(key not in allowed_keys for key in keys):
            return None, _allowed_keys_error(allowed_keys)

        return PressRequest(keys=keys), None

    key = str(payload.get("key", "")).lower()
    if key not in allowed_keys:
        return None, _allowed_keys_error(allowed_keys)

    return PressRequest(
        key=key,
        use_secondary=bool(payload.get("use_secondary", False)),
    ), None


class MobileTyperHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address: tuple[str, int], state: AppState) -> None:
        super().__init__(server_address, MobileTyperHandler)
        self.state = state


class MobileTyperHandler(BaseHTTPRequestHandler):
    server: MobileTyperHTTPServer

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            page = render_page(
                self.server.state.allowed_keys,
                self.server.state.urls,
                self.server.state.key_sender.backend_name,
            )
            self._send_response(
                HTTPStatus.OK,
                page.encode("utf-8"),
                content_type="text/html; charset=utf-8",
            )
            return

        if parsed.path == "/manual.pdf":
            manual_path = _find_manual_pdf()
            if manual_path is None:
                self._send_response(
                    HTTPStatus.NOT_FOUND,
                    b"Manual PDF not found.",
                    content_type="text/plain; charset=utf-8",
                )
                return

            try:
                body = manual_path.read_bytes()
            except OSError:
                self._send_response(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    b"Could not read manual PDF.",
                    content_type="text/plain; charset=utf-8",
                )
                return

            self._send_response(
                HTTPStatus.OK,
                body,
                content_type="application/pdf",
                headers={"Content-Disposition": 'inline; filename="manual.pdf"'},
            )
            return

        if parsed.path == "/api/health":
            self._send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "backend": self.server.state.key_sender.backend_name,
                    "allowed_keys": list(self.server.state.allowed_keys),
                },
            )
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Not found."})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/press":
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Not found."})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "Invalid Content-Length header."},
            )
            return

        raw_body = self.rfile.read(content_length) if content_length else b"{}"
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "Body must be valid JSON."},
            )
            return

        press_request, error = _parse_press_request(payload, self.server.state.allowed_keys)
        if press_request is None:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": error or "Invalid press payload."},
            )
            return

        try:
            if press_request.has_emergency_stop:
                self.server.state.key_sender.press(EMERGENCY_STOP_KEY)
            elif press_request.is_combo:
                self.server.state.key_sender.press_combo(press_request.keys)
            elif press_request.use_secondary:
                modifier = self.server.state.secondary_modifier
                self.server.state.key_sender.press_chord(modifier, press_request.key)
            else:
                self.server.state.key_sender.press(press_request.key)
        except (KeypressError, UnsupportedPlatformError) as exc:
            LOGGER.exception("keypress backend failed")
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"ok": False, "error": str(exc)},
            )
            return

        if press_request.has_emergency_stop:
            LOGGER.info("sent emergency stop keypress: %s", EMERGENCY_STOP_KEY)
            self._send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "key": EMERGENCY_STOP_KEY,
                    "use_secondary": False,
                    "emergency_stop": True,
                },
            )
            return

        if press_request.is_combo:
            LOGGER.info("sent key combo: %s", " + ".join(press_request.keys))
            self._send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "keys": list(press_request.keys),
                    "is_combo": True,
                },
            )
            return

        if press_request.use_secondary:
            modifier = self.server.state.secondary_modifier
            LOGGER.info("sent key chord: %s + %s", modifier, press_request.key)
            self._send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "key": press_request.key,
                    "use_secondary": True,
                    "modifier": modifier,
                },
            )
            return

        LOGGER.info("sent keypress: %s", press_request.key)
        self._send_json(
            HTTPStatus.OK,
            {"ok": True, "key": press_request.key, "use_secondary": False},
        )

    def log_message(self, format: str, *args: object) -> None:
        LOGGER.info("%s - %s", self.address_string(), format % args)

    def _send_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self._send_response(status, body, content_type="application/json; charset=utf-8")

    def _send_response(
        self,
        status: HTTPStatus,
        body: bytes,
        *,
        content_type: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if headers:
            for name, value in headers.items():
                self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)


def create_server(
    host: str,
    port: int,
    key_sender: KeySender,
    *,
    strict_port: bool = False,
) -> MobileTyperHTTPServer:
    state = AppState(
        key_sender=key_sender,
        requested_host=host,
        requested_port=port,
        actual_port=port,
    )

    try:
        server = MobileTyperHTTPServer((host, port), state)
    except OSError as exc:
        if strict_port or port == 0 or not is_port_in_use_error(exc):
            raise

        server = None
        for candidate_port in fallback_ports(port):
            try:
                server = MobileTyperHTTPServer((host, candidate_port), state)
                break
            except OSError as fallback_exc:
                if not is_port_in_use_error(fallback_exc):
                    raise

        if server is None:
            raise exc

        state.port_notice = (
            f"Port {port} was busy, so Mobile Typer switched to port "
            f"{server.server_address[1]}."
        )

    state.actual_port = server.server_address[1]
    refresh_server_urls(server)
    return server


def refresh_server_urls(server: MobileTyperHTTPServer) -> list[str]:
    urls = discover_urls(server.state.actual_port, server.state.requested_host)
    server.state.urls = urls
    return urls


__all__ = [
    "AppState",
    "MobileTyperHTTPServer",
    "MobileTyperHandler",
    "create_server",
    "refresh_server_urls",
]
