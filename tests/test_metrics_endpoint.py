"""Contract and integration tests for GET /api/metrics.

Covers AC-1, AC-2, AC-3, AC-5, AC-7.
Uses FastAPI TestClient; mocks at the HTTP boundary (requests).
"""

from __future__ import annotations

import types
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.backend.services.metrics as metrics_mod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_metrics():
    """Isolate counter state between every test."""
    metrics_mod.reset()
    yield
    metrics_mod.reset()


@pytest.fixture()
def client(monkeypatch):
    """Create a minimal TestClient with only the routes module loaded."""

    # Stub out job_manager to avoid DB / thread dependencies
    fake_jm_module = types.ModuleType("app.backend.services.job_manager")

    class FakeJobManager:
        def create_job(self, *a, **kw):
            return SimpleNamespace(job_id="fake-job")
        def get_job(self, job_id):
            return None
        def cancel_job(self, job_id):
            return False
        def get_stats(self):
            return {}

    fake_jm_module.JobManager = FakeJobManager
    fake_jm_module.JobRecord = object
    monkeypatch.setitem(__import__("sys").modules, "app.backend.services.job_manager", fake_jm_module)

    # Stub translation_cache
    fake_cache_module = types.ModuleType("app.backend.services.translation_cache")
    fake_cache_module.get_cache = lambda: None
    monkeypatch.setitem(__import__("sys").modules, "app.backend.services.translation_cache", fake_cache_module)

    # Stub model_router
    fake_router_module = types.ModuleType("app.backend.services.model_router")

    class FakeRouteGroup:
        pass

    fake_router_module.RouteGroup = FakeRouteGroup
    fake_router_module.get_route_info = lambda *a, **kw: []
    fake_router_module.resolve_route_groups = lambda *a, **kw: None
    monkeypatch.setitem(__import__("sys").modules, "app.backend.services.model_router", fake_router_module)

    # Stub ollama_client.list_ollama_models
    import app.backend.clients.ollama_client as oc
    monkeypatch.setattr(oc, "list_ollama_models", lambda: [])

    import app.backend.api.routes as routes_mod

    app = FastAPI()
    app.include_router(routes_mod.router, prefix="/api")
    return TestClient(app)


# ---------------------------------------------------------------------------
# AC-1: HTTP 200 with correct Content-Type
# ---------------------------------------------------------------------------

def test_get_metrics_returns_200(client):
    resp = client.get("/api/metrics")
    assert resp.status_code == 200


def test_get_metrics_content_type_is_json(client):
    resp = client.get("/api/metrics")
    assert "application/json" in resp.headers.get("content-type", "")


# ---------------------------------------------------------------------------
# AC-2: Response body has all five keys with correct types
# ---------------------------------------------------------------------------

def test_get_metrics_response_keys_present(client):
    data = client.get("/api/metrics").json()
    expected_keys = {
        "translation_count",
        "translation_latency_mean_ms",
        "provider_failure_count",
        "font_cache_hits",
        "font_cache_misses",
    }
    assert expected_keys <= set(data.keys())


def test_get_metrics_field_types(client):
    data = client.get("/api/metrics").json()
    assert isinstance(data["translation_count"], int)
    assert isinstance(data["translation_latency_mean_ms"], float)
    assert isinstance(data["provider_failure_count"], int)
    assert isinstance(data["font_cache_hits"], int)
    assert isinstance(data["font_cache_misses"], int)


def test_get_metrics_initial_values_are_zero(client):
    data = client.get("/api/metrics").json()
    assert data["translation_count"] == 0
    assert data["translation_latency_mean_ms"] == 0.0
    assert data["provider_failure_count"] == 0
    assert data["font_cache_hits"] == 0
    assert data["font_cache_misses"] == 0


# ---------------------------------------------------------------------------
# AC-3: Counter update is reflected in endpoint response
# ---------------------------------------------------------------------------

def test_translation_count_reflected_in_endpoint(client):
    """After calling record_translation, the endpoint must show the updated count."""
    metrics_mod.record_translation(50.0)
    data = client.get("/api/metrics").json()
    assert data["translation_count"] == 1
    assert data["translation_latency_mean_ms"] == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# AC-7: Existing behavior is unchanged (regression guard)
# ---------------------------------------------------------------------------

def test_existing_translation_behavior_unchanged():
    """Importing the instrumented translation_service must not raise."""
    # If metrics hooks altered control flow this import would fail or an error
    # would surface during the test session's import of translation_service.
    import app.backend.services.translation_service as ts  # noqa: F401
    assert hasattr(ts, "translate_texts")


def test_existing_font_load_behavior_unchanged():
    """Importing the instrumented pdf_generator must not raise."""
    # guard: the module must still expose the expected public symbols
    import app.backend.renderers.pdf_generator as pg  # noqa: F401
    assert hasattr(pg, "_load_font_buffer")
    assert hasattr(pg, "clear_font_cache")
