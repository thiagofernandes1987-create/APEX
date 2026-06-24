"""
Sprint X — test port allocator (resolves gate-2b LOW finding "hardcoded_port").

Previously several test_marco_m*.py files hardcoded port numbers like
PORT_M4 = 19084.  Running the suite with pytest-xdist or back-to-back
sessions occasionally tripped on TIME_WAIT collisions.  This helper
asks the kernel for an unused port atomically and returns it.

Usage
-----

    from tests._port_allocator import allocate_port
    PORT_MY = allocate_port()

The port is reserved by a brief socket bind, then released — the
returned number is suitable for HTTPServer to bind shortly thereafter.
"""
from __future__ import annotations

import socket


def allocate_port(*, host: str = "127.0.0.1") -> int:
    """Ask the OS for an ephemeral port that's currently free."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        port = s.getsockname()[1]
    return int(port)
