"""Tests for TermDB: insert, conflict strategies, export/import."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from app.backend.models.term import Term
from app.backend.services.term_db import TermDB


@pytest.fixture()
def db(tmp_path):
    """Fresh in-memory TermDB using a temp file."""
    return TermDB(db_path=tmp_path / "test.sqlite")


def _make_term(**kwargs) -> Term:
    defaults = dict(
        source_text="Pin",
        target_text="chân",
        source_lang="zh",
        target_lang="vi",
        domain="technical",
        context_snippet="Pin腳焊接",
        confidence=1.0,
        usage_count=0,
    )
    defaults.update(kwargs)
    return Term(**defaults)


# ---------------------------------------------------------------------------
# exists / insert / skip
# ---------------------------------------------------------------------------

def test_insert_and_exists(db):
    t = _make_term()
    result = db.insert(t)
    assert result == "inserted"
    assert db.exists("Pin", "vi", "technical")


def test_skip_duplicate(db):
    t = _make_term()
    db.insert(t)
    result = db.insert(t, strategy="skip")
    assert result == "skipped"


def test_different_domain_coexist(db):
    t1 = _make_term(domain="technical")
    t2 = _make_term(domain="electrical", target_text="chốt")
    db.insert(t1)
    db.insert(t2)
    assert db.exists("Pin", "vi", "technical")
    assert db.exists("Pin", "vi", "electrical")


# ---------------------------------------------------------------------------
# Conflict strategies
# ---------------------------------------------------------------------------

def test_overwrite_strategy(db):
    db.insert(_make_term(confidence=0.7))
    result = db.insert(_make_term(target_text="đinh", confidence=1.0), strategy="overwrite")
    assert result == "overwritten"
    # Approve to make injectable, then verify the new target_text is stored
    db.approve("Pin", "vi", "technical")
    terms = db.get_top_terms("vi", "technical")
    assert terms[0].target_text == "đinh"


def test_merge_higher_confidence_wins(db):
    db.insert(_make_term(confidence=0.5))
    result = db.insert(_make_term(target_text="đinh", confidence=1.0), strategy="merge")
    assert result == "overwritten"
    # Approve to make injectable, then verify the winner target_text
    db.approve("Pin", "vi", "technical")
    terms = db.get_top_terms("vi", "technical")
    assert terms[0].target_text == "đinh"


def test_merge_lower_confidence_keeps_existing(db):
    db.insert(_make_term())
    result = db.insert(_make_term(target_text="đinh", confidence=0.3), strategy="merge")
    assert result == "skipped"
    # Approve to make injectable, then verify the original target_text is preserved
    db.approve("Pin", "vi", "technical")
    terms = db.get_top_terms("vi", "technical")
    assert terms[0].target_text == "chân"


# ---------------------------------------------------------------------------
# get_unknown
# ---------------------------------------------------------------------------

def test_get_unknown_filters_known(db):
    db.insert(_make_term(source_text="Pin"))
    candidates = [{"term": "Pin"}, {"term": "SMD"}]
    unknown = db.get_unknown(candidates, "vi", "technical")
    assert len(unknown) == 1
    assert unknown[0]["term"] == "SMD"


# ---------------------------------------------------------------------------
# increment_usage
# ---------------------------------------------------------------------------

def test_increment_usage(db):
    db.insert(_make_term())
    db.increment_usage("Pin", "vi", "technical")
    db.increment_usage("Pin", "vi", "technical")
    # Approve to make injectable, then verify usage_count via get_top_terms
    db.approve("Pin", "vi", "technical")
    terms = db.get_top_terms("vi", "technical")
    assert terms[0].usage_count == 2


# ---------------------------------------------------------------------------
# get_top_terms ordering
# ---------------------------------------------------------------------------

def test_get_top_terms_ordered_by_usage(db):
    db.insert(_make_term(source_text="SMD", usage_count=5))
    db.insert(_make_term(source_text="Pin", usage_count=1))
    # Approve both to make injectable; ordering should still be by usage_count DESC
    db.approve("SMD", "vi", "technical")
    db.approve("Pin", "vi", "technical")
    terms = db.get_top_terms("vi", "technical")
    assert terms[0].source_text == "SMD"


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_get_stats(db):
    db.insert(_make_term(source_text="Pin", domain="technical"))
    db.insert(_make_term(source_text="SMD", domain="technical"))
    db.insert(_make_term(source_text="ROI", domain="finance", target_lang="en"))
    stats = db.get_stats()
    assert stats["total"] == 3
    assert stats["by_domain"]["technical"] == 2
    assert stats["by_domain"]["finance"] == 1


# ---------------------------------------------------------------------------
# Export / Import round-trip
# ---------------------------------------------------------------------------

def test_json_round_trip(db, tmp_path):
    db.insert(_make_term(source_text="Pin"))
    db.insert(_make_term(source_text="SMD", target_text="linh kiện SMD"))
    out = tmp_path / "export.json"
    db.export_json(out)

    db2 = TermDB(db_path=tmp_path / "import.sqlite")
    counts = db2.import_file(out, strategy="skip")
    assert counts["inserted"] == 2
    assert db2.exists("Pin", "vi", "technical")
    assert db2.exists("SMD", "vi", "technical")


def test_csv_round_trip(db, tmp_path):
    db.insert(_make_term(source_text="切彎腳", target_text="trim & form"))
    out = tmp_path / "export.csv"
    db.export_csv(out)

    db2 = TermDB(db_path=tmp_path / "import2.sqlite")
    counts = db2.import_file(out, strategy="skip")
    assert counts["inserted"] == 1
    assert db2.exists("切彎腳", "vi", "technical")


def test_import_skip_preserves_existing(db, tmp_path):
    db.insert(_make_term(source_text="Pin"))
    out = tmp_path / "export.json"
    db.export_json(out)

    # Modify the exported file to have lower confidence
    with out.open("r") as f:
        data = json.load(f)
    data["terms"][0]["confidence"] = 0.5
    data["terms"][0]["target_text"] = "đinh"
    with out.open("w") as f:
        json.dump(data, f)

    counts = db.import_file(out, strategy="skip")
    assert counts["skipped"] == 1
    # Original should be preserved — use get_approved() since original is unverified;
    # approve first then verify via get_top_terms
    db.approve("Pin", "vi", "technical")
    terms = db.get_top_terms("vi", "technical")
    assert terms[0].confidence == 1.0


# ---------------------------------------------------------------------------
# get_similar_terms_by_embedding (term-extraction-db-first, AC-5/AC-6)
# ---------------------------------------------------------------------------

def test_get_similar_terms_by_embedding_cosine(db):
    """AC-6: cosine path is used; no vector DB; approved term returned above threshold."""
    import numpy as np

    # Insert an approved term.
    t = _make_term(source_text="Pin", status="approved")
    db.insert(t)
    db.approve("Pin", "vi", "technical")

    # Query vector and candidate vector pointing in the same direction → cosine = 1.0.
    query_vectors = [[1.0, 0.0, 0.0]]
    candidate_vector = [1.0, 0.0, 0.0]

    # embed_fn returns the candidate vector for the term text.
    def embed_fn(texts):
        return [candidate_vector for _ in texts]

    hits = db.get_similar_terms_by_embedding(
        query_vectors=query_vectors,
        target_lang="vi",
        domain="technical",
        threshold=0.75,
        embed_fn=embed_fn,
    )

    assert len(hits) == 1
    assert hits[0].source_text == "Pin"


def test_get_similar_terms_by_embedding_below_threshold(db):
    """AC-5: term below threshold is NOT returned."""
    import numpy as np

    t = _make_term(source_text="Pin", status="approved")
    db.insert(t)
    db.approve("Pin", "vi", "technical")

    # Orthogonal vectors → cosine = 0.0 < threshold 0.75.
    query_vectors = [[1.0, 0.0]]
    candidate_vector = [0.0, 1.0]

    def embed_fn(texts):
        return [candidate_vector for _ in texts]

    hits = db.get_similar_terms_by_embedding(
        query_vectors=query_vectors,
        target_lang="vi",
        domain="technical",
        threshold=0.75,
        embed_fn=embed_fn,
    )

    assert hits == []


def test_get_similar_terms_by_embedding_embed_fn_failure(db):
    """AC-3: embed_fn returning [] is treated as non-fatal; returns empty list."""
    t = _make_term(source_text="Pin", status="approved")
    db.insert(t)
    db.approve("Pin", "vi", "technical")

    query_vectors = [[1.0, 0.0]]

    def embed_fn(texts):
        return []  # Simulate embedding failure.

    hits = db.get_similar_terms_by_embedding(
        query_vectors=query_vectors,
        target_lang="vi",
        domain="technical",
        threshold=0.75,
        embed_fn=embed_fn,
    )

    assert hits == []


def test_get_similar_terms_by_embedding_empty_query(db):
    """Empty query_vectors → returns [] without calling embed_fn."""
    t = _make_term(source_text="Pin", status="approved")
    db.insert(t)
    db.approve("Pin", "vi", "technical")

    embed_called = []

    def embed_fn(texts):
        embed_called.append(texts)
        return [[1.0, 0.0] for _ in texts]

    hits = db.get_similar_terms_by_embedding(
        query_vectors=[],
        target_lang="vi",
        domain="technical",
        threshold=0.75,
        embed_fn=embed_fn,
    )

    assert hits == []
    assert embed_called == [], "embed_fn must not be called for empty query_vectors"
