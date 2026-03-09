"""Tests for /api/terms/stats, /api/terms/export, /api/terms/import endpoints."""

from __future__ import annotations

import io
import json
import tempfile
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.backend.models.term import Term
from app.backend.services.term_db import TermDB


@pytest.fixture()
def db(tmp_path):
    return TermDB(db_path=tmp_path / "api_test.sqlite")


@pytest.fixture()
def client(db, monkeypatch):
    """Create a test client with a patched TermDB and minimal job manager stub."""
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

    # Patch _term_db in routes
    import app.backend.api.routes as routes_mod
    monkeypatch.setattr(routes_mod, "_term_db", db)

    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(routes_mod.router, prefix="/api")
    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /api/terms/stats
# ---------------------------------------------------------------------------

def test_terms_stats_empty(client):
    resp = client.get("/api/terms/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["by_target_lang"] == {}
    assert data["by_domain"] == {}


def test_terms_stats_with_data(client, db):
    db.insert(Term("Pin", "chân", "zh", "vi", "technical"))
    db.insert(Term("ROI", "ROI", "en", "vi", "finance"))
    resp = client.get("/api/terms/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["by_domain"]["technical"] == 1
    assert data["by_domain"]["finance"] == 1


# ---------------------------------------------------------------------------
# GET /api/terms/export
# ---------------------------------------------------------------------------

def test_terms_export_json(client, db):
    db.insert(Term("Pin", "chân", "zh", "vi", "technical"))
    resp = client.get("/api/terms/export?format=json")
    assert resp.status_code == 200
    assert "application/json" in resp.headers["content-type"]
    body = resp.json()
    assert body["version"] == 1
    assert len(body["terms"]) == 1
    assert body["terms"][0]["source_text"] == "Pin"


def test_terms_export_csv(client, db):
    db.insert(Term("Pin", "chân", "zh", "vi", "technical"))
    resp = client.get("/api/terms/export?format=csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    text = resp.text
    assert "Pin" in text
    assert "source_text" in text  # header row


def test_terms_export_invalid_format(client):
    resp = client.get("/api/terms/export?format=xml")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /api/terms/import
# ---------------------------------------------------------------------------

def _json_import_bytes(terms):
    payload = {"version": 1, "exported_at": "2026-01-01T00:00:00Z", "terms": terms}
    return json.dumps(payload).encode()


def test_terms_import_json_insert(client, db):
    data = _json_import_bytes([{
        "source_text": "Pin",
        "target_text": "chân",
        "source_lang": "zh",
        "target_lang": "vi",
        "domain": "technical",
        "context_snippet": "",
        "confidence": 0.9,
        "usage_count": 0,
    }])
    resp = client.post(
        "/api/terms/import?strategy=skip",
        files={"file": ("terms.json", io.BytesIO(data), "application/json")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["inserted"] == 1
    assert body["skipped"] == 0
    assert db.exists("Pin", "vi", "technical")


def test_terms_import_skip_duplicate(client, db):
    db.insert(Term("Pin", "chân", "zh", "vi", "technical", confidence=0.9))
    data = _json_import_bytes([{
        "source_text": "Pin",
        "target_text": "đinh",
        "source_lang": "zh",
        "target_lang": "vi",
        "domain": "technical",
        "context_snippet": "",
        "confidence": 0.5,
        "usage_count": 0,
    }])
    resp = client.post(
        "/api/terms/import?strategy=skip",
        files={"file": ("terms.json", io.BytesIO(data), "application/json")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["skipped"] == 1
    # Original should remain
    terms = db.get_top_terms("vi", "technical")
    assert terms[0].target_text == "chân"


def test_terms_import_invalid_strategy(client):
    resp = client.post(
        "/api/terms/import?strategy=invalid",
        files={"file": ("terms.json", io.BytesIO(b'{}'), "application/json")},
    )
    assert resp.status_code == 400


def test_terms_import_invalid_file_type(client):
    resp = client.post(
        "/api/terms/import?strategy=skip",
        files={"file": ("terms.xlsx", io.BytesIO(b'data'), "application/octet-stream")},
    )
    assert resp.status_code == 400
