"""Tests for the context-window-segment-prefix feature (wire-context-segments).

Implements all 11 test functions from test-plan.md:
  AC-1  pure-function  test_build_context_prefix_includes_n_preceding
  AC-1  pure-function  test_build_context_prefix_capped_at_n
  AC-1  wiring         test_prompt_payload_contains_neighbor_text_at_call_boundary
  AC-2  pure-function  test_build_context_prefix_truncated_to_max_chars
  AC-2  pure-function  test_build_context_prefix_truncates_from_oldest_end
  AC-3  pure-function  test_build_context_prefix_zero_n_returns_empty
  AC-3  wiring         test_prompt_payload_has_no_context_prefix_when_n_zero
  AC-4  unit           test_context_prefix_header_not_present_in_translated_output
  AC-5  pure-function  test_build_context_prefix_empty_at_first_segment
  AC-5  pure-function  test_build_context_prefix_uses_available_neighbors_at_last_segment
  AC-6  data-boundary  test_context_constants_are_imported_in_pipeline

Mock boundary: _call_ollama (HTTP boundary) via patch.object on a real
OllamaClient instance.  Never mock translate_once, translate_batch, or
translate_blocks_batch.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from app.backend import config as app_config
from app.backend.clients.ollama_client import OllamaClient
from app.backend.services.context_prompts import build_context_prefix
from app.backend.utils.translation_helpers import translate_blocks_batch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent


def _make_mock_call_ollama():
    """Return (calls_list, side_effect) that captures _call_ollama payloads."""
    calls: list[dict] = []

    def _side_effect(payload, timeout_tuple=None):
        calls.append(dict(payload))
        return (True, "ok")

    return calls, _side_effect


# ---------------------------------------------------------------------------
# AC-1 pure-function tests
# ---------------------------------------------------------------------------

def test_build_context_prefix_includes_n_preceding() -> None:
    """build_context_prefix returns a block containing all n preceding segments."""
    segments = ["Alpha.", "Beta.", "Gamma."]
    result = build_context_prefix(segments, current_idx=2, n_context=2, max_chars=1000)
    assert "Alpha." in result
    assert "Beta." in result
    assert result.startswith("Previous segments — reference only, do NOT translate or repeat:")


def test_build_context_prefix_capped_at_n() -> None:
    """At most n_context predecessors are included, not more."""
    segments = ["S0", "S1", "S2", "S3"]
    # At index 3 with n_context=2: only S1 and S2 should appear, not S0.
    result = build_context_prefix(segments, current_idx=3, n_context=2, max_chars=1000)
    assert "S2" in result
    assert "S1" in result
    assert "S0" not in result


# ---------------------------------------------------------------------------
# AC-1 wiring test
# ---------------------------------------------------------------------------

def test_prompt_payload_contains_neighbor_text_at_call_boundary(monkeypatch) -> None:
    """_call_ollama payload for Segment B. must carry the literal 'Segment A.'
    context via the `system` field — never inside the translatable `prompt`
    (context-prefix-bleed-fix: context moved out of the user payload).

    This is a SELECTION test: asserts the specific adjacent segment text
    appears in the correct channel, not just that some context was added.
    Mock boundary: _call_ollama.
    """
    monkeypatch.setattr(app_config, "CONTEXT_WINDOW_SEGMENTS", 2)
    monkeypatch.setattr(app_config, "CONTEXT_MAX_CHARS", 300)

    client = OllamaClient()
    calls, side_effect = _make_mock_call_ollama()

    with patch.object(client, "_call_ollama", side_effect=side_effect):
        translate_blocks_batch(
            ["Segment A.", "Segment B.", "Segment C."],
            "zh-TW",
            None,
            client,
        )

    # Find the _call_ollama invocation whose prompt contains "Segment B."
    segment_b_calls = [c for c in calls if "Segment B." in c.get("prompt", "")]
    assert segment_b_calls, (
        "No _call_ollama call found with 'Segment B.' in payload['prompt']. "
        "Wiring may be broken."
    )
    # SELECTION assertion: the neighbor text must be in the system channel.
    assert "Segment A." in segment_b_calls[0].get("system", ""), (
        "System field for 'Segment B.' does not contain literal 'Segment A.' context. "
        "Context-channel wiring is broken."
    )
    # Regression guard: neighbor text must NEVER be glued into the translatable prompt.
    assert "Segment A." not in segment_b_calls[0]["prompt"], (
        "Neighbor text leaked into the translatable prompt payload — this is exactly "
        "the context-prefix-bleed regression."
    )


# ---------------------------------------------------------------------------
# AC-2 pure-function tests
# ---------------------------------------------------------------------------

def test_build_context_prefix_truncated_to_max_chars() -> None:
    """Context body length must not exceed max_chars."""
    long_text = "X" * 500
    segments = [long_text, "Target"]
    result = build_context_prefix(segments, current_idx=1, n_context=1, max_chars=50)
    # Strip the header line to measure only the body
    header = "Previous segments — reference only, do NOT translate or repeat:\n"
    assert result.startswith(header)
    body = result[len(header):]
    # The body should be derived from at most 50 chars of the combined context.
    assert len(body.rstrip()) <= 50


def test_build_context_prefix_truncates_from_oldest_end() -> None:
    """When context exceeds max_chars, the OLDEST (leftmost) text is dropped first."""
    oldest = "OLDEST_CONTENT"
    newest = "NEWEST_CONTENT"
    segments = [oldest, newest, "Current"]
    # max_chars=20 — combined "OLDEST_CONTENT\nNEWEST_CONTENT" (30 chars) exceeds it.
    # Truncating from oldest end means the suffix (newest) is kept.
    result = build_context_prefix(segments, current_idx=2, n_context=2, max_chars=20)
    # Newest text must survive; oldest may be partially/fully dropped.
    assert newest[-10:] in result, "Newest predecessor text was unexpectedly truncated."
    # Full oldest text must NOT survive (combined is 30 chars > max 20).
    assert oldest not in result, "Oldest predecessor text should have been truncated."


# ---------------------------------------------------------------------------
# AC-3 pure-function test
# ---------------------------------------------------------------------------

def test_build_context_prefix_zero_n_returns_empty() -> None:
    """n_context=0 must return an empty string (disabled context)."""
    result = build_context_prefix(["A", "B", "C"], current_idx=2, n_context=0, max_chars=300)
    assert result == ""


# ---------------------------------------------------------------------------
# AC-3 wiring test
# ---------------------------------------------------------------------------

def test_prompt_payload_has_no_context_prefix_when_n_zero(monkeypatch) -> None:
    """With CONTEXT_WINDOW_SEGMENTS=0, no prompt should contain the context header."""
    monkeypatch.setattr(app_config, "CONTEXT_WINDOW_SEGMENTS", 0)

    client = OllamaClient()
    calls, side_effect = _make_mock_call_ollama()

    with patch.object(client, "_call_ollama", side_effect=side_effect):
        translate_blocks_batch(
            ["Segment A.", "Segment B.", "Segment C."],
            "zh-TW",
            None,
            client,
        )

    for call in calls:
        assert "Previous segments" not in call.get("prompt", ""), (
            "Context header found in prompt even though CONTEXT_WINDOW_SEGMENTS=0. "
            "The n=0 backward-compat guarantee is broken."
        )
        assert "Previous segments" not in call.get("system", ""), (
            "Context header found in system field even though CONTEXT_WINDOW_SEGMENTS=0. "
            "The n=0 backward-compat guarantee is broken."
        )


# ---------------------------------------------------------------------------
# AC-4 test
# ---------------------------------------------------------------------------

def test_context_prefix_header_not_present_in_translated_output(monkeypatch) -> None:
    """Translated output tuples must not contain the context header string."""
    monkeypatch.setattr(app_config, "CONTEXT_WINDOW_SEGMENTS", 2)
    monkeypatch.setattr(app_config, "CONTEXT_MAX_CHARS", 300)

    client = OllamaClient()
    _, side_effect = _make_mock_call_ollama()

    with patch.object(client, "_call_ollama", side_effect=side_effect):
        results = translate_blocks_batch(
            ["Segment A.", "Segment B.", "Segment C."],
            "zh-TW",
            None,
            client,
        )

    for _ok, translated in results:
        assert "Previous segments — reference only, do NOT translate or repeat:" not in translated, (
            f"Context header leaked into translated output: {translated!r}"
        )


# ---------------------------------------------------------------------------
# AC-5 pure-function tests
# ---------------------------------------------------------------------------

def test_build_context_prefix_empty_at_first_segment() -> None:
    """First segment (current_idx=0) has no predecessors — must return ''."""
    result = build_context_prefix(["A", "B", "C"], current_idx=0, n_context=2, max_chars=300)
    assert result == ""


def test_build_context_prefix_uses_available_neighbors_at_last_segment() -> None:
    """At current_idx=1, only one predecessor exists; n_context=2 is fine (no error)."""
    segments = ["Only_predecessor", "Current"]
    result = build_context_prefix(segments, current_idx=1, n_context=2, max_chars=300)
    # Should include the only available predecessor without IndexError
    assert "Only_predecessor" in result
    assert result.startswith("Previous segments — reference only, do NOT translate or repeat:")


# ---------------------------------------------------------------------------
# AC-6 data-boundary test
# ---------------------------------------------------------------------------

def test_context_constants_are_imported_in_pipeline() -> None:
    """CONTEXT_WINDOW_SEGMENTS must be referenced in app/ outside config.py.

    Positive grep: returncode == 0 means the constant IS wired in the pipeline
    (inverse of the dead-reference pattern used in test_dead_references.py).
    """
    app_dir = str(_REPO_ROOT / "app")
    result = subprocess.run(
        [
            "grep",
            "-r",
            "--include=*.py",
            "--exclude=config.py",
            "CONTEXT_WINDOW_SEGMENTS",
            app_dir,
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "CONTEXT_WINDOW_SEGMENTS not found in app/ (outside config.py). "
        "The constant is still orphaned — wiring is missing.\n"
        f"grep stderr: {result.stderr}"
    )
