"""Resilience tests for the cloud-LLM total-duration ceiling (qa-judge-hang-recovery).

These exercise the REAL interruptible-post path against a local socket that
dribbles keep-alive bytes forever (each inter-byte gap < the read timeout), which
is exactly the live-incident shape the per-chunk (connect, read) tuple cannot
bound. Never mock OpenAICompatibleClient internals here (tautology risk) — only
the wall-clock ceiling and a real blocked read are under test.

AC-1: a set cancel_event aborts a blocked in-flight read promptly.
AC-2: the ceiling fires on a dribbling response instead of hanging forever.
AC-8: regression repro — a dribble that hung 30+ min in the incident is now bounded.
"""

from __future__ import annotations

import socket
import threading
import time
from unittest.mock import patch

import pytest

from app.backend.clients.openai_compatible_client import OpenAICompatibleClient


class _DribbleServer:
    """A local HTTP server that sends 200 headers claiming a large body, then
    dribbles one byte at a time forever — never completing the Content-Length.

    A `requests` client doing a non-streamed POST blocks in the body read; the
    per-request read timeout never fires because bytes keep trickling. Only the
    total-duration ceiling can bound it.
    """

    def __init__(self, dribble_total: float = 8.0, chunk_interval: float = 0.2):
        self.dribble_total = dribble_total
        self.chunk_interval = chunk_interval
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(1)
        self.port = self._sock.getsockname()[1]
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, name="dribble-server", daemon=True)

    def _serve(self) -> None:
        try:
            self._sock.settimeout(5.0)
            conn, _ = self._sock.accept()
        except OSError:
            return
        with conn:
            conn.settimeout(1.0)
            try:
                conn.recv(65536)  # consume the request line + headers (best-effort)
            except OSError:
                pass
            headers = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/json\r\n"
                "Content-Length: 100000\r\n"
                "\r\n"
            ).encode()
            try:
                conn.sendall(headers)
                deadline = time.monotonic() + self.dribble_total
                while not self._stop.is_set() and time.monotonic() < deadline:
                    conn.sendall(b" ")  # dribble a keep-alive byte
                    time.sleep(self.chunk_interval)
            except OSError:
                return

    def __enter__(self) -> "_DribbleServer":
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        try:
            self._sock.close()
        except OSError:
            pass

    def client(self) -> OpenAICompatibleClient:
        return OpenAICompatibleClient(
            base_url=f"http://127.0.0.1:{self.port}",
            api_key="test-key",
            model="gpt-oss:120b",
            provider_id="dribble",
        )


def test_ceiling_fires_on_dribbling_never_silent_response():
    """AC-2/BR-100: a dribbling response is aborted at the ceiling, not indefinitely."""
    with _DribbleServer() as srv:
        client = srv.client()
        with patch("app.backend.config.OPENAI_TOTAL_TIMEOUT_SECONDS", 1.0):
            t0 = time.monotonic()
            ok, msg = client._post_completion("hello")
            elapsed = time.monotonic() - t0

    assert ok is False, "a hung/dribbling call must degrade to ok=False, not hang or crash"
    assert elapsed < 5.0, f"ceiling (1s) should abort promptly; took {elapsed:.1f}s"


def test_cancel_event_aborts_blocked_post_mid_read():
    """AC-1/BR-99: setting cancel_event aborts a blocked in-flight read promptly."""
    cancel = threading.Event()
    with _DribbleServer() as srv:
        client = srv.client()
        threading.Thread(target=lambda: (time.sleep(0.5), cancel.set()), daemon=True).start()
        # Ceiling deliberately high so the *cancel* is what aborts the read, not the ceiling.
        with patch("app.backend.config.OPENAI_TOTAL_TIMEOUT_SECONDS", 60.0):
            t0 = time.monotonic()
            ok, msg = client._post_completion("hello", cancel_event=cancel)
            elapsed = time.monotonic() - t0

    assert ok is False
    assert elapsed < 5.0, f"cancel should abort the blocked read ~0.5s; took {elapsed:.1f}s"


def test_dribbling_socket_regression_repro_matches_live_incident():
    """AC-8/BR-100: the dribble that hung the backend 30+ min is now bounded to ~ceiling.

    Pre-fix (no ceiling) this call blocks until the socket eventually closes (well
    over the 5s bound asserted here); post-fix the ceiling bounds it.
    """
    with _DribbleServer(dribble_total=8.0) as srv:
        client = srv.client()
        with patch("app.backend.config.OPENAI_TOTAL_TIMEOUT_SECONDS", 1.0):
            t0 = time.monotonic()
            ok, _msg = client._post_completion("hello")
            elapsed = time.monotonic() - t0

    assert ok is False and elapsed < 5.0, (
        f"regression: dribbling response not bounded by the ceiling ({elapsed:.1f}s)"
    )
