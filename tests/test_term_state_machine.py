"""Tests for p1-term-state-machine: 4-state term lifecycle, injection gate, conflict protection."""

from __future__ import annotations

import types
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.backend.models.term import Term
from app.backend.services.term_db import TermDB
from app.backend.services.term_extractor import (
    _parse_translation_response,
    _LLM_CONFIDENCE_CAP,
    TermExtractor,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db(tmp_path):
    """Fresh TermDB backed by a temp SQLite file."""
    instance = TermDB(db_path=str(tmp_path / "test.db"))
    yield instance


def _make_term(**kwargs) -> Term:
    defaults = dict(
        source_text="Pin",
        target_text="chân",
        source_lang="zh",
        target_lang="vi",
        domain="technical",
        context_snippet="",
        confidence=1.0,
        usage_count=0,
        status="unverified",
    )
    defaults.update(kwargs)
    return Term(**defaults)


@pytest.fixture()
def client(db, monkeypatch):
    """Test client with stubbed services and patched _term_db."""
    # Stub job_manager
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

    import app.backend.clients.ollama_client as oc
    monkeypatch.setattr(oc, "list_ollama_models", lambda: [])

    import app.backend.api.routes as routes_mod
    monkeypatch.setattr(routes_mod, "_term_db", db)

    app = FastAPI()
    app.include_router(routes_mod.router, prefix="/api")
    return TestClient(app)


# ---------------------------------------------------------------------------
# AC-1: injection gate excludes rejected and needs_review terms
# ---------------------------------------------------------------------------

def test_injection_gate_excludes_rejected_and_needs_review(db):
    """get_top_terms / get_document_terms must not return rejected or needs_review terms."""
    rejected_term = _make_term(source_text="RejectedTerm", status="rejected", confidence=1.0)
    needs_review_term = _make_term(source_text="NeedsReviewTerm", status="needs_review", confidence=1.0)

    # Insert directly via SQL to bypass any status validation in insert()
    import sqlite3
    conn = sqlite3.connect(str(db.db_path))
    conn.row_factory = sqlite3.Row
    for t in [rejected_term, needs_review_term]:
        conn.execute(
            """INSERT INTO terms
               (source_text, target_text, source_lang, target_lang, domain,
                context_snippet, confidence, usage_count, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (t.source_text, t.target_text, t.source_lang, t.target_lang, t.domain,
             t.context_snippet, t.confidence, t.usage_count, t.status, t.created_at),
        )
    conn.commit()
    conn.close()

    top = db.get_top_terms("vi", "technical")
    top_sources = {t.source_text for t in top}
    assert "RejectedTerm" not in top_sources
    assert "NeedsReviewTerm" not in top_sources

    doc = db.get_document_terms("vi", "technical", ["RejectedTerm", "NeedsReviewTerm"])
    doc_sources = {t.source_text for t in doc}
    assert "RejectedTerm" not in doc_sources
    assert "NeedsReviewTerm" not in doc_sources


# ---------------------------------------------------------------------------
# AC-2: default gate excludes unverified confidence=1.0
# ---------------------------------------------------------------------------

def test_injection_gate_unverified_confidence_1_not_injected_by_default(db, monkeypatch):
    """unverified terms with confidence=1.0 must NOT appear when loose gate is off."""
    monkeypatch.setattr("app.backend.services.term_db.TERM_INJECT_HIGH_CONFIDENCE_UNVERIFIED", False)

    term = _make_term(source_text="HighConfUnverified", status="unverified", confidence=1.0)
    db.insert(term)

    top = db.get_top_terms("vi", "technical")
    assert all(t.source_text != "HighConfUnverified" for t in top)

    doc = db.get_document_terms("vi", "technical", ["HighConfUnverified"])
    assert all(t.source_text != "HighConfUnverified" for t in doc)


# ---------------------------------------------------------------------------
# AC-3: optional loose gate includes high-confidence unverified
# ---------------------------------------------------------------------------

def test_injection_gate_loose_mode_includes_high_confidence_unverified(db, monkeypatch):
    """With loose gate on, unverified >= threshold included; below threshold excluded."""
    monkeypatch.setattr("app.backend.services.term_db.TERM_INJECT_HIGH_CONFIDENCE_UNVERIFIED", True)
    monkeypatch.setattr("app.backend.services.term_db.TERM_INJECT_CONF_THRESHOLD", 0.9)

    high_conf = _make_term(source_text="HighConf", status="unverified", confidence=0.95)
    low_conf = _make_term(source_text="LowConf", status="unverified", confidence=0.5)
    db.insert(high_conf)
    db.insert(low_conf)

    top = db.get_top_terms("vi", "technical")
    top_sources = {t.source_text for t in top}
    assert "HighConf" in top_sources, "High-confidence unverified should be included in loose mode"
    assert "LowConf" not in top_sources, "Low-confidence unverified should be excluded even in loose mode"

    doc = db.get_document_terms("vi", "technical", ["HighConf", "LowConf"])
    doc_sources = {t.source_text for t in doc}
    assert "HighConf" in doc_sources
    assert "LowConf" not in doc_sources


# ---------------------------------------------------------------------------
# AC-4: reject() and flag_needs_review() transitions
# ---------------------------------------------------------------------------

def test_reject_and_flag_needs_review_transitions(db):
    """State transition methods must update status and return correct bool."""
    import sqlite3

    # reject() from unverified
    db.insert(_make_term(source_text="TermA", status="unverified"))
    result = db.reject("TermA", "vi", "technical")
    assert result is True
    conn = sqlite3.connect(str(db.db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT status FROM terms WHERE source_text=? AND target_lang=? AND domain=?",
        ("TermA", "vi", "technical"),
    ).fetchone()
    conn.close()
    assert row["status"] == "rejected"

    # flag_needs_review() from unverified
    db.insert(_make_term(source_text="TermB", status="unverified"))
    result = db.flag_needs_review("TermB", "vi", "technical")
    assert result is True
    conn = sqlite3.connect(str(db.db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT status FROM terms WHERE source_text=? AND target_lang=? AND domain=?",
        ("TermB", "vi", "technical"),
    ).fetchone()
    conn.close()
    assert row["status"] == "needs_review"

    # flag_needs_review() from approved
    db.insert(_make_term(source_text="TermC", status="unverified"))
    db.approve("TermC", "vi", "technical")
    result = db.flag_needs_review("TermC", "vi", "technical")
    assert result is True
    conn = sqlite3.connect(str(db.db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT status FROM terms WHERE source_text=? AND target_lang=? AND domain=?",
        ("TermC", "vi", "technical"),
    ).fetchone()
    conn.close()
    assert row["status"] == "needs_review"

    # reject() on nonexistent term returns False
    assert db.reject("NonExistent", "vi", "technical") is False

    # flag_needs_review() on nonexistent term returns False
    assert db.flag_needs_review("NonExistent", "vi", "technical") is False


# ---------------------------------------------------------------------------
# AC-5: insert() conflict strategy protects rejected
# ---------------------------------------------------------------------------

def test_insert_conflict_strategy_protects_rejected(db):
    """overwrite and merge strategies must skip rejected; force must overwrite."""
    import sqlite3

    def _get_status(source_text):
        conn = sqlite3.connect(str(db.db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT status FROM terms WHERE source_text=? AND target_lang=? AND domain=?",
            (source_text, "vi", "technical"),
        ).fetchone()
        conn.close()
        return row["status"] if row else None

    # Test overwrite strategy
    db.insert(_make_term(source_text="OW", status="unverified"))
    db.reject("OW", "vi", "technical")
    assert _get_status("OW") == "rejected"

    new_term = _make_term(source_text="OW", status="unverified", target_text="new_target")
    result = db.insert(new_term, strategy="overwrite")
    assert result == "skipped"
    assert _get_status("OW") == "rejected"

    # Test merge strategy
    db.insert(_make_term(source_text="MG", status="unverified"))
    db.reject("MG", "vi", "technical")
    assert _get_status("MG") == "rejected"

    new_term2 = _make_term(source_text="MG", status="unverified", target_text="new_target", confidence=0.99)
    result = db.insert(new_term2, strategy="merge")
    assert result == "skipped"
    assert _get_status("MG") == "rejected"

    # Test force strategy: must overwrite rejected
    db.insert(_make_term(source_text="FC", status="unverified"))
    db.reject("FC", "vi", "technical")
    assert _get_status("FC") == "rejected"

    new_term3 = _make_term(source_text="FC", status="unverified", target_text="forced_target")
    result = db.insert(new_term3, strategy="force")
    assert result == "overwritten"
    assert _get_status("FC") == "unverified"


# ---------------------------------------------------------------------------
# AC-6: get_stats() returns by_status
# ---------------------------------------------------------------------------

def test_get_stats_returns_by_status(db):
    """get_stats() must return by_status dict with counts for all inserted statuses."""
    import sqlite3

    # Insert one term of each status via SQL to avoid insert() strategy restrictions
    conn = sqlite3.connect(str(db.db_path))
    statuses = ["unverified", "needs_review", "approved", "rejected"]
    for i, status in enumerate(statuses):
        t = _make_term(source_text=f"Term{i}", status=status)
        conn.execute(
            """INSERT INTO terms
               (source_text, target_text, source_lang, target_lang, domain,
                context_snippet, confidence, usage_count, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (t.source_text, t.target_text, t.source_lang, t.target_lang, t.domain,
             t.context_snippet, t.confidence, t.usage_count, t.status, t.created_at),
        )
    conn.commit()
    conn.close()

    stats = db.get_stats()
    assert "by_status" in stats
    by_status = stats["by_status"]
    for status in statuses:
        assert status in by_status, f"Expected '{status}' key in by_status"
        assert by_status[status] == 1, f"Expected count 1 for status '{status}'"
    assert stats["total"] == 4


# ---------------------------------------------------------------------------
# AC-7: API endpoints /terms/reject and /terms/flag-needs-review
# ---------------------------------------------------------------------------

def test_reject_and_flag_api_endpoints(client, db):
    """POST /terms/reject and /terms/flag-needs-review: 200 on found, 404 on missing."""
    # Insert a term
    db.insert(_make_term(source_text="APITerm", status="unverified"))

    # POST /terms/reject with existing term
    resp = client.post("/api/terms/reject", json={
        "source_text": "APITerm",
        "target_lang": "vi",
        "domain": "technical",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"

    # Insert another term
    db.insert(_make_term(source_text="APITerm2", status="unverified"))

    # POST /terms/flag-needs-review with existing term
    resp = client.post("/api/terms/flag-needs-review", json={
        "source_text": "APITerm2",
        "target_lang": "vi",
        "domain": "technical",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "needs_review"

    # POST /terms/reject with nonexistent term → 404
    resp = client.post("/api/terms/reject", json={
        "source_text": "NoSuchTerm",
        "target_lang": "vi",
        "domain": "technical",
    })
    assert resp.status_code == 404

    # POST /terms/flag-needs-review with nonexistent term → 404
    resp = client.post("/api/terms/flag-needs-review", json={
        "source_text": "NoSuchTerm",
        "target_lang": "vi",
        "domain": "technical",
    })
    assert resp.status_code == 404

    # GET /terms/export?status=needs_review → 200 (no error)
    resp = client.get("/api/terms/export?status=needs_review")
    assert resp.status_code == 200

    # GET /terms/export?status=rejected → 200 (no error)
    resp = client.get("/api/terms/export?status=rejected")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# AC-8: LLM confidence cap in term_extractor.py
# ---------------------------------------------------------------------------

def test_llm_confidence_cap():
    """LLM-extracted confidence must be capped at _LLM_CONFIDENCE_CAP (0.85)."""
    assert _LLM_CONFIDENCE_CAP == 0.85

    # Test _parse_translation_response (happy path)
    raw = '{"translations": [{"source": "Pin", "target": "chân", "confidence": 1.0}]}'
    result = _parse_translation_response(raw)
    assert len(result) == 1
    assert result[0]["confidence"] <= 0.85, (
        f"confidence should be capped at 0.85, got {result[0]['confidence']}"
    )

    # Test _parse_translation_response (fallback path with surrounding text)
    raw_fallback = 'Output:\n{"translations": [{"source": "SMD", "target": "linh kiện SMD", "confidence": 1.0}]}'
    result2 = _parse_translation_response(raw_fallback)
    assert len(result2) == 1
    assert result2[0]["confidence"] <= 0.85

    # Test that a sub-cap value is NOT altered
    raw_low = '{"translations": [{"source": "Flux", "target": "chất hàn", "confidence": 0.7}]}'
    result3 = _parse_translation_response(raw_low)
    assert len(result3) == 1
    assert result3[0]["confidence"] == 0.7, (
        f"confidence below cap should remain unchanged, got {result3[0]['confidence']}"
    )

    # Test that run_phase0_multi inline path also caps (via TermExtractor.translate_unknown)
    extractor = TermExtractor()
    mock_response = '{"translations": [{"source": "Pin", "target": "chân", "confidence": 1.0}]}'
    with patch.object(extractor, "_call", return_value=mock_response):
        translations = extractor.translate_unknown(
            [{"term": "Pin", "context": ""}], "zh", "vi", "technical"
        )
    assert len(translations) == 1
    assert translations[0]["confidence"] <= 0.85
