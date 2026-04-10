from __future__ import annotations

import socket

from .constants import PORT_IN_USE_ERRNOS


def discover_urls(port: int, bind_host: str) -> list[str]:
    if bind_host not in {"0.0.0.0", "::"}:
        host = bind_host
        if host == "127.0.0.1":
            return [f"http://localhost:{port}"]
        return [f"http://{host}:{port}"]

    addresses: list[str] = []
    seen_addresses: set[str] = set()

    def add_address(ip: str) -> None:
        if not ip or ip.startswith("127.") or ip in seen_addresses:
            return
        seen_addresses.add(ip)
        addresses.append(ip)

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("192.0.2.1", 80))
            add_address(sock.getsockname()[0])
    except OSError:
        pass

    try:
        host_info = socket.getaddrinfo(
            socket.gethostname(),
            None,
            family=socket.AF_INET,
            type=socket.SOCK_STREAM,
        )
        for info in host_info:
            add_address(info[4][0])
    except socket.gaierror:
        pass

    if not addresses:
        return [f"http://localhost:{port}"]

    return [f"http://{ip}:{port}" for ip in addresses]


def is_port_in_use_error(exc: OSError) -> bool:
    return exc.errno in PORT_IN_USE_ERRNOS or "address already in use" in str(exc).lower()


def fallback_ports(port: int, attempts: int = 10) -> list[int]:
    if port <= 0:
        return [0]

    ports: list[int] = []
    for offset in range(1, attempts + 1):
        candidate = port + offset
        if candidate > 65535:
            break
        ports.append(candidate)
    ports.append(0)
    return ports


__all__ = ["discover_urls", "is_port_in_use_error", "fallback_ports"]
