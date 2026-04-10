from __future__ import annotations

import importlib.util
import json
import socket
import threading
import unittest
import urllib.error
import urllib.request
from unittest import mock

from mobile_typer.app import (
    COMBO_WINDOW_MS,
    EMERGENCY_STOP_KEY,
    build_qr_matrix,
    create_server,
    discover_urls,
    fallback_ports,
    parse_args,
    render_page,
    render_terminal_qr,
)

EXPECTED_ALLOWED_KEYS = [chr(code) for code in range(ord("a"), ord("r") + 1)]


class FakeKeySender:
    backend_name = "fake"

    def __init__(self) -> None:
        self.pressed: list[str] = []
        self.chords: list[tuple[str, str]] = []
        self.combos: list[tuple[str, ...]] = []

    def press(self, key: str) -> None:
        self.pressed.append(key)

    def press_combo(self, keys: tuple[str, ...]) -> None:
        self.combos.append(tuple(keys))

    def press_chord(self, modifier: str, key: str) -> None:
        self.chords.append((modifier, key))

    def close(self) -> None:
        return None


class MobileTyperServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sender = FakeKeySender()
        self.server = create_server("127.0.0.1", 0, self.sender)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: dict[str, object] | None = None,
    ) -> tuple[int, str]:
        data = None
        headers: dict[str, str] = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            f"{self.base_url}{path}",
            method=method,
            data=data,
            headers=headers,
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            return response.status, response.read().decode("utf-8")

    def request_error(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: dict[str, object] | None = None,
    ) -> tuple[int, str]:
        data = None
        headers: dict[str, str] = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            f"{self.base_url}{path}",
            method=method,
            data=data,
            headers=headers,
        )

        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(request, timeout=2)

        return context.exception.code, context.exception.read().decode("utf-8")

    def test_root_page_contains_buttons(self) -> None:
        status, body = self.request("/")
        self.assertEqual(status, 200)
        for key in EXPECTED_ALLOWED_KEYS:
            self.assertIn(f'data-key="{key}"', body)

    def test_health_endpoint_reports_backend(self) -> None:
        status, body = self.request("/api/health")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["backend"], "fake")
        self.assertEqual(payload["allowed_keys"], EXPECTED_ALLOWED_KEYS)

    def test_press_endpoint_sends_allowed_key(self) -> None:
        status, body = self.request("/api/press", method="POST", payload={"key": "A"})
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["key"], "a")
        self.assertFalse(payload["use_secondary"])
        self.assertEqual(self.sender.pressed, ["a"])
        self.assertEqual(self.sender.chords, [])
        self.assertEqual(self.sender.combos, [])

    def test_press_endpoint_sends_newly_added_allowed_key(self) -> None:
        status, body = self.request("/api/press", method="POST", payload={"key": "Q"})
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["key"], "q")
        self.assertFalse(payload["use_secondary"])
        self.assertEqual(self.sender.pressed, ["q"])
        self.assertEqual(self.sender.chords, [])
        self.assertEqual(self.sender.combos, [])

    def test_press_endpoint_sends_secondary_chord(self) -> None:
        status, body = self.request(
            "/api/press",
            method="POST",
            payload={"key": "A", "use_secondary": True},
        )
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["key"], "a")
        self.assertTrue(payload["use_secondary"])
        self.assertEqual(payload["modifier"], "e")
        self.assertEqual(self.sender.pressed, [])
        self.assertEqual(self.sender.chords, [("e", "a")])
        self.assertEqual(self.sender.combos, [])

    def test_press_endpoint_sends_combo(self) -> None:
        status, body = self.request(
            "/api/press",
            method="POST",
            payload={"keys": ["A", "B"]},
        )
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertTrue(payload["is_combo"])
        self.assertEqual(payload["keys"], ["a", "b"])
        self.assertEqual(self.sender.pressed, [])
        self.assertEqual(self.sender.chords, [])
        self.assertEqual(self.sender.combos, [("a", "b")])

    def test_press_endpoint_sends_longer_combo(self) -> None:
        status, body = self.request(
            "/api/press",
            method="POST",
            payload={"keys": ["A", "B", "C", "D"]},
        )
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertTrue(payload["is_combo"])
        self.assertEqual(payload["keys"], ["a", "b", "c", "d"])
        self.assertEqual(self.sender.pressed, [])
        self.assertEqual(self.sender.chords, [])
        self.assertEqual(self.sender.combos, [("a", "b", "c", "d")])

    def test_press_endpoint_prioritizes_emergency_stop_over_secondary(self) -> None:
        status, body = self.request(
            "/api/press",
            method="POST",
            payload={"key": "P", "use_secondary": True},
        )
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["key"], EMERGENCY_STOP_KEY)
        self.assertFalse(payload["use_secondary"])
        self.assertTrue(payload["emergency_stop"])
        self.assertEqual(self.sender.pressed, [EMERGENCY_STOP_KEY])
        self.assertEqual(self.sender.chords, [])
        self.assertEqual(self.sender.combos, [])

    def test_press_endpoint_prioritizes_emergency_stop_over_combo_payload(self) -> None:
        status, body = self.request(
            "/api/press",
            method="POST",
            payload={"keys": ["a", "p", "b"]},
        )
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["key"], EMERGENCY_STOP_KEY)
        self.assertFalse(payload["use_secondary"])
        self.assertTrue(payload["emergency_stop"])
        self.assertEqual(self.sender.pressed, [EMERGENCY_STOP_KEY])
        self.assertEqual(self.sender.chords, [])
        self.assertEqual(self.sender.combos, [])

    def test_press_endpoint_accepts_emergency_stop_from_single_item_keys_payload(self) -> None:
        status, body = self.request(
            "/api/press",
            method="POST",
            payload={"keys": ["p"]},
        )
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["key"], EMERGENCY_STOP_KEY)
        self.assertFalse(payload["use_secondary"])
        self.assertTrue(payload["emergency_stop"])
        self.assertEqual(self.sender.pressed, [EMERGENCY_STOP_KEY])
        self.assertEqual(self.sender.chords, [])
        self.assertEqual(self.sender.combos, [])

    def test_press_endpoint_rejects_unlisted_key(self) -> None:
        status, body = self.request_error(
            "/api/press",
            method="POST",
            payload={"key": "x"},
        )
        self.assertEqual(status, 400)
        payload = json.loads(body)
        self.assertIn("Only these keys are allowed", payload["error"])
        self.assertEqual(self.sender.pressed, [])
        self.assertEqual(self.sender.combos, [])

    def test_press_endpoint_rejects_combo_with_invalid_length(self) -> None:
        status, body = self.request_error(
            "/api/press",
            method="POST",
            payload={"keys": ["a"]},
        )
        self.assertEqual(status, 400)
        payload = json.loads(body)
        self.assertEqual(payload["error"], "Combo presses require at least two keys.")
        self.assertEqual(self.sender.combos, [])

    def test_press_endpoint_rejects_combo_with_duplicate_keys(self) -> None:
        status, body = self.request_error(
            "/api/press",
            method="POST",
            payload={"keys": ["a", "A"]},
        )
        self.assertEqual(status, 400)
        payload = json.loads(body)
        self.assertEqual(payload["error"], "Combo presses require distinct keys.")
        self.assertEqual(self.sender.combos, [])

    def test_press_endpoint_rejects_combo_with_unknown_key(self) -> None:
        status, body = self.request_error(
            "/api/press",
            method="POST",
            payload={"keys": ["a", "x"]},
        )
        self.assertEqual(status, 400)
        payload = json.loads(body)
        self.assertIn("Only these keys are allowed", payload["error"])
        self.assertEqual(self.sender.combos, [])

    def test_press_endpoint_rejects_mixed_key_and_keys_payload(self) -> None:
        status, body = self.request_error(
            "/api/press",
            method="POST",
            payload={"key": "a", "keys": ["b", "c"]},
        )
        self.assertEqual(status, 400)
        payload = json.loads(body)
        self.assertEqual(payload["error"], "Provide either 'key' or 'keys', not both.")
        self.assertEqual(self.sender.pressed, [])
        self.assertEqual(self.sender.combos, [])


class MobileTyperQrTests(unittest.TestCase):
    def test_parse_args_supports_no_gui(self) -> None:
        args = parse_args(["--no-gui", "--port", "8123"])

        self.assertTrue(args.no_gui)
        self.assertEqual(args.port, 8123)

    def test_parse_args_supports_strict_port(self) -> None:
        args = parse_args(["--strict-port", "--port", "9000"])

        self.assertTrue(args.strict_port)
        self.assertEqual(args.port, 9000)

    def test_fallback_ports_tries_sequential_ports_then_ephemeral(self) -> None:
        ports = fallback_ports(8000, attempts=3)

        self.assertEqual(ports, [8001, 8002, 8003, 0])

    @mock.patch("mobile_typer.app.socket.getaddrinfo")
    @mock.patch("mobile_typer.app.socket.socket")
    def test_discover_urls_prefers_primary_route_address(
        self,
        mock_socket_class: mock.Mock,
        mock_getaddrinfo: mock.Mock,
    ) -> None:
        mock_socket = mock_socket_class.return_value.__enter__.return_value
        mock_socket.getsockname.return_value = ("192.168.1.55", 43210)
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.0.0.10", 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("192.168.1.55", 0)),
        ]

        urls = discover_urls(8000, "0.0.0.0")

        self.assertEqual(urls[0], "http://192.168.1.55:8000")
        self.assertEqual(urls[1], "http://10.0.0.10:8000")

    @unittest.skipUnless(
        importlib.util.find_spec("qrcode"),
        "qrcode dependency is not installed in this interpreter",
    )
    def test_build_qr_matrix_returns_square_matrix(self) -> None:
        matrix = build_qr_matrix("http://192.168.1.55:8000")

        self.assertIsNotNone(matrix)
        assert matrix is not None
        self.assertGreater(len(matrix), 10)
        self.assertTrue(all(len(row) == len(matrix) for row in matrix))

    @unittest.skipUnless(
        importlib.util.find_spec("qrcode"),
        "qrcode dependency is not installed in this interpreter",
    )
    def test_render_terminal_qr_returns_ansi_block_art(self) -> None:
        qr_art = render_terminal_qr("http://192.168.1.55:8000")

        self.assertIsNotNone(qr_art)
        assert qr_art is not None
        self.assertIn("\x1b[40m  \x1b[0m", qr_art)
        self.assertIn("\x1b[47m  \x1b[0m", qr_art)
        self.assertGreater(len(qr_art.splitlines()), 10)

    def test_render_page_uses_spacious_button_only_layout(self) -> None:
        page = render_page(tuple(EXPECTED_ALLOWED_KEYS), ["http://localhost:8000"], "fake")

        self.assertIn("Mobile Typer hardware remote", page)
        self.assertIn("button-deck", page)
        self.assertIn("SVGRepo_iconCarrier", page)
        self.assertIn("STOP", page)
        self.assertIn("CL", page)
        self.assertIn("CA", page)
        self.assertIn("2nd", page)
        self.assertIn('data-secondary-armed="false"', page)
        self.assertIn('data-is-secondary-modifier="true"', page)
        self.assertIn('role="switch"', page)
        self.assertIn('aria-checked="false"', page)
        self.assertIn("button-band--switch", page)
        self.assertIn("button-switch-track", page)
        self.assertIn("button-switch-state--off", page)
        self.assertIn("button-switch-state--on", page)
        self.assertNotIn("button-switch-legend", page)
        self.assertIn("2nd switch on. It turns off after the next key press.", page)
        self.assertIn("2nd switch is off.", page)
        self.assertIn('data-guide-trigger="true"', page)
        self.assertIn('aria-label="Open the remote guide. Tap twice to open."', page)
        self.assertIn('style="grid-column: 4; grid-row: 5 / span 2;"', page)
        self.assertIn("guide-trigger__inner", page)
        self.assertIn("guide-trigger__eyebrow", page)
        self.assertIn("guide-trigger__hint", page)
        self.assertIn('id="remote-guide"', page)
        self.assertIn('role="dialog"', page)
        self.assertIn('aria-modal="true"', page)
        self.assertIn('id="guide-close"', page)
        self.assertIn("How the remote works", page)
        self.assertNotIn("Quick reference", page)
        self.assertNotIn("Tap a section to expand it.", page)
        self.assertNotIn("manual.pdf, section 5.1", page)
        self.assertNotIn("Using the remote", page)
        self.assertIn("Single buttons and combos", page)
        self.assertIn("The secondary switch", page)
        self.assertIn("Emergency stop", page)
        self.assertIn("Testing programs", page)
        self.assertIn("Entering gross weight", page)
        self.assertIn("Store functions", page)
        self.assertIn("Repeat displays", page)
        self.assertIn("Printout", page)
        self.assertIn("Clear functions", page)
        self.assertIn("Manual 5.1.1", page)
        self.assertIn("Manual 5.1.6", page)
        self.assertIn("Individual wheel-testing, left", page)
        self.assertIn("Regular mode", page)
        self.assertIn("SUPERAUTOMATIC", page)
        self.assertIn("All-wheel-drive test, left-hand side", page)
        self.assertIn("Enter gross weight", page)
        self.assertIn("Front axle", page)
        self.assertIn("Parking brake", page)
        self.assertIn("Max. values, front axle", page)
        self.assertIn("Frequency of resonance", page)
        self.assertIn("Graphic printout", page)
        self.assertIn("Erase complete memory", page)
        self.assertNotIn('<details class="guide-section" open>', page)
        self.assertIn("guide-summary", page)
        self.assertIn("guide-section-body", page)
        self.assertIn("guide-example", page)
        self.assertIn("guide-command-list", page)
        self.assertIn("guide-command", page)
        self.assertIn("guide-command-title", page)
        self.assertIn("guide-command-note", page)
        self.assertIn("guide-button-cluster", page)
        self.assertIn("guide-button-cluster--with-modifier", page)
        self.assertIn("guide-button-separator", page)
        self.assertIn("guide-button-separator--step", page)
        self.assertIn("guide-button-ref-wrap--modifier", page)
        self.assertIn("guide-button-ref__control", page)
        self.assertIn("guide-button-ref__control--modifier", page)
        self.assertIn("guide-button-ref__control--secondary-target", page)
        self.assertIn('data-has-secondary="true"', page)
        self.assertIn("remote-button--has-secondary", page)
        self.assertIn(f"const comboWindowMs = {COMBO_WINDOW_MS};", page)
        self.assertIn("const guideTapWindowMs = 700;", page)
        self.assertIn(f'const emergencyStopKey = "{EMERGENCY_STOP_KEY}";', page)
        self.assertIn('const guideTrigger = document.querySelector("[data-guide-trigger]");', page)
        self.assertIn('classList.add("is-pending")', page)
        self.assertIn('guideTrigger.classList.add("is-armed");', page)
        self.assertIn("status-chip__face", page)
        self.assertIn("status-chip__label", page)
        self.assertIn("--status-progress-turn", page)
        self.assertIn("conic-gradient(", page)
        self.assertIn('aria-hidden="true"', page)
        self.assertIn("left: calc(env(safe-area-inset-left, 0px) + 0.9rem);", page)
        self.assertIn("top: calc(env(safe-area-inset-top, 0px) + 0.9rem);", page)
        self.assertIn("waiting to send or extend a combo.", page)
        self.assertNotIn("waiting to arm 2nd or form a combo.", page)
        self.assertIn("controlSequence.map((control) => control.dataset.key)", page)
        self.assertIn("Sending emergency stop ", page)
        self.assertIn("clearPendingControls();", page)
        self.assertIn("background:\n        linear-gradient(180deg, rgba(255, 255, 255, 0.86), rgba(208, 216, 230, 0.96));", page)
        self.assertIn("opacity: 0.28;", page)
        self.assertIn("brightness(1.28)", page)
        self.assertIn("color: #121212;", page)
        self.assertIn("fill: #121212;", page)
        self.assertIn("guideOverlay.hidden = false;", page)
        self.assertIn("guideOverlay.hidden = true;", page)
        self.assertIn('document.body.classList.add("guide-open");', page)
        self.assertIn('document.body.classList.remove("guide-open");', page)
        self.assertIn("--guide-pad-top:", page)
        self.assertIn("overflow-y: auto;", page)
        self.assertIn("overflow-x: hidden;", page)
        self.assertIn("width: min(100%, 48rem);", page)
        self.assertIn("min-height: calc(100dvh - var(--guide-pad-top) - var(--guide-pad-bottom));", page)
        self.assertIn("overflow: visible;", page)
        self.assertIn(".guide-button-ref-wrap {\n      --guide-ref-scale: 0.6;\n      --guide-ref-width: 5.4rem;\n      --guide-ref-height: 7.3rem;\n      position: relative;", page)
        self.assertIn(".guide-button-ref__control {\n      position: absolute;\n      top: 0;\n      left: 0;", page)
        self.assertIn(".guide-button-cluster--with-modifier {\n      gap: 0.76rem;\n      margin-bottom: 1.1rem;", page)
        self.assertIn(".guide-button-separator {\n      width: 1.3rem;\n      min-height: calc(5.95rem * 0.6);\n      position: relative;\n      z-index: 2;", page)
        self.assertNotIn("guide-button-separator--modifier-plus", page)
        self.assertIn(".guide-button-ref-wrap--modifier-equal {\n      margin-right: 0;", page)
        self.assertIn(".guide-button-ref__control--guide-modifier-card {\n      border-color: rgba(244, 247, 255, 0.42);\n      background:", page)
        self.assertIn(".guide-button-ref__control--guide-modifier-card .button-inner {\n      border-color: rgba(124, 137, 162, 0.24);\n      padding: 0.34rem 0.2rem 0.24rem;", page)
        self.assertIn(".guide-button-ref__control--guide-modifier-card .button-band {\n      min-height: 1.78rem;\n      border-color: rgba(255, 255, 255, 0.44);\n      background:", page)
        self.assertIn("guide-button-ref-wrap--modifier-equal", page)
        self.assertIn("guide-button-ref__control--guide-modifier-card", page)
        self.assertIn("guide-modifier-card__state", page)
        self.assertIn(".guide-button-cluster--with-modifier .guide-button-ref__control--secondary-target .button-bottom {\n      background:", page)
        self.assertIn(".guide-button-ref__control--guide-modifier-card .button-band {\n        min-height: 1.64rem;", page)
        self.assertIn(".guide-command {\n      display: grid;\n      grid-template-columns: 1fr;", page)
        self.assertIn(".guide-example {\n      display: grid;\n      grid-template-columns: 1fr;", page)
        self.assertIn("-webkit-overflow-scrolling: touch;", page)
        self.assertIn('event.key === "Escape"', page)
        self.assertIn("if (isSecondaryModifier) {", page)
        self.assertIn("await flushPendingSequence();", page)
        self.assertNotIn("secondary-banner", page)
        self.assertNotIn("display-screen", page)
        self.assertNotIn("remote-shell", page)
        self.assertNotIn("Virtual Track", page)
        self.assertNotIn("Run4More", page)
        self.assertEqual(page.count('data-key="'), len(EXPECTED_ALLOWED_KEYS))
        for key in EXPECTED_ALLOWED_KEYS:
            self.assertIn(f'data-key="{key}"', page)


if __name__ == "__main__":
    unittest.main()
