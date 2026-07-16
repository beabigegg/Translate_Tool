"""Tests for Silero VAD segmentation (vad_segmenter.py).

Mock seams:
- sys.modules["silero_vad"] — silero-vad is lazily imported (inside function
  bodies), so the module is injected via patch.dict("sys.modules", ...)
  rather than patching an attribute on vad_segmenter itself (mirrors
  test_quality_evaluation.py's test_qe_invalid_device_falls_back_to_cpu,
  which injects a fake "comet" module the same way).
- vad_segmenter._load_wav_as_tensor — patched directly rather than mocking
  soundfile, since audio loading is intentionally NOT routed through
  silero_vad's own read_audio() helper (that helper needs torchaudio's
  torchcodec backend, an extra dependency this pipeline avoids by loading via
  soundfile instead — see _load_wav_as_tensor's docstring).

Anti-tautology: assert call_count/call_args on the injected mock functions,
not just the returned tuple list.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from app.backend import config
from app.backend.services import vad_segmenter


def _make_mock_silero_module(timestamps, model=None):
    """Build a fake silero_vad module exposing load_silero_vad and
    get_speech_timestamps with controlled return values."""
    mock_model = model if model is not None else MagicMock(name="vad_model")
    mock_module = MagicMock()
    mock_module.load_silero_vad.return_value = mock_model
    mock_module.get_speech_timestamps.return_value = timestamps
    return mock_module, mock_model


@pytest.fixture(autouse=True)
def _clear_model_cache():
    """Ensure each test starts from a clean process-lifetime model cache."""
    vad_segmenter._model_cache.clear()
    yield
    vad_segmenter._model_cache.clear()


@pytest.fixture
def mock_wav_loading():
    """_load_wav_as_tensor does real soundfile/torch work — patch it to a
    deterministic fake tensor. NOT autouse: the dedicated real-loading tests
    near the bottom of this file exercise the unpatched function directly."""
    with patch.object(vad_segmenter, "_load_wav_as_tensor", return_value="FAKE_WAV_TENSOR") as m:
        yield m


# ---------------------------------------------------------------------------
# Core conversion behavior
# ---------------------------------------------------------------------------

def test_segment_by_voice_activity_converts_timestamps_to_tuples(mock_wav_loading):
    raw_timestamps = [
        {"start": 0.5, "end": 2.3},
        {"start": 5.0, "end": 7.25},
    ]
    mock_module, _ = _make_mock_silero_module(raw_timestamps)

    with patch.dict(sys.modules, {"silero_vad": mock_module}):
        result = vad_segmenter.segment_by_voice_activity("fake.wav")

    assert result == [(0.5, 2.3), (5.0, 7.25)]
    for start, end in result:
        assert isinstance(start, float)
        assert isinstance(end, float)


def test_segment_by_voice_activity_coerces_non_float_timestamp_values(mock_wav_loading):
    """get_speech_timestamps can return int/str-ish numeric values; the
    function must coerce both start and end to float regardless of the
    incoming type."""
    raw_timestamps = [{"start": 1, "end": 3}]
    mock_module, _ = _make_mock_silero_module(raw_timestamps)

    with patch.dict(sys.modules, {"silero_vad": mock_module}):
        result = vad_segmenter.segment_by_voice_activity("fake.wav")

    assert result == [(1.0, 3.0)]
    assert isinstance(result[0][0], float)
    assert isinstance(result[0][1], float)


def test_segment_by_voice_activity_empty_timestamps_returns_empty_list(mock_wav_loading):
    mock_module, _ = _make_mock_silero_module([])

    with patch.dict(sys.modules, {"silero_vad": mock_module}):
        result = vad_segmenter.segment_by_voice_activity("silence.wav")

    assert result == []


def test_segment_by_voice_activity_preserves_input_order(mock_wav_loading):
    raw_timestamps = [
        {"start": 10.0, "end": 12.0},
        {"start": 1.0, "end": 2.0},
        {"start": 20.0, "end": 21.0},
    ]
    mock_module, _ = _make_mock_silero_module(raw_timestamps)

    with patch.dict(sys.modules, {"silero_vad": mock_module}):
        result = vad_segmenter.segment_by_voice_activity("fake.wav")

    assert result == [(10.0, 12.0), (1.0, 2.0), (20.0, 21.0)]


# ---------------------------------------------------------------------------
# Wiring: audio loading / get_speech_timestamps call shape
# ---------------------------------------------------------------------------

def test_segment_by_voice_activity_loads_audio_from_wav_path(mock_wav_loading):
    mock_module, _ = _make_mock_silero_module([])

    with patch.dict(sys.modules, {"silero_vad": mock_module}):
        vad_segmenter.segment_by_voice_activity("some/path/audio.wav")

    mock_wav_loading.assert_called_once_with("some/path/audio.wav")


def test_segment_by_voice_activity_passes_wav_and_model_positionally(mock_wav_loading):
    mock_wav_loading.return_value = "THE_WAV"
    mock_module, mock_model = _make_mock_silero_module([])

    with patch.dict(sys.modules, {"silero_vad": mock_module}):
        vad_segmenter.segment_by_voice_activity("fake.wav")

    call_args = mock_module.get_speech_timestamps.call_args
    assert call_args.args == ("THE_WAV", mock_model)


def test_segment_by_voice_activity_passes_min_silence_ms_from_config(mock_wav_loading):
    mock_module, _ = _make_mock_silero_module([])

    with patch.dict(sys.modules, {"silero_vad": mock_module}):
        vad_segmenter.segment_by_voice_activity("fake.wav")

    call_kwargs = mock_module.get_speech_timestamps.call_args.kwargs
    assert call_kwargs["sampling_rate"] == 16000
    assert call_kwargs["min_silence_duration_ms"] == config.VAD_MIN_SILENCE_MS
    assert call_kwargs["return_seconds"] is True


def test_segment_by_voice_activity_respects_updated_min_silence_ms_config(monkeypatch, mock_wav_loading):
    """The kwarg must be read from config at call time, not a value baked in
    at import time — patch config.VAD_MIN_SILENCE_MS to a non-default number
    and confirm it's the exact value forwarded."""
    monkeypatch.setattr(config, "VAD_MIN_SILENCE_MS", 750)
    mock_module, _ = _make_mock_silero_module([])

    with patch.dict(sys.modules, {"silero_vad": mock_module}):
        vad_segmenter.segment_by_voice_activity("fake.wav")

    call_kwargs = mock_module.get_speech_timestamps.call_args.kwargs
    assert call_kwargs["min_silence_duration_ms"] == 750


# ---------------------------------------------------------------------------
# Model caching (process-lifetime cache)
# ---------------------------------------------------------------------------

def test_model_is_loaded_once_and_cached_across_multiple_calls(mock_wav_loading):
    mock_module, mock_model = _make_mock_silero_module([])

    with patch.dict(sys.modules, {"silero_vad": mock_module}):
        vad_segmenter.segment_by_voice_activity("a.wav")
        vad_segmenter.segment_by_voice_activity("b.wav")

    assert mock_module.load_silero_vad.call_count == 1, (
        "load_silero_vad must be called only once; subsequent calls should "
        "reuse the cached model instance"
    )
    # Both calls to get_speech_timestamps must have used the same cached model.
    first_call_model = mock_module.get_speech_timestamps.call_args_list[0].args[1]
    second_call_model = mock_module.get_speech_timestamps.call_args_list[1].args[1]
    assert first_call_model is mock_model
    assert second_call_model is mock_model


def test_load_vad_model_returns_cached_instance_without_reloading():
    mock_module, mock_model = _make_mock_silero_module([])

    with patch.dict(sys.modules, {"silero_vad": mock_module}):
        first = vad_segmenter._load_vad_model()
        second = vad_segmenter._load_vad_model()

    assert first is mock_model
    assert second is mock_model
    assert mock_module.load_silero_vad.call_count == 1


def test_load_vad_model_uses_fixed_cache_key():
    mock_module, mock_model = _make_mock_silero_module([])

    with patch.dict(sys.modules, {"silero_vad": mock_module}):
        vad_segmenter._load_vad_model()

    assert vad_segmenter._model_cache.get(vad_segmenter._CACHE_KEY) is mock_model


# ---------------------------------------------------------------------------
# Model unload (memory release when the vad_segmenting stage exits)
# ---------------------------------------------------------------------------

def test_unload_model_clears_the_cache():
    mock_module, mock_model = _make_mock_silero_module([])

    with patch.dict(sys.modules, {"silero_vad": mock_module}):
        vad_segmenter._load_vad_model()
        assert vad_segmenter._model_cache  # populated before unload

        vad_segmenter.unload_model()

    assert vad_segmenter._model_cache == {}


def test_unload_model_forces_reload_on_next_call(mock_wav_loading):
    mock_module, _ = _make_mock_silero_module([])

    with patch.dict(sys.modules, {"silero_vad": mock_module}):
        vad_segmenter.segment_by_voice_activity("a.wav")
        vad_segmenter.unload_model()
        vad_segmenter.segment_by_voice_activity("b.wav")

    assert mock_module.load_silero_vad.call_count == 2, (
        "after unload_model(), the next segmentation call must reload the "
        "model rather than reuse a stale cached reference"
    )


def test_unload_model_is_a_no_op_on_an_empty_cache():
    """Calling unload before any model was ever loaded (e.g. a job whose VAD
    stage failed before caching) must not raise."""
    vad_segmenter.unload_model()
    assert vad_segmenter._model_cache == {}


# ---------------------------------------------------------------------------
# No eager import of silero_vad at module load time
# ---------------------------------------------------------------------------

def test_silero_vad_not_imported_at_module_level():
    """vad_segmenter imports silero_vad lazily (inside function bodies) —
    importing vad_segmenter itself (already done at module load above) must
    not pull silero_vad into the module's own namespace, regardless of
    whether the real package happens to be installed in this environment."""
    assert "silero_vad" not in vars(vad_segmenter)


# ---------------------------------------------------------------------------
# Real audio loading (no mocking) — _load_wav_as_tensor itself
# ---------------------------------------------------------------------------

def test_load_wav_as_tensor_reads_real_16khz_mono_wav(tmp_path):
    """Exercises the real soundfile + torch path (no silero_vad involved) —
    catches a torchaudio/torchcodec-shaped regression if someone routes this
    back through silero_vad's read_audio() helper."""
    import numpy as np
    import soundfile as sf
    import torch

    wav_path = tmp_path / "tone.wav"
    samples = np.zeros(16000, dtype="float32")  # 1s of silence at 16kHz
    sf.write(str(wav_path), samples, 16000, subtype="PCM_16")

    result = vad_segmenter._load_wav_as_tensor(str(wav_path))

    assert isinstance(result, torch.Tensor)
    assert result.shape[0] == 16000


def test_load_wav_as_tensor_rejects_wrong_sample_rate(tmp_path):
    import numpy as np
    import soundfile as sf

    wav_path = tmp_path / "wrong_rate.wav"
    samples = np.zeros(8000, dtype="float32")
    sf.write(str(wav_path), samples, 8000, subtype="PCM_16")

    with pytest.raises(ValueError, match="16000Hz"):
        vad_segmenter._load_wav_as_tensor(str(wav_path))
