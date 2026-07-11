"""Tests for the round-based batched critique-loop QE scoring
(batch-critique-qe-scoring).

Entry point: translate_texts() (not translate_document() — unwired per
CLAUDE.md lessons; pattern mirrors tests/test_glossary_enforcement.py /
tests/test_translate_document_parity.py).

Mock boundaries:
- app.backend.services.translation_service.translate_blocks_batch (Phase-1
  translation, consumer-module bound name).
- app.backend.services.translation_service.get_cache (Phase-1 + critique
  ":c" cache).
- app.backend.services.quality_evaluator.load_model / score_blocks — LAZY
  imports inside _batched_critique_adopt / _critique_gate_adopt, so must be
  patched at the DEFINITION module (quality_evaluator), captured at
  collection time (CLAUDE.md mock.patch lesson).

Anti-tautology: every test asserts exact adopted TEXT identity per segment,
exact call args (blocks pairing/order), or exact counter values — never just
"no exception raised" or job completion.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

# Capture the definition module at collection time (immune to reload
# contamination — CLAUDE.md mock.patch lesson).
import app.backend.services.quality_evaluator as _qe_mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(cache_model_key: str = "test-model"):
    client = MagicMock()
    client.cache_model_key = cache_model_key
    return client


# ---------------------------------------------------------------------------
# AC-1: parity — round-based adoption matches a scripted, hand-computed
# strict-greater-than baseline (NOT a diff against the old implementation).
# ---------------------------------------------------------------------------

def test_batched_loop_matches_per_segment_adoption_parity():
    """AC-1: for 3 segments over 2 rounds, the final per-segment adopted text
    must match a hand-computed baseline of the strict-greater-than / tie-
    keeps-draft rule applied independently, round by round, per segment.

    Scripted baseline (computed by hand, not by running the implementation):
      Round 0 scores (draft, revised) per segment:
        A: (0.1, 0.9) -> adopt revised -> A becomes "RevisedA1"
        B: (0.9, 0.1) -> keep draft    -> B stays "Draft B"
        C: (0.5, 0.5) -> tie keeps draft -> C stays "Draft C"
      Round 1 scores (draft, revised) per segment (draft = round-0 result):
        A: (0.9, 0.85) -> keep draft (already "RevisedA1")
        B: (0.2, 0.8)  -> adopt revised -> B becomes "RevisedB2"
        C: (0.6, 0.6)  -> tie keeps draft -> C stays "Draft C"
      Expected final: A="RevisedA1", B="RevisedB2", C="Draft C"
    """
    from app.backend.services.translation_service import translate_texts

    client = _make_client()
    call_counts = {"A": 0, "B": 0, "C": 0}

    def _translate_once_side_effect(prompt, tgt, src_lang):
        for seg in ("A", "B", "C"):
            if f"Source: Seg {seg}" in prompt:
                call_counts[seg] += 1
                return (True, f"Revised{seg}{call_counts[seg]}")
        raise AssertionError(f"Unexpected critique prompt: {prompt!r}")

    client.translate_once.side_effect = _translate_once_side_effect

    round0_scores = [0.1, 0.9, 0.9, 0.1, 0.5, 0.5]  # A draft/revised, B, C
    round1_scores = [0.9, 0.85, 0.2, 0.8, 0.6, 0.6]

    with patch(
        "app.backend.services.translation_service.translate_blocks_batch",
        return_value=[(True, "Draft A"), (True, "Draft B"), (True, "Draft C")],
    ), patch(
        "app.backend.services.translation_service.get_cache", return_value=None,
    ), patch(
        "app.backend.services.translation_service.CRITIQUE_LOOP_ENABLED", True,
    ), patch(
        "app.backend.services.translation_service.CRITIQUE_MAX_ITERATIONS", 2,
    ), patch.object(
        _qe_mod, "load_model", return_value=MagicMock(),
    ), patch.object(
        _qe_mod, "score_blocks", side_effect=[round0_scores, round1_scores],
    ) as mock_sb:
        tmap, _, fail_cnt, stopped = translate_texts(
            texts=["Seg A", "Seg B", "Seg C"],
            targets=["fr"],
            src_lang="en",
            client=client,
        )

    assert not stopped
    assert fail_cnt == 0
    assert tmap[("fr", "Seg A")] == "RevisedA1", (
        f"Segment A: expected round-0 revised adoption; got {tmap[('fr', 'Seg A')]!r}"
    )
    assert tmap[("fr", "Seg B")] == "RevisedB2", (
        f"Segment B: expected round-1 revised adoption; got {tmap[('fr', 'Seg B')]!r}"
    )
    assert tmap[("fr", "Seg C")] == "Draft C", (
        f"Segment C: expected draft kept on ties both rounds; got {tmap[('fr', 'Seg C')]!r}"
    )
    # AC-2: exactly one score_blocks() call per round (2 rounds -> 2 calls),
    # never once per segment (which would be 6 calls for 3 segments x 2 rounds).
    assert mock_sb.call_count == 2

    # Guard the index-mapping: verify the exact blocks pairing/order per round.
    round0_blocks = mock_sb.call_args_list[0][0][1]
    assert round0_blocks == [
        ("Seg A", "Draft A"), ("Seg A", "Revised" + "A1"),
        ("Seg B", "Draft B"), ("Seg B", "Revised" + "B1"),
        ("Seg C", "Draft C"), ("Seg C", "Revised" + "C1"),
    ]


# ---------------------------------------------------------------------------
# AC-2: score_blocks() call count is bounded by rounds, not segment count.
# ---------------------------------------------------------------------------

def test_score_blocks_call_count_bounded_by_iterations_not_segment_count():
    """AC-2: with 5 segments and CRITIQUE_MAX_ITERATIONS=3, score_blocks() must
    be called at most 3 times total (once per round), never once per
    (segment, iteration) which would be up to 15 calls."""
    from app.backend.services.translation_service import translate_texts

    client = _make_client()
    client.translate_once.return_value = (True, "revised text")

    segments = [f"Seg {i}" for i in range(5)]
    drafts = [(True, f"Draft {i}") for i in range(5)]

    def _score_side_effect(model, blocks, device="cpu"):
        return [0.5] * len(blocks)  # ties everywhere -> keep draft, deterministic

    with patch(
        "app.backend.services.translation_service.translate_blocks_batch",
        return_value=drafts,
    ), patch(
        "app.backend.services.translation_service.get_cache", return_value=None,
    ), patch(
        "app.backend.services.translation_service.CRITIQUE_LOOP_ENABLED", True,
    ), patch(
        "app.backend.services.translation_service.CRITIQUE_MAX_ITERATIONS", 3,
    ), patch.object(
        _qe_mod, "load_model", return_value=MagicMock(),
    ), patch.object(
        _qe_mod, "score_blocks", side_effect=_score_side_effect,
    ) as mock_sb:
        translate_texts(
            texts=segments,
            targets=["fr"],
            src_lang="en",
            client=client,
        )

    assert mock_sb.call_count <= 3, (
        f"Expected score_blocks call_count bounded by CRITIQUE_MAX_ITERATIONS=3 "
        f"(not per-segment), got {mock_sb.call_count}"
    )
    assert mock_sb.call_count == 3, (
        "All 3 rounds should run (no early exit) since every segment stays active"
    )
    # Every call must batch all 5 segments' pairs (10 blocks), never one segment
    # at a time.
    for call in mock_sb.call_args_list:
        blocks = call[0][1]
        assert len(blocks) == 10, f"Expected 10 blocks (5 segments x 2) per round call, got {len(blocks)}"


# ---------------------------------------------------------------------------
# AC-3 (integration): tie keeps draft inside a batched multi-segment round.
# ---------------------------------------------------------------------------

def test_tie_score_keeps_draft_in_batched_round():
    """AC-3: in a batched round scoring 2 segments, a tie for one segment must
    keep its draft while the other segment (clear win) adopts its revision —
    proving the tie rule survives batching alongside a non-tie neighbor."""
    from app.backend.services.translation_service import translate_texts

    client = _make_client()

    def _translate_once_side_effect(prompt, tgt, src_lang):
        if "Source: Tie Seg" in prompt:
            return (True, "Revised Tie")
        if "Source: Win Seg" in prompt:
            return (True, "Revised Win")
        raise AssertionError(f"Unexpected prompt: {prompt!r}")

    client.translate_once.side_effect = _translate_once_side_effect

    # blocks order: Tie Seg (draft, revised), Win Seg (draft, revised)
    scores = [0.8, 0.8, 0.2, 0.9]

    with patch(
        "app.backend.services.translation_service.translate_blocks_batch",
        return_value=[(True, "Draft Tie"), (True, "Draft Win")],
    ), patch(
        "app.backend.services.translation_service.get_cache", return_value=None,
    ), patch(
        "app.backend.services.translation_service.CRITIQUE_LOOP_ENABLED", True,
    ), patch(
        "app.backend.services.translation_service.CRITIQUE_MAX_ITERATIONS", 1,
    ), patch.object(
        _qe_mod, "load_model", return_value=MagicMock(),
    ), patch.object(
        _qe_mod, "score_blocks", return_value=scores,
    ):
        tmap, _, _, _ = translate_texts(
            texts=["Tie Seg", "Win Seg"],
            targets=["fr"],
            src_lang="en",
            client=client,
        )

    assert tmap[("fr", "Tie Seg")] == "Draft Tie", "Tie must keep draft (BR-89)"
    assert tmap[("fr", "Win Seg")] == "Revised Win", "Clear win must adopt revised"


# ---------------------------------------------------------------------------
# AC-4: cached (":c") segments are excluded from every round's batch.
# ---------------------------------------------------------------------------

def test_cached_segments_excluded_from_round_batch():
    """AC-4: a segment already critiqued (":c" cache hit) must never enter any
    round's revision/score batch — verified by both its unchanged tmap value
    AND its absence from the score_blocks() blocks argument."""
    from app.backend.services.translation_service import translate_texts

    client = _make_client()

    def _translate_once_side_effect(prompt, tgt, src_lang):
        assert "Seg B" not in prompt, (
            f"Cached segment 'Seg B' must never be revised: {prompt!r}"
        )
        if "Source: Seg A" in prompt:
            return (True, "Revised A")
        raise AssertionError(f"Unexpected prompt: {prompt!r}")

    client.translate_once.side_effect = _translate_once_side_effect

    cache = MagicMock()

    def _get_batch_side_effect(texts, tgt, src_lang, model_key):
        if model_key.endswith(":c"):
            if "Seg B" in texts:
                return {"Seg B": "Cached Critiqued B"}
            return {}
        return {}  # no Phase-1 cache hits

    cache.get_batch.side_effect = _get_batch_side_effect

    with patch(
        "app.backend.services.translation_service.translate_blocks_batch",
        return_value=[(True, "Draft A"), (True, "Draft B")],
    ), patch(
        "app.backend.services.translation_service.get_cache", return_value=cache,
    ), patch(
        "app.backend.services.translation_service.CRITIQUE_LOOP_ENABLED", True,
    ), patch(
        "app.backend.services.translation_service.CRITIQUE_MAX_ITERATIONS", 1,
    ), patch.object(
        _qe_mod, "load_model", return_value=MagicMock(),
    ), patch.object(
        _qe_mod, "score_blocks", return_value=[0.1, 0.9],
    ) as mock_sb:
        tmap, _, _, _ = translate_texts(
            texts=["Seg A", "Seg B"],
            targets=["fr"],
            src_lang="en",
            client=client,
        )

    assert tmap[("fr", "Seg B")] == "Cached Critiqued B", (
        "Cached segment's value must come from the ':c' cache, untouched by any round"
    )
    assert tmap[("fr", "Seg A")] == "Revised A"

    # Only Seg A's pair enters the batch (2 blocks), never Seg B's.
    assert mock_sb.call_count == 1
    blocks = mock_sb.call_args[0][1]
    assert blocks == [("Seg A", "Draft A"), ("Seg A", "Revised A")]


# ---------------------------------------------------------------------------
# AC-5: per-segment exception isolation within a round.
# ---------------------------------------------------------------------------

def test_segment_exception_in_round_does_not_abort_other_segments():
    """AC-5: one segment's revision-generation exception must not prevent
    other segments in the same round from being revised, scored, and adopted."""
    from app.backend.services.translation_service import translate_texts

    client = _make_client()

    def _translate_once_side_effect(prompt, tgt, src_lang):
        if "Source: Bad Seg" in prompt:
            raise RuntimeError("LLM blew up for this segment only")
        if "Source: Good Seg" in prompt:
            return (True, "Revised Good")
        raise AssertionError(f"Unexpected prompt: {prompt!r}")

    client.translate_once.side_effect = _translate_once_side_effect

    with patch(
        "app.backend.services.translation_service.translate_blocks_batch",
        return_value=[(True, "Draft Bad"), (True, "Draft Good")],
    ), patch(
        "app.backend.services.translation_service.get_cache", return_value=None,
    ), patch(
        "app.backend.services.translation_service.CRITIQUE_LOOP_ENABLED", True,
    ), patch(
        "app.backend.services.translation_service.CRITIQUE_MAX_ITERATIONS", 1,
    ), patch.object(
        _qe_mod, "load_model", return_value=MagicMock(),
    ), patch.object(
        _qe_mod, "score_blocks", return_value=[0.1, 0.9],
    ) as mock_sb:
        tmap, _, fail_cnt, stopped = translate_texts(
            texts=["Bad Seg", "Good Seg"],
            targets=["fr"],
            src_lang="en",
            client=client,
        )

    assert not stopped
    assert fail_cnt == 0
    # Bad Seg keeps its draft (its own exception isolated it from the batch).
    assert tmap[("fr", "Bad Seg")] == "Draft Bad"
    # Good Seg still got revised, scored, and adopted despite Bad Seg's exception.
    assert tmap[("fr", "Good Seg")] == "Revised Good"
    # Only Good Seg's pair should have entered the batch.
    assert mock_sb.call_count == 1
    blocks = mock_sb.call_args[0][1]
    assert blocks == [("Good Seg", "Draft Good"), ("Good Seg", "Revised Good")]


def test_segment_timeout_in_round_does_not_abort_other_segments():
    """AC-5: one segment's revision call exceeding CRITIQUE_TIMEOUT_SECONDS
    must keep its draft and NOT enter the round's batch, while other segments
    proceed normally (revised/scored/adopted) in the same round."""
    from app.backend.services.translation_service import translate_texts

    client = _make_client()

    def _translate_once_side_effect(prompt, tgt, src_lang):
        if "Source: Slow Seg" in prompt:
            time.sleep(0.15)  # exceeds the patched CRITIQUE_TIMEOUT_SECONDS
            return (True, "Revised Slow")
        if "Source: Fast Seg" in prompt:
            return (True, "Revised Fast")
        raise AssertionError(f"Unexpected prompt: {prompt!r}")

    client.translate_once.side_effect = _translate_once_side_effect

    with patch(
        "app.backend.services.translation_service.translate_blocks_batch",
        return_value=[(True, "Draft Slow"), (True, "Draft Fast")],
    ), patch(
        "app.backend.services.translation_service.get_cache", return_value=None,
    ), patch(
        "app.backend.services.translation_service.CRITIQUE_LOOP_ENABLED", True,
    ), patch(
        "app.backend.services.translation_service.CRITIQUE_MAX_ITERATIONS", 1,
    ), patch(
        "app.backend.services.translation_service.CRITIQUE_TIMEOUT_SECONDS", 0.05,
    ), patch.object(
        _qe_mod, "load_model", return_value=MagicMock(),
    ), patch.object(
        _qe_mod, "score_blocks", return_value=[0.1, 0.9],
    ) as mock_sb:
        tmap, _, fail_cnt, stopped = translate_texts(
            texts=["Slow Seg", "Fast Seg"],
            targets=["fr"],
            src_lang="en",
            client=client,
        )

    assert not stopped
    assert fail_cnt == 0
    # Slow Seg keeps its draft (timed out, excluded from the batch).
    assert tmap[("fr", "Slow Seg")] == "Draft Slow"
    # Fast Seg still got revised, scored, and adopted despite Slow Seg's timeout.
    assert tmap[("fr", "Fast Seg")] == "Revised Fast"
    assert mock_sb.call_count == 1
    blocks = mock_sb.call_args[0][1]
    assert blocks == [("Fast Seg", "Draft Fast"), ("Fast Seg", "Revised Fast")]


# ---------------------------------------------------------------------------
# AC-7: CRITIQUE_* config defaults are unchanged by the batching refactor.
# ---------------------------------------------------------------------------

def test_critique_config_defaults_unchanged_after_batching():
    """AC-7: CRITIQUE_LOOP_ENABLED / CRITIQUE_MAX_ITERATIONS /
    CRITIQUE_TIMEOUT_SECONDS defaults are unchanged (true / 3 / 60.0) — the
    batching refactor must not alter any config default."""
    import os
    from importlib import reload

    prev = {
        k: os.environ.pop(k, None)
        for k in ("CRITIQUE_LOOP_ENABLED", "CRITIQUE_MAX_ITERATIONS", "CRITIQUE_TIMEOUT_SECONDS")
    }
    try:
        import app.backend.config as cfg
        reload(cfg)
        assert cfg.CRITIQUE_LOOP_ENABLED is True, (
            f"CRITIQUE_LOOP_ENABLED default must remain True; got {cfg.CRITIQUE_LOOP_ENABLED}"
        )
        assert cfg.CRITIQUE_MAX_ITERATIONS == 3, (
            f"CRITIQUE_MAX_ITERATIONS default must remain 3; got {cfg.CRITIQUE_MAX_ITERATIONS}"
        )
        assert cfg.CRITIQUE_TIMEOUT_SECONDS == 60.0, (
            f"CRITIQUE_TIMEOUT_SECONDS default must remain 60.0; got {cfg.CRITIQUE_TIMEOUT_SECONDS}"
        )
    finally:
        for k, v in prev.items():
            if v is not None:
                os.environ[k] = v
        reload(cfg)


# ---------------------------------------------------------------------------
# metrics parity (BR-46): critique_loop_invocations / critique_iterations_total
# counters must match the pre-refactor accounting scheme.
# ---------------------------------------------------------------------------

def test_critique_loop_invocation_and_iteration_counters_match_baseline():
    """BR-46: record_critique_loop_invocation() fires exactly once per
    translate_texts() call, and record_critique_iteration(total) receives the
    sum of each segment's successful-revision count across all rounds —
    matching the pre-refactor per-segment accounting scheme exactly.

    Scripted baseline (hand-computed):
      Segment A: round 0 succeeds (iters=1), round 1 raises -> isolated,
                 stops (iters stays 1).
      Segment B: round 0 and round 1 both succeed (iters=2).
      Expected total = 1 + 2 = 3.
    """
    from app.backend.services.translation_service import translate_texts

    client = _make_client()
    a_calls = {"n": 0}

    def _translate_once_side_effect(prompt, tgt, src_lang):
        if "Source: Seg A" in prompt:
            a_calls["n"] += 1
            if a_calls["n"] == 1:
                return (True, "Revised A1")
            raise RuntimeError("Segment A fails starting round 2")
        if "Source: Seg B" in prompt:
            return (True, "Revised B")
        raise AssertionError(f"Unexpected prompt: {prompt!r}")

    client.translate_once.side_effect = _translate_once_side_effect

    def _score_side_effect(model, blocks, device="cpu"):
        return [0.5] * len(blocks)  # ties everywhere; adoption outcome irrelevant here

    with patch(
        "app.backend.services.translation_service.translate_blocks_batch",
        return_value=[(True, "Draft A"), (True, "Draft B")],
    ), patch(
        "app.backend.services.translation_service.get_cache", return_value=None,
    ), patch(
        "app.backend.services.translation_service.CRITIQUE_LOOP_ENABLED", True,
    ), patch(
        "app.backend.services.translation_service.CRITIQUE_MAX_ITERATIONS", 2,
    ), patch.object(
        _qe_mod, "load_model", return_value=MagicMock(),
    ), patch.object(
        _qe_mod, "score_blocks", side_effect=_score_side_effect,
    ), patch(
        "app.backend.services.translation_service.record_critique_loop_invocation"
    ) as mock_invocation, patch(
        "app.backend.services.translation_service.record_critique_iteration"
    ) as mock_iteration:
        translate_texts(
            texts=["Seg A", "Seg B"],
            targets=["fr"],
            src_lang="en",
            client=client,
        )

    mock_invocation.assert_called_once()
    mock_iteration.assert_called_once_with(3)


# ---------------------------------------------------------------------------
# BR-119 (cloud-reasoning-stall-hardening, AC-5): default-off critique-loop
# skip of Phase-1 base-cache-HIT segments, gated by
# config.CRITIQUE_SKIP_CACHED_SEGMENTS. Assertions target the SELECTION of
# which keys enter the round's score_blocks() batch (not merely a count), and
# that an excluded segment's Phase-1 draft is never dropped from tmap.
# ---------------------------------------------------------------------------

def _make_cache_with_phase1_hit(phase1_hits: dict):
    """A fake cache whose Phase-1 (non-":c") get_batch call returns
    `phase1_hits` for any requested text present in the dict, and whose
    critique (":c"-suffixed model key) get_batch call always misses — so the
    only source of "already handled" segments in these tests is the Phase-1
    cache, isolating the BR-119 pre-filter clause from the pre-existing
    ":c" critique-cache clause."""
    cache = MagicMock()

    def _get_batch_side_effect(texts, tgt, src_lang, model_key):
        if model_key.endswith(":c"):
            return {}
        return {t: v for t, v in phase1_hits.items() if t in texts}

    cache.get_batch.side_effect = _get_batch_side_effect
    return cache


def _run_skip_cached_scenario(skip_flag: bool):
    """Seg A is a Phase-1 cache HIT ("Cached Draft A"); Seg B is uncached and
    goes through live translate_blocks_batch. Both are eligible for critique
    revision via client.translate_once."""
    from app.backend.services.translation_service import translate_texts

    client = _make_client()

    def _translate_once_side_effect(prompt, tgt, src_lang):
        if "Source: Seg A" in prompt:
            return (True, "Revised A")
        if "Source: Seg B" in prompt:
            return (True, "Revised B")
        raise AssertionError(f"Unexpected critique prompt: {prompt!r}")

    client.translate_once.side_effect = _translate_once_side_effect
    cache = _make_cache_with_phase1_hit({"Seg A": "Cached Draft A"})

    with patch(
        "app.backend.services.translation_service.translate_blocks_batch",
        return_value=[(True, "Draft B")],  # only Seg B is uncached -> live translate
    ), patch(
        "app.backend.services.translation_service.get_cache", return_value=cache,
    ), patch(
        "app.backend.services.translation_service.CRITIQUE_LOOP_ENABLED", True,
    ), patch(
        "app.backend.services.translation_service.CRITIQUE_MAX_ITERATIONS", 1,
    ), patch(
        "app.backend.config.CRITIQUE_SKIP_CACHED_SEGMENTS", skip_flag,
    ), patch.object(
        _qe_mod, "load_model", return_value=MagicMock(),
    ), patch.object(
        _qe_mod, "score_blocks", return_value=[0.1, 0.9, 0.1, 0.9],
    ) as mock_sb:
        tmap, _done, fail_cnt, stopped = translate_texts(
            texts=["Seg A", "Seg B"],
            targets=["fr"],
            src_lang="en",
            client=client,
        )
    return tmap, mock_sb, fail_cnt, stopped


def test_critique_skip_cached_segments_default_false_every_segment_still_enters_pending_keys():
    """AC-5 (default-off parity): with CRITIQUE_SKIP_CACHED_SEGMENTS left at
    its default (false), the Phase-1 cache-HIT segment (Seg A) still enters
    the critique round's batch exactly like the non-cached segment (Seg B) —
    byte-identical to pre-BR-119 behavior. SELECTION assertion (which keys
    entered), not a count."""
    tmap, mock_sb, fail_cnt, stopped = _run_skip_cached_scenario(skip_flag=False)

    assert not stopped
    assert fail_cnt == 0
    assert mock_sb.call_count == 1
    blocks = mock_sb.call_args[0][1]
    block_keys = {src for src, _draft_or_revised in blocks}
    assert block_keys == {"Seg A", "Seg B"}, (
        f"default-off: BOTH the Phase-1 cache-HIT segment and the live-"
        f"translated segment must enter the critique batch, got {block_keys!r}"
    )
    assert tmap[("fr", "Seg A")] == "Revised A"
    assert tmap[("fr", "Seg B")] == "Revised B"


def test_critique_skip_cached_segments_true_excludes_phase1_cache_hit_keys_from_pending_keys():
    """AC-5 (opt-in selection): with CRITIQUE_SKIP_CACHED_SEGMENTS=true, the
    Phase-1 cache-HIT segment (Seg A) must be EXCLUDED from the round's
    score_blocks() batch while the non-cached segment (Seg B) still enters —
    a SET-membership assertion, not a count (a count alone would not prove
    WHICH key was excluded)."""
    tmap, mock_sb, fail_cnt, stopped = _run_skip_cached_scenario(skip_flag=True)

    assert not stopped
    assert fail_cnt == 0
    assert mock_sb.call_count == 1
    blocks = mock_sb.call_args[0][1]
    block_keys = {src for src, _draft_or_revised in blocks}
    assert block_keys == {"Seg B"}, (
        f"opt-in: the Phase-1 cache-HIT segment must be excluded from the "
        f"critique batch, got {block_keys!r}"
    )
    assert tmap[("fr", "Seg B")] == "Revised B"


def test_critique_skip_cached_segments_true_keeps_excluded_segments_draft_present_in_tmap():
    """AC-5 (no-drop): the excluded Phase-1 cache-HIT segment's draft stays
    present and untouched in tmap — the flag skips CRITIQUE for it, it does
    not remove or blank its translation."""
    tmap, _mock_sb, _fail_cnt, _stopped = _run_skip_cached_scenario(skip_flag=True)

    assert tmap[("fr", "Seg A")] == "Cached Draft A", (
        "an excluded cache-HIT segment's Phase-1 draft must remain present "
        "in tmap, unmodified by the critique loop"
    )
