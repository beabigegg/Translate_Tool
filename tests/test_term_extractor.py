"""Tests for TermExtractor prompt parsing helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.backend.services.term_extractor import (
    _parse_json_list,
    _parse_translation_response,
    run_phase0,
    TermExtractor,
    SCENARIO_TO_DOMAIN,
)
from app.backend.services.term_db import TermDB


# ---------------------------------------------------------------------------
# _parse_json_list
# ---------------------------------------------------------------------------

def test_parse_json_list_valid():
    raw = '[{"term": "Pin", "context": "Pin腳焊接"}, {"term": "SMD", "context": "SMD元件"}]'
    result = _parse_json_list(raw)
    assert len(result) == 2
    assert result[0]["term"] == "Pin"


def test_parse_json_list_with_surrounding_text():
    raw = 'Here are the terms:\n[{"term": "Flux", "context": "焊劑"}]\nDone.'
    result = _parse_json_list(raw)
    assert len(result) == 1
    assert result[0]["term"] == "Flux"


def test_parse_json_list_invalid_returns_empty():
    result = _parse_json_list("not json at all")
    assert result == []


# ---------------------------------------------------------------------------
# _parse_translation_response
# ---------------------------------------------------------------------------

def test_parse_translation_response_valid():
    raw = '{"translations": [{"source": "Pin", "target": "chân", "confidence": 0.9}]}'
    result = _parse_translation_response(raw)
    assert len(result) == 1
    assert result[0]["source"] == "Pin"
    assert result[0]["target"] == "chân"
    assert result[0]["confidence"] == 0.9


def test_parse_translation_response_with_surrounding_text():
    raw = 'Output:\n{"translations": [{"source": "SMD", "target": "linh kiện SMD", "confidence": 1.0}]}'
    result = _parse_translation_response(raw)
    assert len(result) == 1


def test_parse_translation_response_invalid_returns_empty():
    result = _parse_translation_response("broken output")
    assert result == []


def test_parse_translation_response_missing_source_skipped():
    raw = '{"translations": [{"target": "chân", "confidence": 0.9}]}'
    result = _parse_translation_response(raw)
    assert result == []


# ---------------------------------------------------------------------------
# SCENARIO_TO_DOMAIN
# ---------------------------------------------------------------------------

def test_scenario_to_domain_mappings():
    assert SCENARIO_TO_DOMAIN["TECHNICAL_PROCESS"] == "technical"
    assert SCENARIO_TO_DOMAIN["BUSINESS_FINANCE"] == "finance"
    assert SCENARIO_TO_DOMAIN["LEGAL_CONTRACT"] == "legal"
    assert SCENARIO_TO_DOMAIN["GENERAL"] == "general"


# ---------------------------------------------------------------------------
# TermExtractor.extract_from_segments (mock Qwen)
# ---------------------------------------------------------------------------

def test_extract_from_segments_deduplicates(tmp_path):
    """Same term appearing in multiple segments should be deduplicated."""
    extractor = TermExtractor()
    mock_response = '[{"term": "Pin", "context": "Pin腳"}, {"term": "SMD", "context": "SMD件"}]'

    with patch.object(extractor, "_call", return_value=mock_response):
        segments = ["段落1", "段落2", "段落3"]
        result = extractor.extract_from_segments(segments, "technical")

    # "Pin" and "SMD" each appear in all 3 segments but should be deduplicated
    terms = {r["term"] for r in result}
    assert "Pin" in terms
    assert "SMD" in terms
    assert len(result) == 2  # deduplicated


def test_extract_from_segments_handles_parse_failure(tmp_path):
    """A segment that returns unparseable JSON should be silently skipped."""
    extractor = TermExtractor()
    responses = ["not json", '[{"term": "Flux", "context": "焊劑"}]']

    call_count = [0]
    def fake_call(prompt):
        r = responses[call_count[0]]
        call_count[0] += 1
        return r

    with patch.object(extractor, "_call", side_effect=fake_call):
        result = extractor.extract_from_segments(["seg1", "seg2"], "technical")

    assert len(result) == 1
    assert result[0]["term"] == "Flux"


# ---------------------------------------------------------------------------
# TermExtractor.translate_unknown (mock Qwen)
# ---------------------------------------------------------------------------

def test_translate_unknown_returns_parsed_results():
    extractor = TermExtractor()
    mock_response = '{"translations": [{"source": "Pin", "target": "chân", "confidence": 0.9}]}'

    with patch.object(extractor, "_call", return_value=mock_response):
        terms = [{"term": "Pin", "context": ""}]
        result = extractor.translate_unknown(terms, "zh", "vi", "technical")

    assert len(result) == 1
    assert result[0]["target"] == "chân"


def test_translate_unknown_empty_input_skips_call():
    extractor = TermExtractor()
    with patch.object(extractor, "_call") as mock_call:
        result = extractor.translate_unknown([], "zh", "vi", "technical")
    mock_call.assert_not_called()
    assert result == []


# ---------------------------------------------------------------------------
# run_phase0 (integration with mock Qwen)
# ---------------------------------------------------------------------------

def test_run_phase0_normal_flow(tmp_path):
    db = TermDB(db_path=tmp_path / "phase0.sqlite")

    extract_response = '[{"term": "Pin", "context": "Pin腳"}]'
    translate_response = '{"translations": [{"source": "Pin", "target": "chân", "confidence": 0.9}]}'
    unload_called = []

    def fake_call(self, prompt):
        if "提取" in prompt or "專有名詞" in prompt:
            return extract_response
        return translate_response

    def fake_unload(self):
        unload_called.append(True)

    with patch.object(TermExtractor, "_call", fake_call), \
         patch.object(TermExtractor, "unload", fake_unload):
        summary = run_phase0(
            segments=["Pin腳焊接作業"],
            source_lang="zh",
            target_lang="vi",
            scenario="TECHNICAL_PROCESS",
            document_context="焊接工站作業指導",
            term_db=db,
        )

    assert summary["extracted"] == 1
    assert summary["added"] == 1
    assert db.exists("Pin", "vi", "technical")
    assert len(unload_called) == 1


def test_run_phase0_failure_does_not_abort(tmp_path):
    """Phase 0 failure should log warning and return gracefully."""
    db = TermDB(db_path=tmp_path / "phase0_fail.sqlite")

    def fake_call(self, prompt):
        raise RuntimeError("Ollama unreachable")

    with patch.object(TermExtractor, "_call", fake_call), \
         patch.object(TermExtractor, "unload", lambda self: None):
        summary = run_phase0(
            segments=["some text"],
            source_lang="zh",
            target_lang="vi",
            scenario="GENERAL",
            document_context="",
            term_db=db,
        )

    # Should return empty summary without raising
    assert summary["extracted"] == 0
    assert summary["added"] == 0


def test_run_phase0_extraction_only_skips_known_terms(tmp_path):
    """Terms already in the DB should be counted as skipped."""
    from app.backend.models.term import Term
    db = TermDB(db_path=tmp_path / "phase0_skip.sqlite")
    db.insert(Term(
        source_text="Pin",
        target_text="chân",
        source_lang="zh",
        target_lang="vi",
        domain="technical",
    ))

    extract_response = '[{"term": "Pin", "context": "Pin腳"}]'

    def fake_call(self, prompt):
        return extract_response

    with patch.object(TermExtractor, "_call", fake_call), \
         patch.object(TermExtractor, "unload", lambda self: None):
        summary = run_phase0(
            segments=["Pin腳焊接"],
            source_lang="zh",
            target_lang="vi",
            scenario="TECHNICAL_PROCESS",
            document_context="",
            term_db=db,
        )

    assert summary["skipped"] >= 1
    assert summary["added"] == 0
