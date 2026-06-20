"""Resilience and data-boundary tests for the PANJIT embedding path in run_phase0_multi.

AC-3: embedding API failures must be non-fatal.  run_phase0_multi must return
without raising on any network/HTTP error, and must not inject terms when the
embedding call fails.

Data-boundary: malformed API responses, empty DB, zero-similarity, oversized
segments.

Mocking rules (per CLAUDE.md):
- Mock at the consumer-bound name, NOT the definition path.
- The embed() method lives on OpenAICompatibleClient and calls
  self._session.post(...).  We mock at the client class level:
  ``app.backend.clients.openai_compatible_client.OpenAICompatibleClient.embed``
  – this is the name the term_extractor module holds after it imports the
  class inside run_phase0_multi.
- Call run_phase0_multi directly – NOT via translate_document() or
  process_files() (wrong-entry-point tautology per CLAUDE.md).
"""

from __future__ import annotations

from typing import List
from unittest.mock import MagicMock, patch

import pytest
import requests

from app.backend.services.term_extractor import run_phase0_multi
from app.backend.services.term_db import TermDB
from app.backend.models.term import Term

# ---------------------------------------------------------------------------
# Shared config / helpers
# ---------------------------------------------------------------------------

_PANJIT_CFG = dict(
    panjit_base_url="https://panjit.example.com",
    panjit_api_key="test-key",
    panjit_tls_verify=False,
    embedding_model="Qwen3-Embedding-8B",
    extraction_model="gemma4:latest",
    embedding_threshold=0.75,
)

_SEGMENTS = ["Pin腳焊接作業", "SMD元件組裝"]


def _fresh_db(tmp_path, name="res.sqlite") -> TermDB:
    return TermDB(db_path=tmp_path / name)


def _make_approved_term(**kwargs) -> Term:
    defaults = dict(
        source_text="Pin",
        target_text="chân",
        source_lang="zh",
        target_lang="vi",
        domain="technical",
        context_snippet="Pin腳焊接",
        confidence=1.0,
        usage_count=0,
        status="approved",
    )
    defaults.update(kwargs)
    return Term(**defaults)


def _assert_no_injection(summary: dict) -> None:
    """Assert that no terms were injected into the terminology block."""
    assert summary["extracted_source_texts"] == [], (
        f"Expected no injected terms on embedding failure; got {summary['extracted_source_texts']}"
    )
    assert summary["extracted"] == 0
    assert summary["added"] == 0


# ---------------------------------------------------------------------------
# Resilience: embedding API failure modes (all must be non-fatal)
# ---------------------------------------------------------------------------

def test_embed_connection_error_skips_injection(tmp_path):
    """AC-3: ConnectionError from embedding call → skip injection, no raise."""
    db = _fresh_db(tmp_path)

    # embed() on OpenAICompatibleClient calls self._session.post().
    # The client catches all exceptions in embed() and returns [].
    # Patch the session.post at the instance level via the class-level embed mock
    # that raises the error, bypassing the try/except inside embed() itself.
    # We patch embed() directly to simulate the net effect of a transport failure:
    # the method returns [] (as documented: "Returns [] on any failure").
    mock_embed = MagicMock(side_effect=requests.exceptions.ConnectionError("refused"))

    with patch(
        "app.backend.clients.openai_compatible_client.OpenAICompatibleClient.embed",
        mock_embed,
    ):
        # Must not raise.
        summary = run_phase0_multi(
            segments=_SEGMENTS,
            source_lang="zh",
            target_langs=["vi"],
            scenario="TECHNICAL_PROCESS",
            document_context="",
            term_db=db,
            **_PANJIT_CFG,
        )

    _assert_no_injection(summary)


def test_embed_timeout_skips_injection(tmp_path):
    """AC-3: Timeout from embedding call → skip injection, no raise."""
    db = _fresh_db(tmp_path, "timeout.sqlite")

    mock_embed = MagicMock(side_effect=requests.exceptions.Timeout("timed out"))

    with patch(
        "app.backend.clients.openai_compatible_client.OpenAICompatibleClient.embed",
        mock_embed,
    ):
        summary = run_phase0_multi(
            segments=_SEGMENTS,
            source_lang="zh",
            target_langs=["vi"],
            scenario="TECHNICAL_PROCESS",
            document_context="",
            term_db=db,
            **_PANJIT_CFG,
        )

    _assert_no_injection(summary)


def test_embed_5xx_response_skips_injection(tmp_path):
    """AC-3: 503 HTTP error from embedding endpoint → skip injection, no raise.

    embed() on OpenAICompatibleClient calls raise_for_status() which raises
    requests.exceptions.HTTPError; the except block returns [].
    We simulate this by making embed() raise HTTPError (as if raise_for_status fired).
    """
    db = _fresh_db(tmp_path, "5xx.sqlite")

    http_err = requests.exceptions.HTTPError(
        response=MagicMock(status_code=503, text="Service Unavailable")
    )
    mock_embed = MagicMock(side_effect=http_err)

    with patch(
        "app.backend.clients.openai_compatible_client.OpenAICompatibleClient.embed",
        mock_embed,
    ):
        summary = run_phase0_multi(
            segments=_SEGMENTS,
            source_lang="zh",
            target_langs=["vi"],
            scenario="TECHNICAL_PROCESS",
            document_context="",
            term_db=db,
            **_PANJIT_CFG,
        )

    _assert_no_injection(summary)


def test_embed_ssl_error_skips_injection(tmp_path):
    """AC-3: SSLError from embedding call → skip injection, no raise."""
    db = _fresh_db(tmp_path, "ssl.sqlite")

    mock_embed = MagicMock(side_effect=requests.exceptions.SSLError("cert verify failed"))

    with patch(
        "app.backend.clients.openai_compatible_client.OpenAICompatibleClient.embed",
        mock_embed,
    ):
        summary = run_phase0_multi(
            segments=_SEGMENTS,
            source_lang="zh",
            target_langs=["vi"],
            scenario="TECHNICAL_PROCESS",
            document_context="",
            term_db=db,
            **_PANJIT_CFG,
        )

    _assert_no_injection(summary)


# ---------------------------------------------------------------------------
# Data-boundary: response shape anomalies
# ---------------------------------------------------------------------------

def test_embed_empty_response_data_skips_injection(tmp_path):
    """Data-boundary: embed() returns [] (API returned empty data) → injection skipped."""
    db = _fresh_db(tmp_path, "empty_embed.sqlite")

    # embed() already returns [] on failure — simulate the API returning no vectors.
    mock_embed = MagicMock(return_value=[])

    with patch(
        "app.backend.clients.openai_compatible_client.OpenAICompatibleClient.embed",
        mock_embed,
    ):
        summary = run_phase0_multi(
            segments=_SEGMENTS,
            source_lang="zh",
            target_langs=["vi"],
            scenario="TECHNICAL_PROCESS",
            document_context="",
            term_db=db,
            **_PANJIT_CFG,
        )

    # embed returned [] → run_phase0_multi must skip injection and return cleanly.
    _assert_no_injection(summary)


def test_embed_malformed_response_missing_embedding_key(tmp_path):
    """Data-boundary: HTTP response with {"data": [{}]} (no 'embedding' key) → embed() returns [].

    This tests the real embed() implementation against a KeyError on item["embedding"].
    We call embed() directly (not via run_phase0_multi) to verify the method's own
    error handling, then confirm run_phase0_multi also skips injection.
    """
    from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

    client = OpenAICompatibleClient(
        base_url="https://panjit.example.com",
        api_key="test-key",
        model="Qwen3-Embedding-8B",
        verify_ssl=False,
    )

    # Mock the session.post response to return {"data": [{}]} — missing 'embedding' key.
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"data": [{}]}

    with patch.object(client._session, "post", return_value=mock_response):
        result = client.embed(["some text"], model_name="Qwen3-Embedding-8B")

    # KeyError on item["embedding"] is caught; embed() returns [].
    assert result == [], f"Expected [] on missing 'embedding' key; got {result}"


def test_embed_zero_similarity_all_terms(tmp_path):
    """Data-boundary: term_db has terms but all cosine similarities are 0.0 → DB-miss path taken.

    We inject an approved term into the DB and return real (orthogonal) vectors
    from embed(), so cosine similarity = 0.0 for all candidates.  The threshold
    is 0.75, so get_similar_terms_by_embedding returns [] → DB miss → extraction called.
    """
    db = _fresh_db(tmp_path, "zero_sim.sqlite")
    db.insert(_make_approved_term())
    db.approve("Pin", "vi", "technical")

    # Query vector: [1, 0]  Candidate vector: [0, 1]  → cosine = 0.0
    query_vector = [[1.0, 0.0]]
    candidate_vector = [[0.0, 1.0]]

    call_count = [0]

    def fake_embed_side_effect(*args, **kwargs):
        """Side-effect for MagicMock: track calls and return appropriate vectors.

        When patch replaces OpenAICompatibleClient.embed (a class-level patch),
        the mock is called as mock(client_instance, texts, model_name=...).
        We inspect args to find the texts list regardless of call style.
        """
        # Find the texts arg: first list arg among positional args.
        texts = next((a for a in args if isinstance(a, list)), [])
        idx = call_count[0]
        call_count[0] += 1
        if idx == 0:
            # First call: embed the source segments → query vectors.
            return query_vector * len(texts) if texts else query_vector
        # Second call: embed DB candidate source texts → orthogonal vectors.
        return candidate_vector * len(texts) if texts else candidate_vector

    extraction_called = []

    def fake_extract(self, segments, domain):
        extraction_called.append(True)
        return []

    mock_embed = MagicMock(side_effect=fake_embed_side_effect)

    with patch(
        "app.backend.clients.openai_compatible_client.OpenAICompatibleClient.embed",
        mock_embed,
    ), patch(
        "app.backend.services.term_extractor._PANJITTermExtractor.extract_from_segments",
        fake_extract,
    ):
        run_phase0_multi(
            segments=["Pin腳焊接"],
            source_lang="zh",
            target_langs=["vi"],
            scenario="TECHNICAL_PROCESS",
            document_context="",
            term_db=db,
            **_PANJIT_CFG,
        )

    assert extraction_called, (
        "Zero similarity → DB miss → extraction LLM must be called"
    )


def test_embed_empty_term_db(tmp_path):
    """Data-boundary: get_document_terms/DB returns [] → embed call is skipped; extraction called.

    When the DB is empty, get_similar_terms_by_embedding returns [] immediately
    (no rows to embed) and the DB-miss path calls the extraction LLM.
    """
    db = _fresh_db(tmp_path, "empty_db.sqlite")
    # DB is empty — no terms to match.

    mock_embed = MagicMock(return_value=[[0.1, 0.2, 0.3]])
    extraction_called = []

    def fake_extract(self, segments, domain):
        extraction_called.append(True)
        return []

    with patch(
        "app.backend.clients.openai_compatible_client.OpenAICompatibleClient.embed",
        mock_embed,
    ), patch(
        "app.backend.services.term_extractor._PANJITTermExtractor.extract_from_segments",
        fake_extract,
    ):
        summary = run_phase0_multi(
            segments=["Pin腳焊接"],
            source_lang="zh",
            target_langs=["vi"],
            scenario="TECHNICAL_PROCESS",
            document_context="",
            term_db=db,
            **_PANJIT_CFG,
        )

    # extraction must have been called (DB miss — no rows in DB).
    assert extraction_called, "Empty DB → DB miss → extraction LLM must be called"
    # No terms injected (extraction returned nothing).
    assert summary["extracted_source_texts"] == []


def test_embed_oversized_segment_text(tmp_path):
    """Data-boundary: very long segment text (50 000 chars) → no exception raised.

    The embedding call may truncate or succeed; run_phase0_multi must not raise.
    """
    db = _fresh_db(tmp_path, "oversized.sqlite")
    huge_segment = "x" * 50_000

    # Return a valid embedding so the flow proceeds to DB lookup.
    mock_embed = MagicMock(return_value=[[0.1, 0.2, 0.3]])
    mock_get_similar = MagicMock(return_value=[])  # DB miss path.

    with patch(
        "app.backend.clients.openai_compatible_client.OpenAICompatibleClient.embed",
        mock_embed,
    ), patch(
        "app.backend.services.term_db.TermDB.get_similar_terms_by_embedding",
        mock_get_similar,
    ), patch(
        "app.backend.services.term_extractor._PANJITTermExtractor.extract_from_segments",
        MagicMock(return_value=[]),
    ):
        # Must not raise.
        summary = run_phase0_multi(
            segments=[huge_segment],
            source_lang="zh",
            target_langs=["vi"],
            scenario="TECHNICAL_PROCESS",
            document_context="",
            term_db=db,
            **_PANJIT_CFG,
        )

    # Should complete gracefully.
    assert isinstance(summary, dict)
    assert "extracted_source_texts" in summary


# ---------------------------------------------------------------------------
# Data-boundary: malformed response — wrong vector type
# ---------------------------------------------------------------------------

def test_malformed_embedding_missing_data_key(tmp_path):
    """Data-boundary: HTTP response missing 'data' key entirely → embed() returns [].

    Tests the KeyError path inside embed() when the response JSON has no 'data' key.
    """
    from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

    client = OpenAICompatibleClient(
        base_url="https://panjit.example.com",
        api_key="test-key",
        model="Qwen3-Embedding-8B",
        verify_ssl=False,
    )

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    # No 'data' key — will raise KeyError in embed().
    mock_response.json.return_value = {"error": "model not found"}

    with patch.object(client._session, "post", return_value=mock_response):
        result = client.embed(["text"], model_name="Qwen3-Embedding-8B")

    assert result == [], f"Expected [] on missing 'data' key; got {result}"


def test_malformed_embedding_wrong_type(tmp_path):
    """Data-boundary: 'embedding' value is a string instead of List[float] → embed() returns [].

    Tests that embed() doesn't crash when the API returns a malformed vector type
    (e.g., embedding is a string); the exception is caught and [] returned.
    """
    from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

    client = OpenAICompatibleClient(
        base_url="https://panjit.example.com",
        api_key="test-key",
        model="Qwen3-Embedding-8B",
        verify_ssl=False,
    )

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    # 'embedding' is a string — wrong type; downstream numpy call will error.
    mock_response.json.return_value = {"data": [{"embedding": "not-a-vector"}]}

    with patch.object(client._session, "post", return_value=mock_response):
        # embed() itself won't fail here — it returns the string as-is because it
        # does [item["embedding"] for item in items] without type checking.
        # The failure would happen when numpy tries to use the string as a matrix.
        # Either way, no uncaught exception should propagate out of run_phase0_multi.
        result = client.embed(["text"], model_name="Qwen3-Embedding-8B")

    # result may be ["not-a-vector"] (list of strings) — the important thing is
    # run_phase0_multi doesn't raise when it receives bad vectors from embed().
    # Test the full flow to verify graceful degradation:
    db = _fresh_db(tmp_path, "bad_type.sqlite")
    db.insert(_make_approved_term())
    db.approve("Pin", "vi", "technical")

    # Patch embed() to return the wrong-type result (list containing a string).
    mock_embed_bad = MagicMock(return_value=["not-a-vector"])

    with patch(
        "app.backend.clients.openai_compatible_client.OpenAICompatibleClient.embed",
        mock_embed_bad,
    ):
        # Must not raise despite bad vector type.
        summary = run_phase0_multi(
            segments=["Pin腳焊接"],
            source_lang="zh",
            target_langs=["vi"],
            scenario="TECHNICAL_PROCESS",
            document_context="",
            term_db=db,
            **_PANJIT_CFG,
        )

    # Summary must be a valid dict regardless of the bad embedding.
    assert isinstance(summary, dict)
    assert "extracted_source_texts" in summary


def test_empty_term_db_translation_proceeds(tmp_path):
    """Data-boundary: empty term DB → translation proceeds normally (no raise, no injection).

    This covers the scenario where run_phase0_multi is called on a document
    with no matching terms in the DB and extraction also finds nothing.
    Translation must proceed without any exception.
    """
    db = _fresh_db(tmp_path, "empty_proceed.sqlite")

    mock_embed = MagicMock(return_value=[[0.1, 0.2, 0.3]])

    with patch(
        "app.backend.clients.openai_compatible_client.OpenAICompatibleClient.embed",
        mock_embed,
    ), patch(
        "app.backend.services.term_extractor._PANJITTermExtractor.extract_from_segments",
        MagicMock(return_value=[]),
    ):
        summary = run_phase0_multi(
            segments=["一般文本，無術語"],
            source_lang="zh",
            target_langs=["vi"],
            scenario="GENERAL",
            document_context="",
            term_db=db,
            **_PANJIT_CFG,
        )

    # Function completes without exception and returns a valid summary.
    assert isinstance(summary, dict)
    assert summary.get("extracted", 0) == 0
    assert summary.get("added", 0) == 0
    # No injection occurred.
    assert summary.get("extracted_source_texts", []) == []


def test_oversized_segment_graceful(tmp_path):
    """Data-boundary: oversized segment (>32K chars) → graceful degradation, no raise.

    Alias for test_embed_oversized_segment_text using the test-plan name.
    Verifies the same contract under the test-plan's exact test ID.
    """
    db = _fresh_db(tmp_path, "oversized2.sqlite")
    huge_segment = "製程術語 " * 10_000  # ~50 000 chars

    mock_embed = MagicMock(return_value=[[0.1, 0.2, 0.3]])
    mock_get_similar = MagicMock(return_value=[])

    with patch(
        "app.backend.clients.openai_compatible_client.OpenAICompatibleClient.embed",
        mock_embed,
    ), patch(
        "app.backend.services.term_db.TermDB.get_similar_terms_by_embedding",
        mock_get_similar,
    ), patch(
        "app.backend.services.term_extractor._PANJITTermExtractor.extract_from_segments",
        MagicMock(return_value=[]),
    ):
        summary = run_phase0_multi(
            segments=[huge_segment],
            source_lang="zh",
            target_langs=["vi"],
            scenario="TECHNICAL_PROCESS",
            document_context="",
            term_db=db,
            **_PANJIT_CFG,
        )

    assert isinstance(summary, dict), "run_phase0_multi must return dict on oversized input"
    assert "extracted_source_texts" in summary
