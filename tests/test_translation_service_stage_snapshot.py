"""Integration test: translate_texts()'s widened status_callback emits a
structured current-segment snapshot at each stage transition (translation-
progress-detail-ui, IP-3, AC-1).

Entry point: translate_texts() directly (NOT translate_document() — the
wrong-entry-point anti-tautology guard from CLAUDE.md promoted learnings).

Mock boundary: only the LLM client (`client.translate_once`, patch.object at
collection time via a MagicMock) is faked. CRITIQUE_LOOP_ENABLED/CRITIQUE_MAX_
ITERATIONS/SENTENCE_MODE/QE_ENABLED are plain config toggles (same pattern as
tests/test_critique_loop_batching.py), not internal-helper mocks — the real
round-based critique loop and the real _batched_critique_adopt heuristic
fallback both execute unmocked.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_status_callback_emits_structured_snapshot_at_each_stage_transition():
    from app.backend.services.translation_service import translate_texts

    client = MagicMock()
    client.cache_model_key = "test-model"

    def _translate_once_side_effect(prompt, tgt, src_lang):
        if prompt == "Hello world":
            return (True, "Bonjour le monde")
        if "Review and improve this translation." in prompt:
            return (True, "Bonjour le monde ameliore")
        raise AssertionError(f"unexpected prompt sent to LLM client: {prompt!r}")

    client.translate_once.side_effect = _translate_once_side_effect

    snapshots = []

    def status_callback(message, segment=None):
        snapshots.append((message, segment))

    with patch("app.backend.services.translation_service.SENTENCE_MODE", False), \
         patch("app.backend.services.translation_service.get_cache", return_value=None), \
         patch("app.backend.config.QE_ENABLED", False), \
         patch("app.backend.services.translation_service.CRITIQUE_LOOP_ENABLED", True), \
         patch("app.backend.services.translation_service.CRITIQUE_MAX_ITERATIONS", 1):
        tmap, done, fail_cnt, stopped = translate_texts(
            texts=["Hello world"],
            targets=["fr"],
            src_lang="en",
            client=client,
            status_callback=status_callback,
        )

    assert not stopped
    assert fail_cnt == 0
    assert tmap[("fr", "Hello world")] == "Bonjour le monde ameliore"

    staged = [seg for (_msg, seg) in snapshots if seg is not None]
    stages_seen = [seg.stage for seg in staged]
    assert stages_seen == ["translate", "critique", "qe", "adopt"], (
        f"expected the 4 stage transitions in order, got {stages_seen!r}"
    )

    translate_seg, critique_seg, qe_seg, adopt_seg = staged

    # Stage "translate": the freshly machine-translated draft, pre-critique.
    assert translate_seg.source == "Hello world"
    assert translate_seg.draft == "Bonjour le monde"

    # Stage "critique": about to issue the revision call — draft is still the
    # PRE-revision text (the revision hasn't returned yet at this point).
    assert critique_seg.source == "Hello world"
    assert critique_seg.draft == "Bonjour le monde"

    # Stage "qe": the just-produced revision candidate, about to be scored.
    assert qe_seg.source == "Hello world"
    assert qe_seg.draft == "Bonjour le monde ameliore"

    # Stage "adopt": the decided outcome — revised passes the length-ratio
    # heuristic (QE disabled) so it is adopted.
    assert adopt_seg.source == "Hello world"
    assert adopt_seg.draft == "Bonjour le monde ameliore"
    assert adopt_seg.adopted is True

    # The final call clears status_detail/segment (existing string-message
    # behavior preserved — AC-2 backward compatibility).
    assert snapshots[-1] == (None, None)
