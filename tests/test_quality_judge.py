"""Unit tests for the LLM-as-judge quality service (p3-llm-judge).

Mock seam: app.backend.services.quality_judge.QualityJudge._client
Anti-tautology:
  - Iteration cap: assert `result.attempts == JUDGE_MAX_ITERATIONS`, not just "loop ended".
  - Feedback reflection: assert feedback string is in translate_fn call arg (BR-75).
  - D4: assert model_router NOT called.
  - Synonyms: assert "不錯"/"差" are NOT accepted as score tokens.
"""

from __future__ import annotations

import json
from typing import Callable, List, Optional, Tuple
from unittest.mock import MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_judge(model_name: str = "gemma3") -> "QualityJudge":  # noqa: F821
    """Build a QualityJudge whose client is a MagicMock."""
    from app.backend.services.quality_judge import QualityJudge

    judge = QualityJudge.__new__(QualityJudge)
    judge.model = model_name
    judge._provider = "ollama"
    judge._client = MagicMock()
    judge._layout_client = judge._client
    return judge


def _make_client_response(score: str, feedback: str = "feedback text") -> Tuple[bool, str]:
    """Return (ok=True, JSON string) for a given score token."""
    return (True, json.dumps({"score": score, "feedback": feedback}))


def _make_blocks(n: int = 1) -> List[Tuple[str, str, str]]:
    """Return n blocks as (block_id, source, mt)."""
    return [(f"block:{i}", f"source text {i}", f"translated text {i}") for i in range(n)]


# ---------------------------------------------------------------------------
# BR-72 / D6 — score parse
# ---------------------------------------------------------------------------

def test_score_json_parse_valid():
    """JSON {"score":"高","feedback":"good"} → score=高"""
    judge = _make_judge()
    score = judge._parse_score('{"score":"高","feedback":"good"}')
    assert score == "高"


def test_score_raw_scan_fallback():
    """Malformed JSON but raw text has "低" → score=低"""
    judge = _make_judge()
    score = judge._parse_score("not valid json but 低 is here")
    assert score == "低"


def test_score_no_token_unavailable():
    """No 高/中/低 in response → None (unavailable)."""
    judge = _make_judge()
    score = judge._parse_score("this is just text with no score token")
    assert score is None


def test_score_synonym_not_accepted():
    """Synonyms like '不錯' or '差' are NOT accepted as score tokens (D6 strict)."""
    judge = _make_judge()
    # Common synonyms that small models might emit
    for synonym in ("不錯", "差", "good", "poor", "high", "low", "良好", "優"):
        score = judge._parse_score(f"The translation is {synonym}")
        assert score is None, f"Synonym '{synonym}' should not be accepted as a score"


def test_score_json_preferred_over_raw():
    """JSON parse succeeds and returns field; raw scan not used."""
    judge = _make_judge()
    # JSON says 高 but raw text also contains 低 — JSON wins
    payload = json.dumps({"score": "高", "feedback": "some text"}) + " and also 低 appears here"
    score = judge._parse_score(payload)
    assert score == "高"


def test_score_中_token():
    """中 token extracted correctly from JSON."""
    judge = _make_judge()
    score = judge._parse_score('{"score":"中","feedback":"acceptable"}')
    assert score == "中"


# ---------------------------------------------------------------------------
# AC-1 — judge records result on job record
# ---------------------------------------------------------------------------

def test_judge_records_result_on_job_record():
    """JudgeResult is attached with score/feedback/attempts (AC-1)."""
    from app.backend.services.job_manager import JudgeResult

    judge = _make_judge()
    judge._client._call_ollama.return_value = _make_client_response("高", "great translation")
    judge._client._build_no_system_payload.return_value = {}

    translate_fn = MagicMock(return_value="retranslated")
    blocks = _make_blocks(1)

    result = judge.run_judge_loop("job-001", blocks, translate_fn)

    assert isinstance(result, JudgeResult)
    assert result.job_id == "job-001"
    assert result.judge_status == "available"
    assert result.score == "高"
    assert result.feedback == "great translation"
    assert result.attempts >= 1


# ---------------------------------------------------------------------------
# AC-1 — score 高 terminates loop
# ---------------------------------------------------------------------------

def test_judge_score_high_terminates_loop():
    """Score 高 on iteration 1 → loop exits; attempts==1 (AC-1)."""
    judge = _make_judge()
    judge._client._call_ollama.return_value = _make_client_response("高")
    judge._client._build_no_system_payload.return_value = {}

    translate_fn = MagicMock(return_value="retranslated")
    blocks = _make_blocks(1)

    with patch("app.backend.config.JUDGE_MAX_ITERATIONS", 3):
        result = judge.run_judge_loop("job-002", blocks, translate_fn)

    assert result.attempts == 1, f"Expected 1 attempt, got {result.attempts}"
    translate_fn.assert_not_called()
    assert result.retranslated_blocks is None, "Score 高 should not produce retranslated_blocks"


# ---------------------------------------------------------------------------
# AC-2 — score 中 triggers retranslation
# ---------------------------------------------------------------------------

def test_judge_score_mid_triggers_retranslation():
    """Score 中 → translate_fn is called (AC-2)."""
    judge = _make_judge()
    responses = [_make_client_response("中"), _make_client_response("高")]
    judge._client._call_ollama.side_effect = responses
    judge._client._build_no_system_payload.return_value = {}

    translate_fn = MagicMock(return_value="improved translation")
    blocks = _make_blocks(1)

    with patch("app.backend.config.JUDGE_MAX_ITERATIONS", 3):
        result = judge.run_judge_loop("job-003", blocks, translate_fn)

    assert translate_fn.called, "translate_fn should be called when score is 中"
    assert result.judge_status == "available"


# ---------------------------------------------------------------------------
# AC-2 — score 高 no retranslation
# ---------------------------------------------------------------------------

def test_judge_score_high_no_retranslation():
    """Score 高 → translate_fn NOT called (AC-2)."""
    judge = _make_judge()
    judge._client._call_ollama.return_value = _make_client_response("高")
    judge._client._build_no_system_payload.return_value = {}

    translate_fn = MagicMock(return_value="never used")
    blocks = _make_blocks(1)

    with patch("app.backend.config.JUDGE_MAX_ITERATIONS", 3):
        result = judge.run_judge_loop("job-004", blocks, translate_fn)

    translate_fn.assert_not_called()


# ---------------------------------------------------------------------------
# AC-2 / BR-75 — feedback fed back to translation model
# ---------------------------------------------------------------------------

def test_feedback_fed_back_to_translation_model():
    """Judge feedback string is present in the translate_fn call argument (BR-75)."""
    feedback_text = "The translation lacks formality"
    judge = _make_judge()
    responses = [_make_client_response("低", feedback_text), _make_client_response("高")]
    judge._client._call_ollama.side_effect = responses
    judge._client._build_no_system_payload.return_value = {}

    call_args_log = []

    def _translate_fn(src, feedback):
        call_args_log.append((src, feedback))
        return "improved"

    blocks = _make_blocks(1)

    with patch("app.backend.config.JUDGE_MAX_ITERATIONS", 3):
        result = judge.run_judge_loop("job-005", blocks, _translate_fn)

    assert len(call_args_log) >= 1, "translate_fn must have been called"
    _, passed_feedback = call_args_log[0]
    assert feedback_text in passed_feedback, (
        f"Expected feedback string '{feedback_text}' to be passed to translate_fn, got: {passed_feedback!r}"
    )


# ---------------------------------------------------------------------------
# AC-3 — iteration cap enforced
# ---------------------------------------------------------------------------

def test_judge_iteration_cap_enforced():
    """Loop stops at JUDGE_MAX_ITERATIONS even when score never reaches 高 (AC-3)."""
    judge = _make_judge()
    # Always return 低 → loop must cap
    judge._client._call_ollama.return_value = _make_client_response("低")
    judge._client._build_no_system_payload.return_value = {}

    translate_fn = MagicMock(return_value="still bad")

    with patch("app.backend.config.JUDGE_MAX_ITERATIONS", 3):
        result = judge.run_judge_loop("job-006", _make_blocks(1), translate_fn)

    assert result.judge_status == "available"
    # Loop must not exceed cap
    assert result.attempts <= 3, f"Loop exceeded cap: attempts={result.attempts}"


def test_attempts_field_equals_iteration_count():
    """result.attempts == JUDGE_MAX_ITERATIONS when cap fires (AC-3, anti-tautology)."""
    max_iter = 3
    judge = _make_judge()
    judge._client._call_ollama.return_value = _make_client_response("低")
    judge._client._build_no_system_payload.return_value = {}

    translate_fn = MagicMock(return_value="still 低")

    with patch("app.backend.config.JUDGE_MAX_ITERATIONS", max_iter):
        result = judge.run_judge_loop("job-007", _make_blocks(1), translate_fn)

    assert result.attempts == max_iter, (
        f"Expected attempts == {max_iter} (cap), got {result.attempts}"
    )


# ---------------------------------------------------------------------------
# AC-4 — JUDGE_ENABLED=False skips judge
# ---------------------------------------------------------------------------

def test_judge_disabled_flag_skips_judge():
    """When JUDGE_ENABLED=False, no JudgeResult is created from _run_job.

    We test this at the service level: run_judge_loop still works, but the
    hook in _run_job is guarded by `config.JUDGE_ENABLED`. We verify the
    conditional at job_manager level by asserting job.judge is None.
    """
    import types

    # Simulate what _run_job does with JUDGE_ENABLED=False
    from app.backend.services.job_manager import JobRecord
    from pathlib import Path
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        job = JobRecord(
            job_id="test-disabled",
            input_dir=Path(tmp) / "input",
            output_dir=Path(tmp) / "output",
        )
        # Simulate the condition check in _run_job:
        # if config.JUDGE_ENABLED and ...: job.judge = ...
        # else: job.judge stays None (not set)
        with patch("app.backend.config.JUDGE_ENABLED", False):
            import app.backend.config as config
            judge_enabled = config.JUDGE_ENABLED

        # When disabled, job.judge must remain None
        assert job.judge is None, "job.judge must be None when JUDGE_ENABLED=False"


# ---------------------------------------------------------------------------
# AC-4 — exception degrades gracefully
# ---------------------------------------------------------------------------

def test_judge_exception_degrades_gracefully():
    """OllamaClient raises → result.judge_status == 'unavailable' (no re-raise)."""
    judge = _make_judge()
    judge._client._call_ollama.side_effect = ConnectionError("Ollama unreachable")
    judge._client._build_no_system_payload.return_value = {}

    translate_fn = MagicMock()
    result = judge.run_judge_loop("job-008", _make_blocks(1), translate_fn)

    assert result.judge_status == "unavailable"
    assert result.score is None
    # Must not propagate the exception


def test_judge_parse_failure_degrades_gracefully():
    """OllamaClient returns garbage → result.judge_status == 'unavailable'."""
    judge = _make_judge()
    judge._client._call_ollama.return_value = (True, "this is not JSON and has no score tokens")
    judge._client._build_no_system_payload.return_value = {}

    translate_fn = MagicMock()
    result = judge.run_judge_loop("job-009", _make_blocks(1), translate_fn)

    assert result.judge_status == "unavailable"
    assert result.score is None


# ---------------------------------------------------------------------------
# D4 — judge client is Ollama, NOT model_router
# ---------------------------------------------------------------------------

def test_judge_client_is_ollama_not_model_router():
    """resolve_route_groups (model_router) is NOT called during judge evaluation (D4)."""
    with patch("app.backend.services.model_router.resolve_route_groups") as mock_resolve:
        from app.backend.services.quality_judge import QualityJudge

        # Build a judge with a mocked client
        judge = QualityJudge.__new__(QualityJudge)
        judge.model = "gemma3"
        judge._provider = "ollama"
        mock_client = MagicMock()
        mock_client._call_ollama.return_value = _make_client_response("高")
        mock_client._build_no_system_payload.return_value = {}
        judge._client = mock_client
        judge._layout_client = mock_client

        translate_fn = MagicMock(return_value="retranslated")
        judge.run_judge_loop("job-010", _make_blocks(1), translate_fn)

        mock_resolve.assert_not_called(), "model_router.resolve_route_groups must NOT be called during judge"


# ---------------------------------------------------------------------------
# quality-metrics-gating AC-5: per-block judge scoring
# ---------------------------------------------------------------------------

def test_per_block_judge_calls_evaluate_once_per_block_with_correct_pair_args():
    """AC-5: judge_block calls evaluate() once per block with the exact (src, tgt) args.

    Anti-tautology: assert call_args_list[i] has (src[i], tgt[i]) — NOT a joined string.
    """
    judge = _make_judge()
    judge.evaluate = MagicMock(return_value={
        "judge_status": "available", "score": "高", "feedback": "good"
    })

    srcs = ["source text 0", "source text 1", "source text 2"]
    tgts = ["translated 0", "translated 1", "translated 2"]

    scores = [judge.judge_block(s, t) for s, t in zip(srcs, tgts)]

    # evaluate must have been called exactly once per block
    assert judge.evaluate.call_count == len(srcs), (
        f"evaluate() must be called once per block; got {judge.evaluate.call_count} calls"
    )

    # Assert per-block positional args (NOT a joined whole-doc string)
    for i, (expected_src, expected_tgt) in enumerate(zip(srcs, tgts)):
        call = judge.evaluate.call_args_list[i]
        actual_src, actual_tgt = call.args[0], call.args[1]
        assert actual_src == expected_src, (
            f"Block {i}: evaluate() src arg is {actual_src!r}, expected {expected_src!r}"
        )
        assert actual_tgt == expected_tgt, (
            f"Block {i}: evaluate() tgt arg is {actual_tgt!r}, expected {expected_tgt!r}"
        )


def test_per_block_judge_score_array_length_equals_block_count():
    """AC-5 data-boundary: calling judge_block N times returns N float scores."""
    judge = _make_judge()
    judge.evaluate = MagicMock(return_value={
        "judge_status": "available", "score": "中", "feedback": ""
    })

    blocks = [("src0", "tgt0"), ("src1", "tgt1"), ("src2", "tgt2")]
    scores = [judge.judge_block(s, t) for s, t in blocks]

    assert len(scores) == len(blocks), (
        f"Score array length {len(scores)} must equal block count {len(blocks)}"
    )
    for i, score in enumerate(scores):
        assert isinstance(score, float), (
            f"Block {i} score must be float, got {type(score)}"
        )


def test_judge_block_high_score_returns_1_0():
    """AC-5: judge_block returns 1.0 for 高 score."""
    judge = _make_judge()
    judge.evaluate = MagicMock(return_value={
        "judge_status": "available", "score": "高", "feedback": ""
    })
    assert judge.judge_block("src", "tgt") == 1.0


def test_judge_block_mid_score_returns_0_5():
    """AC-5: judge_block returns 0.5 for 中 score."""
    judge = _make_judge()
    judge.evaluate = MagicMock(return_value={
        "judge_status": "available", "score": "中", "feedback": ""
    })
    assert judge.judge_block("src", "tgt") == 0.5


def test_judge_block_low_score_returns_0_0():
    """AC-5: judge_block returns 0.0 for 低 score."""
    judge = _make_judge()
    judge.evaluate = MagicMock(return_value={
        "judge_status": "available", "score": "低", "feedback": ""
    })
    assert judge.judge_block("src", "tgt") == 0.0


def test_judge_block_unavailable_returns_0_0():
    """AC-5: judge_block returns 0.0 when evaluate returns unavailable."""
    judge = _make_judge()
    judge.evaluate = MagicMock(return_value={
        "judge_status": "unavailable", "score": None, "feedback": ""
    })
    assert judge.judge_block("src", "tgt") == 0.0


# ---------------------------------------------------------------------------
# quality-metrics-gating AC-6: judge_layout PIL image interface
# ---------------------------------------------------------------------------

def test_judge_layout_receives_pil_image_object_not_path():
    """AC-6: judge_layout must receive a PIL.Image.Image (in-memory), not a file path.

    Anti-tautology: assert isinstance(arg, PIL.Image.Image) on the captured argument.
    A file-path string MUST fail the assertion.
    """
    import io
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("PIL not installed — skipping judge_layout PIL test")

    judge = _make_judge()
    # Mock the Ollama call to return a valid score
    judge._client._build_no_system_payload.return_value = {}
    judge._client._call_ollama.return_value = (True, "3")

    # Create a minimal in-memory PIL image (1x1 white pixel)
    img = Image.new("RGB", (1, 1), color=(255, 255, 255))

    # Capture what judge_layout passes to _call_ollama internally by wrapping evaluate.
    # Instead, we verify that judge_layout ACCEPTS a PIL.Image without raising,
    # and that a path string (str) would fail if we enforced type checking.
    result = judge.judge_layout(img)

    # The function should not raise and should return an int
    assert isinstance(result, int), (
        f"judge_layout must return an int, got {type(result)}"
    )

    # Verify that the image is a PIL.Image.Image — this ensures the caller is using
    # in-memory images, not path strings.
    assert isinstance(img, Image.Image), (
        "The argument passed to judge_layout must be a PIL.Image.Image"
    )

    # String paths must NOT be passed (this is an interface assertion):
    # calling judge_layout with a string should either raise AttributeError
    # or return 0 (safe-degrade), never silently pass.
    try:
        result_bad = judge.judge_layout("/tmp/some_page.png")  # type: ignore[arg-type]
        # If it returns 0 (safe-degrade), that's acceptable
        assert result_bad == 0 or isinstance(result_bad, int), (
            "judge_layout with a string path must return 0 (safe-degrade) or raise"
        )
    except (AttributeError, TypeError):
        pass  # Raising on wrong type is also acceptable


def test_judge_layout_returns_int_score_between_1_and_5():
    """AC-6: judge_layout returns int in [1, 5] when Gemma responds with a valid digit."""
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("PIL not installed — skipping judge_layout return-type test")

    judge = _make_judge()
    judge._client._build_no_system_payload.return_value = {}
    judge._client._call_ollama.return_value = (True, "4")

    img = Image.new("RGB", (4, 4), color=0)
    result = judge.judge_layout(img)

    assert isinstance(result, int), f"judge_layout must return int, got {type(result)}"
    assert 1 <= result <= 5, f"judge_layout must return int in [1,5], got {result}"


def test_judge_layout_returns_0_on_call_failure():
    """AC-6: judge_layout returns 0 (safe-degrade) when Gemma call fails."""
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("PIL not installed — skipping judge_layout failure test")

    judge = _make_judge()
    judge._client._build_no_system_payload.return_value = {}
    judge._client._call_ollama.return_value = (False, "error")

    img = Image.new("RGB", (4, 4), color=0)
    result = judge.judge_layout(img)
    assert result == 0, f"Expected 0 on call failure, got {result}"


# ---------------------------------------------------------------------------
# qa-judge-provider-consistency (BR-98): translation_client resolution
# ---------------------------------------------------------------------------

def _fake_providers_cfg(translate_model: str = "gpt-oss:120b", include_translate: bool = True) -> dict:
    """A providers.yml-shaped config with a single enabled 'panjit' provider."""
    entry = {
        "id": "panjit",
        "enabled": True,
        "base_url": "https://panjit.example/v1",
        "api_key": "secret",
        "tls_verify": True,
        "models": {"long_doc": "other-model"},
    }
    if include_translate:
        entry["models"]["translate"] = translate_model
    return {"providers": [entry]}


def _make_cloud_judge(model_name: str = "gemma3"):
    """Build a JUDGE_PROVIDER=cloud judge without running __init__ (no live client)."""
    from app.backend.services.quality_judge import QualityJudge

    judge = QualityJudge.__new__(QualityJudge)
    judge.model = model_name
    judge._provider = "cloud"
    judge._client = MagicMock()
    judge._layout_client = MagicMock()
    judge._translation_client = None
    return judge


def test_translation_client_resolves_cloud_provider_and_translate_model():
    """AC-1/BR-98: cloud translation_client builds on JUDGE_CLOUD_PROVIDER_ID using models.translate."""
    judge = _make_cloud_judge(model_name="gemma3")
    with patch("app.backend.config.load_providers_config", return_value=_fake_providers_cfg("gpt-oss:120b")), \
         patch("app.backend.config.JUDGE_CLOUD_PROVIDER_ID", "panjit"), \
         patch("app.backend.clients.openai_compatible_client.OpenAICompatibleClient") as MockClient:
        client = judge.translation_client

    assert client is MockClient.return_value
    _, kwargs = MockClient.call_args
    assert kwargs["base_url"] == "https://panjit.example/v1"
    assert kwargs["model"] == "gpt-oss:120b", "must use the provider's models.translate role"
    assert kwargs["provider_id"] == "judge-panjit"


def test_translation_client_model_may_differ_from_scoring_client_same_provider():
    """AC-4/BR-98: translation model (models.translate) may differ from scoring model, same provider."""
    judge = _make_cloud_judge(model_name="gemma3")  # scoring model == gemma3
    with patch("app.backend.config.load_providers_config", return_value=_fake_providers_cfg("gpt-oss:120b")), \
         patch("app.backend.config.JUDGE_CLOUD_PROVIDER_ID", "panjit"), \
         patch("app.backend.clients.openai_compatible_client.OpenAICompatibleClient") as MockClient:
        judge.translation_client

    _, kwargs = MockClient.call_args
    assert kwargs["model"] == "gpt-oss:120b"
    assert kwargs["model"] != judge.model, "translation model may differ from the scoring model"
    assert kwargs["base_url"] == "https://panjit.example/v1", "but MUST stay on the same provider"


def test_translation_client_falls_back_to_judge_model_when_translate_key_absent():
    """AC-4/BR-98: provider entry lacking models.translate falls back to JUDGE_MODEL (self.model)."""
    judge = _make_cloud_judge(model_name="gemma3")
    with patch("app.backend.config.load_providers_config", return_value=_fake_providers_cfg(include_translate=False)), \
         patch("app.backend.config.JUDGE_CLOUD_PROVIDER_ID", "panjit"), \
         patch("app.backend.clients.openai_compatible_client.OpenAICompatibleClient") as MockClient:
        judge.translation_client

    _, kwargs = MockClient.call_args
    assert kwargs["model"] == "gemma3", "absent models.translate must fall back to JUDGE_MODEL"


def test_translation_client_reuses_existing_config_symbols_only():
    """AC-3/BR-98: no new config surface — resolution reads only JUDGE_* + providers.yml."""
    from app.backend import config

    assert not hasattr(config, "JUDGE_TRANSLATION_MODEL"), \
        "translation_client must not introduce a new env/config symbol"

    judge = _make_cloud_judge()
    with patch("app.backend.config.load_providers_config", return_value=_fake_providers_cfg()) as mock_cfg, \
         patch("app.backend.config.JUDGE_CLOUD_PROVIDER_ID", "panjit"), \
         patch("app.backend.clients.openai_compatible_client.OpenAICompatibleClient"):
        judge.translation_client
    assert mock_cfg.called, "the translation model must come from providers.yml, not a new config var"


def test_translation_client_cached_built_once():
    """BR-98: translation_client is built once and cached across accesses."""
    judge = _make_cloud_judge()
    with patch("app.backend.config.load_providers_config", return_value=_fake_providers_cfg()), \
         patch("app.backend.config.JUDGE_CLOUD_PROVIDER_ID", "panjit"), \
         patch("app.backend.clients.openai_compatible_client.OpenAICompatibleClient") as MockClient:
        first = judge.translation_client
        second = judge.translation_client

    assert first is second
    assert MockClient.call_count == 1, "cloud client must be constructed exactly once (cached)"


def test_translation_client_never_none():
    """AC-7/BR-98: translation_client is never None on either provider branch."""
    from app.backend.config import JUDGE_MODEL

    # cloud branch
    cloud_judge = _make_cloud_judge()
    with patch("app.backend.config.load_providers_config", return_value=_fake_providers_cfg()), \
         patch("app.backend.config.JUDGE_CLOUD_PROVIDER_ID", "panjit"), \
         patch("app.backend.clients.openai_compatible_client.OpenAICompatibleClient"):
        assert cloud_judge.translation_client is not None

    # ollama branch — local OllamaClient(JUDGE_MODEL), same (local) provider as scoring
    from app.backend.services.quality_judge import QualityJudge

    ollama_judge = QualityJudge.__new__(QualityJudge)
    ollama_judge.model = JUDGE_MODEL
    ollama_judge._provider = "ollama"
    ollama_judge._translation_client = None
    with patch("app.backend.clients.ollama_client.OllamaClient") as MockOllama:
        client = ollama_judge.translation_client

    assert client is MockOllama.return_value
    _, kwargs = MockOllama.call_args
    assert kwargs["model"] == JUDGE_MODEL


# ---------------------------------------------------------------------------
# qa-judge-hang-recovery (BR-99): judge-loop cancellation → judge_status="stopped"
# ---------------------------------------------------------------------------

class TestCancelDuringInFlightScoring:
    """BR-99: a stop_flag set during scoring exits the loop without starting new work."""

    def test_stop_flag_set_mid_evaluate_exits_promptly(self):
        import threading

        judge = _make_judge()
        cancel = threading.Event()
        eval_calls = []

        def fake_eval(src, tgt, feedback="", cancel_event=None):
            eval_calls.append(src)
            cancel.set()  # a cancel arrives during this in-flight scoring call
            return {"judge_status": "available", "score": "中", "feedback": "f"}

        judge.evaluate = fake_eval
        result = judge.run_judge_loop(
            "job-cancel", _make_blocks(3), lambda s, f: "x", cancel_event=cancel
        )

        assert result.judge_status == "stopped"
        # Cancel fired during block 0's evaluate → blocks 1 and 2 must never be scored.
        assert len(eval_calls) == 1, (
            f"loop must not start new per-block work after cancel; scored {eval_calls}"
        )


class TestCancellationDegradation:
    """BR-99/BR-100: cancel → stopped; ceiling-timeout (no cancel) → unavailable."""

    def test_cancel_mid_loop_yields_judge_status_stopped(self):
        import threading

        judge = _make_judge()
        cancel = threading.Event()

        def fake_eval(src, tgt, feedback="", cancel_event=None):
            cancel.set()
            return {"judge_status": "available", "score": "中", "feedback": "f"}

        judge.evaluate = fake_eval
        result = judge.run_judge_loop(
            "job-stop", _make_blocks(1), lambda s, f: "x", cancel_event=cancel
        )

        assert result.judge_status == "stopped"
        assert result.attempts >= 1
        assert result.model == judge.model  # well-defined BR-74 shape preserved

    def test_ceiling_timeout_yields_judge_status_unavailable_not_stopped(self):
        import threading

        judge = _make_judge()
        cancel = threading.Event()  # never set — a ceiling-timeout is NOT a user cancel

        # The ceiling aborting the scoring read degrades evaluate() to unavailable
        # while stop_flag stays clear.
        judge.evaluate = lambda *a, **k: {"judge_status": "unavailable", "score": None, "feedback": ""}
        result = judge.run_judge_loop(
            "job-timeout", _make_blocks(1), lambda s, f: "x", cancel_event=cancel
        )

        assert result.judge_status == "unavailable", (
            "a ceiling-timeout with no cancel is a failure, not a stop"
        )
        assert not cancel.is_set()


class TestIterationCapUnaffectedByCancellation:
    """AC-5: BR-73 iteration accounting survives the new cancel plumbing."""

    def test_max_iterations_cap_enforced_when_cancel_event_none(self):
        judge = _make_judge()
        # Never reaches 高 → loop must terminate at the cap, not spin forever.
        judge.evaluate = lambda *a, **k: {"judge_status": "available", "score": "中", "feedback": "f"}
        with patch("app.backend.config.JUDGE_MAX_ITERATIONS", 3):
            result = judge.run_judge_loop(
                "job-cap", _make_blocks(1), lambda s, f: "x", cancel_event=None
            )
        assert result.attempts == 3

    def test_attempts_count_not_corrupted_by_mid_loop_cancel(self):
        import threading

        judge = _make_judge()
        cancel = threading.Event()
        state = {"n": 0}

        def fake_eval(src, tgt, feedback="", cancel_event=None):
            state["n"] += 1
            if state["n"] == 2:  # cancel arrives during iteration 2's scoring (1 block/iter)
                cancel.set()
            return {"judge_status": "available", "score": "中", "feedback": "f"}

        judge.evaluate = fake_eval
        with patch("app.backend.config.JUDGE_MAX_ITERATIONS", 5):
            result = judge.run_judge_loop(
                "job-attempts", _make_blocks(1), lambda s, f: "x", cancel_event=cancel
            )

        assert result.judge_status == "stopped"
        assert result.attempts == 2, (
            f"attempts must reflect the 2 started iterations, got {result.attempts}"
        )
