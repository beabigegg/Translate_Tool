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


# ── cloud-reasoning-stall-hardening: lowered ceiling (480→120) + bounded embed() ──
#
# AC-3 (BR-100 ceiling): the wall-clock ceiling itself — not the specific 480s vs
# 120s literal — is what's under test here (the literal default is covered by
# TestTotalTimeoutConfig::test_env_var_parses_positive_float_default in
# test_openai_compatible_client.py). These two resilience tests prove: (1) a
# `_post_completion` whose `session.post` never returns is aborted by whatever the
# ceiling is set to, in a small bounded multiple of it — never anywhere close to
# the legacy 480s — and degrades to ok=False; (2) embed()'s POST, now routed
# through the SAME `_run_bounded_post` wrapper (BR-100/AC-4), is aborted the same
# way and degrades to `[]` instead of hanging or raising.
#
# Per launch-task instruction (not the real-socket _DribbleServer pattern above):
# simulate the stall with a fake/slow `requests.Session.post` blocked on a
# threading.Event — no live network call, no real socket. The Event is released in
# a `finally` so the abandoned daemon worker inside `_run_bounded_post` unblocks
# promptly instead of leaking for the test process's lifetime.


def _blocking_client() -> OpenAICompatibleClient:
    return OpenAICompatibleClient(
        base_url="http://fake-host:8080",
        api_key="test-key",
        model="gpt-oss:120b",
        provider_id="stall-probe",
    )


def test_stalled_dribble_aborts_within_120s_ceiling_not_480s():
    """AC-3/BR-100: a stalled session.post is aborted by the ceiling, not the
    legacy 480s default — proven by patching the ceiling to a small value and
    asserting the call returns in a small bounded multiple of THAT value, never
    anywhere near 480s.
    """
    release = threading.Event()

    def _blocking_post(*_args, **_kwargs):
        # Simulate a Cloudflare-cut CLOSE-WAIT dribble: session.post never
        # returns on its own. The worker thread stays blocked here until the
        # test releases it in `finally`; the ceiling must abort the CALLER
        # long before that release happens.
        release.wait(timeout=10.0)
        raise RuntimeError("fake session.post must not complete inside this test")

    client = _blocking_client()
    ceiling = 0.5
    try:
        with patch("requests.Session.post", side_effect=_blocking_post), \
             patch("app.backend.config.OPENAI_TOTAL_TIMEOUT_SECONDS", ceiling):
            t0 = time.monotonic()
            ok, msg = client._post_completion("hello")
            elapsed = time.monotonic() - t0
    finally:
        release.set()  # unblock the abandoned daemon worker so it doesn't linger

    assert ok is False, f"a stalled post must degrade to ok=False, got ok=True msg={msg!r}"
    assert elapsed < ceiling * 5, (
        f"ceiling ({ceiling}s) — not the 480s legacy default — must govern; "
        f"took {elapsed:.2f}s, expected well under {ceiling * 5:.2f}s"
    )
    assert elapsed >= ceiling * 0.5, (
        f"call returned suspiciously fast ({elapsed:.2f}s) for a {ceiling}s ceiling; "
        "the ceiling wait loop may not actually be governing the abort"
    )


def test_embed_stalled_post_aborts_within_ceiling_degrades_to_empty_list():
    """AC-4/BR-100: embed(), now routed through the same _run_bounded_post ceiling
    as completions, aborts a stalled session.post within the ceiling and degrades
    to [] — never a hang, never an unhandled exception.
    """
    release = threading.Event()

    def _blocking_post(*_args, **_kwargs):
        release.wait(timeout=10.0)
        raise RuntimeError("fake session.post must not complete inside this test")

    client = _blocking_client()
    ceiling = 0.5
    try:
        with patch("requests.Session.post", side_effect=_blocking_post), \
             patch("app.backend.config.OPENAI_TOTAL_TIMEOUT_SECONDS", ceiling):
            t0 = time.monotonic()
            vectors = client.embed(["hello"], "text-embedding-test")
            elapsed = time.monotonic() - t0
    finally:
        release.set()  # unblock the abandoned daemon worker so it doesn't linger

    assert vectors == [], f"a stalled embed() POST must degrade to [], got {vectors!r}"
    assert elapsed < ceiling * 5, (
        f"ceiling ({ceiling}s) must bound embed(); took {elapsed:.2f}s, "
        f"expected well under {ceiling * 5:.2f}s"
    )
    assert elapsed >= ceiling * 0.5, (
        f"call returned suspiciously fast ({elapsed:.2f}s) for a {ceiling}s ceiling; "
        "the ceiling wait loop may not actually be governing the abort"
    )
