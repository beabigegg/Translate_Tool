"""Tests for the dual-engine STT abstraction (stt_engine.py).

Mock seam: neither qwen_asr nor faster_whisper is installed in this
environment (both are lazy-imported inside function bodies) — mock at the
function-call boundary (app.backend.services.stt_engine._transcribe_qwen3_asr
/ _transcribe_faster_whisper / _load_*_model / _qwen3_asr_infer_chunk),
mirroring tests/test_quality_evaluation.py's load_model mocking convention.

Anti-tautology: assert call_count/call_args on the mocks, not just that
transcribe() returned without erroring.
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

from app.backend.services import stt_engine


# ---------------------------------------------------------------------------
# transcribe() dispatch
# ---------------------------------------------------------------------------

def test_transcribe_dispatches_to_qwen3_asr_by_default(monkeypatch):
    monkeypatch.setattr(stt_engine.config, "STT_ENGINE", "qwen3-asr")
    vad_segments = [(0.0, 1.0)]

    with patch.object(stt_engine, "_transcribe_qwen3_asr") as mock_qwen, \
         patch.object(stt_engine, "_transcribe_faster_whisper") as mock_fw:
        mock_qwen.return_value = []
        stt_engine.transcribe("audio.wav", vad_segments)

    mock_qwen.assert_called_once_with("audio.wav", vad_segments)
    mock_fw.assert_not_called()


def test_transcribe_dispatches_to_faster_whisper_when_configured(monkeypatch):
    monkeypatch.setattr(stt_engine.config, "STT_ENGINE", "faster-whisper")
    vad_segments = [(0.0, 1.0)]

    with patch.object(stt_engine, "_transcribe_qwen3_asr") as mock_qwen, \
         patch.object(stt_engine, "_transcribe_faster_whisper") as mock_fw:
        mock_fw.return_value = []
        stt_engine.transcribe("audio.wav", vad_segments)

    mock_fw.assert_called_once_with("audio.wav", vad_segments)
    mock_qwen.assert_not_called()


def test_transcribe_dispatch_is_case_and_whitespace_normalized_by_config(monkeypatch):
    # config.STT_ENGINE itself lower()/strip()s at load time; transcribe()
    # only ever sees the normalized value — confirm the dispatch condition
    # is an exact-match on that normalized string, not e.g. a substring check
    # that would also match unrelated values.
    monkeypatch.setattr(stt_engine.config, "STT_ENGINE", "qwen3-asr")

    with patch.object(stt_engine, "_transcribe_qwen3_asr") as mock_qwen, \
         patch.object(stt_engine, "_transcribe_faster_whisper") as mock_fw:
        mock_qwen.return_value = []
        stt_engine.transcribe("audio.wav", [])

    mock_qwen.assert_called_once()
    mock_fw.assert_not_called()


# ---------------------------------------------------------------------------
# MOST IMPORTANT: per-segment (not whole-file) language detection
# ---------------------------------------------------------------------------

def test_qwen3_asr_detects_language_independently_per_segment():
    """A recording that switches speaker language mid-file must produce
    TranscriptSegment.language values that differ segment-to-segment, and the
    model must be invoked exactly once per VAD segment (not once for the
    whole file)."""
    vad_segments = [(0.0, 1.0), (1.0, 2.5), (2.5, 4.0)]

    fake_model = object()
    fake_audio = MagicMock(name="full_audio_array")
    fake_chunk = MagicMock(name="audio_chunk")

    infer_results = [
        MagicMock(text="你好", language="zh"),
        MagicMock(text="hello", language="en"),
        MagicMock(text="再見", language="zh"),
    ]

    with patch.object(stt_engine, "_load_qwen3_asr_model", return_value=fake_model) as mock_load, \
         patch.object(stt_engine, "_load_audio", return_value=(fake_audio, 16000)) as mock_load_audio, \
         patch.object(stt_engine, "_slice_chunk", return_value=fake_chunk) as mock_slice, \
         patch.object(stt_engine, "_qwen3_asr_infer_chunk", side_effect=infer_results) as mock_infer:
        segments = stt_engine._transcribe_qwen3_asr("audio.wav", vad_segments)

    assert mock_load.call_count == 1, "model should be loaded once and reused, not per-segment"
    assert mock_load_audio.call_args_list == [call("audio.wav")], (
        "the audio file must be decoded exactly once per transcribe() call, "
        "not re-read from disk for every VAD segment"
    )
    assert mock_infer.call_count == len(vad_segments), (
        f"expected one inference call per VAD segment ({len(vad_segments)}), "
        f"got {mock_infer.call_count}"
    )

    assert len(segments) == 3
    assert [s.language for s in segments] == ["zh", "en", "zh"], (
        "each segment's language must independently match its own detection "
        "result, not be pinned to a single whole-file language"
    )
    assert [s.text for s in segments] == ["你好", "hello", "再見"]

    # Boundaries preserved verbatim from the input VAD windows.
    assert [(s.start, s.end) for s in segments] == vad_segments

    # Confirm each inference call actually corresponds to its own segment's
    # slice of the (once-loaded) audio array (call-wiring, not just three
    # calls in any order).
    assert mock_slice.call_args_list == [
        call(fake_audio, 16000, 0.0, 1.0),
        call(fake_audio, 16000, 1.0, 2.5),
        call(fake_audio, 16000, 2.5, 4.0),
    ]
    for infer_call in mock_infer.call_args_list:
        args, kwargs = infer_call
        assert args[0] is fake_model
        assert args[1] is fake_chunk
        assert kwargs.get("sample_rate", args[2] if len(args) > 2 else None) == 16000


def test_faster_whisper_detects_language_independently_per_segment():
    """Same per-segment-language regression as above, for the faster-whisper
    engine path."""
    vad_segments = [(0.0, 1.0), (1.0, 2.5), (2.5, 4.0)]

    fake_model = MagicMock(name="faster_whisper_model")
    fake_audio = MagicMock(name="full_audio_array")
    fake_chunk = MagicMock(name="audio_chunk")

    def _piece(text):
        p = MagicMock()
        p.text = text
        return p

    info_zh = MagicMock(language="zh")
    info_en = MagicMock(language="en")
    info_zh2 = MagicMock(language="zh")

    fake_model.transcribe.side_effect = [
        (iter([_piece("你好")]), info_zh),
        (iter([_piece("hello")]), info_en),
        (iter([_piece("再見")]), info_zh2),
    ]

    with patch.object(stt_engine, "_load_faster_whisper_model", return_value=fake_model) as mock_load, \
         patch.object(stt_engine, "_load_audio", return_value=(fake_audio, 16000)) as mock_load_audio, \
         patch.object(stt_engine, "_slice_chunk", return_value=fake_chunk) as mock_slice:
        segments = stt_engine._transcribe_faster_whisper("audio.wav", vad_segments)

    assert mock_load.call_count == 1, "model should be loaded once and reused, not per-segment"
    assert mock_load_audio.call_args_list == [call("audio.wav")], (
        "the audio file must be decoded exactly once per transcribe() call, "
        "not re-read from disk for every VAD segment"
    )
    assert fake_model.transcribe.call_count == len(vad_segments), (
        f"expected one inference call per VAD segment ({len(vad_segments)}), "
        f"got {fake_model.transcribe.call_count}"
    )

    assert len(segments) == 3
    assert [s.language for s in segments] == ["zh", "en", "zh"], (
        "each segment's language must independently match its own detection "
        "result, not be pinned to a single whole-file language"
    )
    assert [s.text for s in segments] == ["你好", "hello", "再見"]
    assert [(s.start, s.end) for s in segments] == vad_segments

    assert mock_slice.call_args_list == [
        call(fake_audio, 16000, 0.0, 1.0),
        call(fake_audio, 16000, 1.0, 2.5),
        call(fake_audio, 16000, 2.5, 4.0),
    ]
    for transcribe_call in fake_model.transcribe.call_args_list:
        args, kwargs = transcribe_call
        assert args[0] is fake_chunk
        assert kwargs.get("language") is None
        assert kwargs.get("vad_filter") is False


# ---------------------------------------------------------------------------
# Empty input / model caching edge cases
# ---------------------------------------------------------------------------

def test_qwen3_asr_empty_vad_segments_returns_empty_without_loading_model():
    with patch.object(stt_engine, "_load_qwen3_asr_model") as mock_load, \
         patch.object(stt_engine, "_qwen3_asr_infer_chunk") as mock_infer:
        result = stt_engine._transcribe_qwen3_asr("audio.wav", [])

    assert result == []
    mock_load.assert_not_called()
    mock_infer.assert_not_called()


def test_faster_whisper_empty_vad_segments_returns_empty_without_loading_model():
    with patch.object(stt_engine, "_load_faster_whisper_model") as mock_load:
        result = stt_engine._transcribe_faster_whisper("audio.wav", [])

    assert result == []
    mock_load.assert_not_called()


def test_qwen3_asr_infer_chunk_matches_real_package_call_shape():
    """Regression test for the real qwen-asr API (verified against the
    installed package, not guessed): Qwen3ASRModel.transcribe() takes a
    single (ndarray, sample_rate) tuple as `audio` — no `sample_rate=` kwarg
    — and always returns a List[ASRTranscription], even for one chunk."""
    fake_result = MagicMock(text="你好", language="Chinese")
    fake_model = MagicMock()
    fake_model.transcribe.return_value = [fake_result]

    result = stt_engine._qwen3_asr_infer_chunk(fake_model, "chunk-array", 16000)

    fake_model.transcribe.assert_called_once_with(
        ("chunk-array", 16000), language=None, return_time_stamps=False
    )
    assert result is fake_result


def test_qwen3_asr_model_loaded_once_and_cached_across_calls(monkeypatch):
    """_load_qwen3_asr_model() must reuse the process-lifetime cache instead
    of reconstructing the model on every call."""
    monkeypatch.setattr(stt_engine.config, "STT_MODEL_NAME", "test-model-x")
    monkeypatch.setattr(stt_engine.config, "STT_DEVICE", "cpu")
    stt_engine._qwen3_asr_cache.clear()

    fake_model_cls = MagicMock()
    fake_model_cls.from_pretrained.return_value = MagicMock(name="loaded_model")

    fake_module = MagicMock()
    fake_module.Qwen3ASRModel = fake_model_cls

    try:
        with patch.dict("sys.modules", {"qwen_asr": fake_module}):
            first = stt_engine._load_qwen3_asr_model()
            second = stt_engine._load_qwen3_asr_model()
    finally:
        stt_engine._qwen3_asr_cache.clear()

    assert first is second
    assert fake_model_cls.from_pretrained.call_count == 1, (
        "model construction must happen once and be cached, not once per call"
    )


# ---------------------------------------------------------------------------
# _resolve_device: STT_DEVICE="cuda" (the default) must not hard-crash a
# GPU-less machine — mirrors quality_evaluator.load_model's invalid-device
# fallback, but checks runtime CUDA availability rather than string validity.
# These tests exercise the real `torch` import (STT_DEVICE != "cpu" always
# imports torch inside _resolve_device), so — like the rest of this project's
# torch-backed tests — they require the `translate-tool` conda env.
# ---------------------------------------------------------------------------

def test_resolve_device_returns_cpu_directly(monkeypatch):
    monkeypatch.setattr(stt_engine.config, "STT_DEVICE", "cpu")
    assert stt_engine._resolve_device() == "cpu"


def test_resolve_device_returns_cuda_when_available(monkeypatch):
    monkeypatch.setattr(stt_engine.config, "STT_DEVICE", "cuda")
    with patch("torch.cuda.is_available", return_value=True):
        assert stt_engine._resolve_device() == "cuda"


def test_resolve_device_falls_back_to_cpu_when_cuda_unavailable(monkeypatch, caplog):
    import logging

    monkeypatch.setattr(stt_engine.config, "STT_DEVICE", "cuda")
    with patch("torch.cuda.is_available", return_value=False), \
         caplog.at_level(logging.WARNING, logger="TranslateTool"):
        result = stt_engine._resolve_device()

    assert result == "cpu", "STT_DEVICE=cuda on a GPU-less machine must fall back, not crash"
    warnings = [r for r in caplog.records if r.name == "TranslateTool" and r.levelno == logging.WARNING]
    assert any("STT_DEVICE" in r.getMessage() for r in warnings)


def test_load_qwen3_asr_model_uses_resolved_device_for_cache_key_and_from_pretrained(monkeypatch):
    """When STT_DEVICE=cuda but CUDA is unavailable, both the cache key and
    the actual from_pretrained(device_map=...) call must use the RESOLVED
    ("cpu") device — not the raw config value — or the model would be built
    requesting a device that doesn't exist."""
    monkeypatch.setattr(stt_engine.config, "STT_MODEL_NAME", "test-model-y")
    monkeypatch.setattr(stt_engine.config, "STT_DEVICE", "cuda")
    stt_engine._qwen3_asr_cache.clear()

    fake_model_cls = MagicMock()
    fake_model_cls.from_pretrained.return_value = MagicMock(name="loaded_model")
    fake_module = MagicMock()
    fake_module.Qwen3ASRModel = fake_model_cls

    try:
        with patch("torch.cuda.is_available", return_value=False), \
             patch.dict("sys.modules", {"qwen_asr": fake_module}):
            stt_engine._load_qwen3_asr_model()
    finally:
        stt_engine._qwen3_asr_cache.clear()

    fake_model_cls.from_pretrained.assert_called_once_with(
        "test-model-y", device_map="cpu", dtype="float32",
    )


# ---------------------------------------------------------------------------
# unload_model: memory release when the transcribing stage exits
# ---------------------------------------------------------------------------

def test_unload_model_clears_both_engine_caches():
    stt_engine._qwen3_asr_cache["k"] = MagicMock()
    stt_engine._faster_whisper_cache["k"] = MagicMock()

    try:
        stt_engine.unload_model()
        assert stt_engine._qwen3_asr_cache == {}
        assert stt_engine._faster_whisper_cache == {}
    finally:
        stt_engine._qwen3_asr_cache.clear()
        stt_engine._faster_whisper_cache.clear()


def test_unload_model_forces_reload_of_qwen3_asr_on_next_call(monkeypatch):
    monkeypatch.setattr(stt_engine.config, "STT_MODEL_NAME", "test-model-z")
    monkeypatch.setattr(stt_engine.config, "STT_DEVICE", "cpu")
    stt_engine._qwen3_asr_cache.clear()

    fake_model_cls = MagicMock()
    fake_model_cls.from_pretrained.return_value = MagicMock(name="loaded_model")
    fake_module = MagicMock()
    fake_module.Qwen3ASRModel = fake_model_cls

    try:
        with patch.dict("sys.modules", {"qwen_asr": fake_module}):
            stt_engine._load_qwen3_asr_model()
            stt_engine.unload_model()
            stt_engine._load_qwen3_asr_model()
    finally:
        stt_engine._qwen3_asr_cache.clear()

    assert fake_model_cls.from_pretrained.call_count == 2, (
        "after unload_model(), the next load call must reconstruct the "
        "model rather than reuse a stale cached reference"
    )


def test_unload_model_calls_cuda_empty_cache_when_cuda_available():
    with patch("torch.cuda.is_available", return_value=True), \
         patch("torch.cuda.empty_cache") as mock_empty_cache:
        stt_engine.unload_model()

    mock_empty_cache.assert_called_once()


def test_unload_model_skips_cuda_empty_cache_when_cuda_unavailable():
    with patch("torch.cuda.is_available", return_value=False), \
         patch("torch.cuda.empty_cache") as mock_empty_cache:
        stt_engine.unload_model()

    mock_empty_cache.assert_not_called()


def test_unload_model_is_a_no_op_on_empty_caches():
    stt_engine._qwen3_asr_cache.clear()
    stt_engine._faster_whisper_cache.clear()
    stt_engine.unload_model()  # must not raise
    assert stt_engine._qwen3_asr_cache == {}
    assert stt_engine._faster_whisper_cache == {}
