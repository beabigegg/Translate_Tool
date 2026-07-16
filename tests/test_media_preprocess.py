"""Tests for media preprocessing: ffmpeg audio extraction + DeepFilterNet3 denoise.

Mock seam: subprocess.Popen (extract_audio uses Popen, mirroring
libreoffice_helpers._libreoffice_convert's process-group-kill pattern — see
tests/test_libreoffice_helpers.py for the reference style).

denoise_audio()'s df import failure is forced via sys.modules['df'] = None
(monkeypatch), the standard technique for making `import df...` raise
ImportError deterministically regardless of whether the real `df` package
happens to be installed in the environment running the test.

Neither ffmpeg nor df/soundfile/etc. are installed in this test environment —
that is expected; nothing here imports them for real.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.backend.services import media_preprocess


@pytest.fixture(autouse=True)
def _reset_module_caches():
    """Reset ffmpeg-detection and denoise-model caches around every test."""
    media_preprocess._FFMPEG_BINARY = None
    media_preprocess._DETECTION_DONE = False
    media_preprocess._denoise_model_cache.clear()
    yield
    media_preprocess._FFMPEG_BINARY = None
    media_preprocess._DETECTION_DONE = False
    media_preprocess._denoise_model_cache.clear()


def _make_fake_popen(returncode=0, stdout="", stderr="", write_output=True):
    """Build a fake Popen class that captures argv and simulates ffmpeg exit."""
    captured = {}

    class _FakeProc:
        def __init__(self, cmd, stdout=None, stderr=None, text=None, start_new_session=None):
            captured["cmd"] = cmd
            self.pid = 55555
            self.returncode = returncode
            if write_output and returncode == 0:
                Path(cmd[-1]).write_bytes(b"RIFF-fake-wav-bytes")

        def communicate(self, timeout=None):
            return (stdout, stderr)

    return _FakeProc, captured


# ---------------------------------------------------------------------------
# extract_audio: ffmpeg argv shape
# ---------------------------------------------------------------------------

def test_extract_audio_builds_correct_ffmpeg_argv(tmp_path):
    input_path = tmp_path / "clip.mp4"
    input_path.write_bytes(b"fake-video-bytes")
    output_dir = tmp_path / "work"

    fake_proc, captured = _make_fake_popen(returncode=0)

    with (
        patch("app.backend.services.media_preprocess.FFMPEG_PATH", ""),
        patch(
            "shutil.which",
            side_effect=lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None,
        ),
        patch("subprocess.Popen", side_effect=fake_proc) as mock_popen,
    ):
        result_path = media_preprocess.extract_audio(input_path, output_dir)

    assert mock_popen.called, "subprocess.Popen must be invoked for ffmpeg extraction"
    cmd = captured["cmd"]

    resolved_input = str(Path(input_path).resolve())
    assert cmd == [
        "/usr/bin/ffmpeg",
        "-y",
        "-i", resolved_input,
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        "-c:a", "pcm_s16le",
        "-af", "loudnorm",
        str(result_path),
    ], f"unexpected ffmpeg argv: {cmd}"
    assert result_path.exists()
    assert result_path.parent == output_dir, (
        "extract_audio must write into the caller-supplied output_dir, not a "
        "self-managed tempfile.mkdtemp() dir that nothing ever cleans up"
    )


def test_extract_audio_raises_when_ffmpeg_not_available(tmp_path):
    input_path = tmp_path / "clip.mp4"
    input_path.write_bytes(b"fake-video-bytes")

    with (
        patch("app.backend.services.media_preprocess.FFMPEG_PATH", ""),
        patch("shutil.which", return_value=None),
        patch("os.path.isfile", return_value=False),
    ):
        with pytest.raises(RuntimeError, match="ffmpeg is not available"):
            media_preprocess.extract_audio(input_path, tmp_path / "work")


# ---------------------------------------------------------------------------
# extract_audio: non-zero exit code
# ---------------------------------------------------------------------------

def test_extract_audio_raises_on_nonzero_exit_with_stderr_content(tmp_path):
    input_path = tmp_path / "clip.mp4"
    input_path.write_bytes(b"fake-video-bytes")

    fake_proc, captured = _make_fake_popen(
        returncode=1,
        stdout="",
        stderr="ffmpeg: Invalid data found when processing input",
    )

    with (
        patch("app.backend.services.media_preprocess.FFMPEG_PATH", ""),
        patch(
            "shutil.which",
            side_effect=lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None,
        ),
        patch("subprocess.Popen", side_effect=fake_proc),
    ):
        with pytest.raises(RuntimeError, match="Invalid data found when processing input"):
            media_preprocess.extract_audio(input_path, tmp_path / "work")

    assert captured["cmd"][0] == "/usr/bin/ffmpeg"


def test_extract_audio_kills_process_group_on_timeout(tmp_path):
    input_path = tmp_path / "clip.mp4"
    input_path.write_bytes(b"fake-video-bytes")

    fake_proc = MagicMock()
    fake_proc.pid = 24680
    fake_proc.communicate.side_effect = [
        subprocess.TimeoutExpired(cmd="ffmpeg", timeout=600),
        ("", ""),
    ]

    with (
        patch("app.backend.services.media_preprocess.FFMPEG_PATH", ""),
        patch(
            "shutil.which",
            side_effect=lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None,
        ),
        patch("subprocess.Popen", return_value=fake_proc),
        patch("os.getpgid", return_value=24680) as mock_getpgid,
        patch("os.killpg") as mock_killpg,
    ):
        with pytest.raises(RuntimeError, match="timed out"):
            media_preprocess.extract_audio(input_path, tmp_path / "work")

    mock_getpgid.assert_called_once_with(24680)
    mock_killpg.assert_called_once_with(24680, media_preprocess.signal.SIGKILL)
    assert fake_proc.communicate.call_count == 2


# ---------------------------------------------------------------------------
# extract_audio: FFMPEG_PATH config override
# ---------------------------------------------------------------------------

def test_extract_audio_honors_ffmpeg_path_config_override(tmp_path):
    input_path = tmp_path / "clip.mp4"
    input_path.write_bytes(b"fake-video-bytes")
    override_path = "/opt/custom/bin/ffmpeg"

    fake_proc, captured = _make_fake_popen(returncode=0)

    with (
        patch("app.backend.services.media_preprocess.FFMPEG_PATH", override_path),
        patch("os.path.isfile", side_effect=lambda p: p == override_path),
        patch("os.access", side_effect=lambda p, mode: p == override_path),
        # PATH lookup would resolve to a *different* binary — proves the
        # config override takes priority rather than falling through to it.
        patch(
            "shutil.which",
            side_effect=lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None,
        ),
        patch("subprocess.Popen", side_effect=fake_proc) as mock_popen,
    ):
        media_preprocess.extract_audio(input_path, tmp_path / "work")

    assert mock_popen.called
    assert captured["cmd"][0] == override_path, (
        f"FFMPEG_PATH override must be used; got binary {captured['cmd'][0]!r}"
    )


# ---------------------------------------------------------------------------
# denoise_audio: graceful fallback when `df` import fails
# ---------------------------------------------------------------------------

def test_denoise_audio_falls_back_when_df_import_fails(monkeypatch, tmp_path, caplog):
    # sys.modules[name] = None is the standard way to force `import name...`
    # to raise ImportError deterministically, regardless of whether the real
    # `df` package happens to be installed in the environment running this.
    monkeypatch.setitem(sys.modules, "df", None)
    monkeypatch.delitem(sys.modules, "df.enhance", raising=False)

    wav_path = tmp_path / "extracted.wav"
    wav_path.write_bytes(b"fake-wav-bytes")

    with caplog.at_level(logging.WARNING, logger="TranslateTool"):
        result = media_preprocess.denoise_audio(wav_path, tmp_path / "work", [(0.0, 1.0)])

    assert result == wav_path, "on import failure, the original wav_path must be returned unchanged"

    warnings = [r for r in caplog.records if r.name == "TranslateTool" and r.levelno == logging.WARNING]
    assert warnings, "denoise_audio must log a WARNING when DeepFilterNet3 is unavailable"
    assert any("denoise" in r.getMessage().lower() for r in warnings)


def test_denoise_audio_falls_back_on_any_runtime_error(monkeypatch, tmp_path, caplog):
    """Non-import failures (e.g. a model load error) must also degrade gracefully."""
    monkeypatch.setattr(
        media_preprocess,
        "_run_deepfilternet",
        MagicMock(side_effect=RuntimeError("model checkpoint corrupt")),
    )

    wav_path = tmp_path / "extracted.wav"
    wav_path.write_bytes(b"fake-wav-bytes")

    with caplog.at_level(logging.WARNING, logger="TranslateTool"):
        result = media_preprocess.denoise_audio(wav_path, tmp_path / "work", [(0.0, 1.0)])

    assert result == wav_path
    warnings = [r for r in caplog.records if r.name == "TranslateTool" and r.levelno == logging.WARNING]
    assert warnings


def test_denoise_audio_success_returns_enhanced_path(tmp_path):
    """Wiring check: denoise_audio forwards _run_deepfilternet's result untouched
    on success (the try/except must not swallow a good result)."""
    enhanced_path = tmp_path / "enhanced.wav"
    enhanced_path.write_bytes(b"enhanced-bytes")
    mock_run = MagicMock(return_value=enhanced_path)

    wav_path = tmp_path / "extracted.wav"
    wav_path.write_bytes(b"fake-wav-bytes")
    output_dir = tmp_path / "work"
    vad_segments = [(0.0, 1.0), (2.0, 3.5)]

    with patch.object(media_preprocess, "_run_deepfilternet", mock_run):
        result = media_preprocess.denoise_audio(wav_path, output_dir, vad_segments)

    mock_run.assert_called_once_with(wav_path, output_dir, vad_segments)
    assert result == enhanced_path


def test_denoise_audio_clears_cuda_cache_on_failure(monkeypatch, tmp_path, caplog):
    """Regression: a caught OOM (or any other failure) must not leave PyTorch's
    caching allocator holding fragmented/reserved GPU memory for the rest of
    the process — mirrors quality_evaluator.score_blocks' OOM-retry cleanup."""
    monkeypatch.setattr(
        media_preprocess,
        "_run_deepfilternet",
        MagicMock(side_effect=RuntimeError("CUDA out of memory")),
    )
    fake_torch = MagicMock()
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    wav_path = tmp_path / "extracted.wav"
    wav_path.write_bytes(b"fake-wav-bytes")

    with caplog.at_level(logging.WARNING, logger="TranslateTool"):
        result = media_preprocess.denoise_audio(wav_path, tmp_path / "work", [(0.0, 1.0)])

    assert result == wav_path
    fake_torch.cuda.empty_cache.assert_called_once()


def test_denoise_audio_failure_survives_missing_torch(monkeypatch, tmp_path, caplog):
    """The best-effort cache-clear must not itself raise/mask the original
    graceful-fallback behavior when torch isn't importable."""
    monkeypatch.setattr(
        media_preprocess,
        "_run_deepfilternet",
        MagicMock(side_effect=RuntimeError("model checkpoint corrupt")),
    )
    monkeypatch.setitem(sys.modules, "torch", None)

    wav_path = tmp_path / "extracted.wav"
    wav_path.write_bytes(b"fake-wav-bytes")

    result = media_preprocess.denoise_audio(wav_path, tmp_path / "work", [(0.0, 1.0)])

    assert result == wav_path


# ---------------------------------------------------------------------------
# _enhance_in_chunks: bounded-memory chunked denoise (OOM regression coverage)
#
# Root cause of the real-world OOM this guards against: DeepFilterNet3's
# enhance() holds STFT features + model activations for EVERY timestep of its
# input simultaneously. Feeding it a full recording in one call (e.g. a
# 64-minute meeting, this pipeline's primary input) exhausted an 8GB GPU's
# memory in production. These tests use real (tiny) torch tensors — mirrors
# test_vad_segmenter.py's real-loading tests — and therefore require the
# `translate-tool` conda env's torch, same as the rest of this project's
# torch-backed tests.
# ---------------------------------------------------------------------------

def test_enhance_in_chunks_single_call_when_audio_fits_one_chunk(monkeypatch):
    import torch

    monkeypatch.setattr(media_preprocess, "DENOISE_CHUNK_SECONDS", 1)
    model_sr = 10  # chunk_samples = 1 * 10 = 10
    tensor = torch.arange(10, dtype=torch.float32).unsqueeze(0)  # exactly chunk_samples
    enhance_fn = MagicMock(side_effect=lambda model, state, chunk: chunk)

    result = media_preprocess._enhance_in_chunks(
        model=object(), df_state=object(), tensor=tensor, model_sr=model_sr, enhance_fn=enhance_fn,
    )

    enhance_fn.assert_called_once()
    called_chunk = enhance_fn.call_args.args[2]
    assert torch.equal(called_chunk, tensor), (
        "audio that fits within one chunk must be passed through unsplit"
    )
    assert torch.equal(result, tensor)


def test_enhance_in_chunks_splits_long_audio_and_never_exceeds_chunk_size(monkeypatch):
    """Direct regression test for the production incident: no single
    enhance_fn call may ever receive more than chunk_samples of audio,
    regardless of total recording length."""
    import torch

    monkeypatch.setattr(media_preprocess, "DENOISE_CHUNK_SECONDS", 1)
    model_sr = 10  # chunk_samples = 10
    total_samples = 25  # 2 full chunks + 1 partial trailing chunk of 5
    tensor = torch.arange(total_samples, dtype=torch.float32).unsqueeze(0)
    enhance_fn = MagicMock(side_effect=lambda model, state, chunk: chunk)

    result = media_preprocess._enhance_in_chunks(
        model=object(), df_state=object(), tensor=tensor, model_sr=model_sr, enhance_fn=enhance_fn,
    )

    assert enhance_fn.call_count == 3, "25 samples at chunk_samples=10 must split into 3 calls"
    chunk_sizes = [call.args[2].shape[-1] for call in enhance_fn.call_args_list]
    assert chunk_sizes == [10, 10, 5]
    assert all(size <= 10 for size in chunk_sizes), (
        "no chunk may exceed chunk_samples — this is the exact bound that "
        "prevents the whole-file-in-one-tensor OOM observed in production"
    )
    assert torch.equal(result, tensor), (
        "chunked enhance + concatenation must reassemble byte-for-byte "
        "identical audio when enhance_fn is the identity function"
    )


def test_enhance_in_chunks_reads_chunk_seconds_from_config_at_call_time(monkeypatch):
    """DENOISE_CHUNK_SECONDS must be read live, not baked in at import time —
    same convention as vad_segmenter's VAD_MIN_SILENCE_MS."""
    import torch

    model_sr = 10
    tensor = torch.arange(20, dtype=torch.float32).unsqueeze(0)
    enhance_fn = MagicMock(side_effect=lambda model, state, chunk: chunk)

    monkeypatch.setattr(media_preprocess, "DENOISE_CHUNK_SECONDS", 2)  # chunk_samples=20
    media_preprocess._enhance_in_chunks(object(), object(), tensor, model_sr, enhance_fn)
    assert enhance_fn.call_count == 1, "20 samples at chunk_samples=20 must fit in one call"

    enhance_fn.reset_mock()
    monkeypatch.setattr(media_preprocess, "DENOISE_CHUNK_SECONDS", 0.5)  # chunk_samples=5
    media_preprocess._enhance_in_chunks(object(), object(), tensor, model_sr, enhance_fn)
    assert enhance_fn.call_count == 4, "20 samples at chunk_samples=5 must split into 4 calls"


# ---------------------------------------------------------------------------
# _enhance_speech_spans: VAD-aligned denoise chunking (avoids mid-word cuts)
#
# Reordering the pipeline so VAD runs before denoise (media_job_manager.py)
# lets denoising split its calls at VAD's silence/pause boundaries instead of
# a fixed time window — this fixes the same OOM as _enhance_in_chunks while
# also avoiding an audible artifact a fixed window can introduce at a cut
# that lands mid-word (DeepFilterNet3 resets recurrent state at the start of
# every enhance() call).
# ---------------------------------------------------------------------------

def test_enhance_speech_spans_denoises_speech_and_passes_gaps_through_unchanged():
    import torch

    model_sr = 10
    # 30 samples: [0-10) silence, [10-20) speech, [20-30) silence
    tensor = torch.arange(30, dtype=torch.float32).unsqueeze(0)
    vad_segments = [(1.0, 2.0)]  # seconds * model_sr(10) = samples [10:20)

    def mark_enhanced(model, state, chunk):
        return chunk * 100  # distinguishable from an untouched passthrough

    result = media_preprocess._enhance_speech_spans(
        model=object(), df_state=object(), tensor=tensor, model_sr=model_sr,
        vad_segments=vad_segments, enhance_fn=mark_enhanced,
    )

    assert result.shape[-1] == tensor.shape[-1], "output must preserve total length/alignment"
    assert torch.equal(result[:, 0:10], tensor[:, 0:10]), "pre-speech gap must pass through unchanged"
    assert torch.equal(result[:, 10:20], tensor[:, 10:20] * 100), "VAD speech span must be denoised"
    assert torch.equal(result[:, 20:30], tensor[:, 20:30]), "post-speech gap must pass through unchanged"


def test_enhance_speech_spans_handles_multiple_segments_and_unsorted_input():
    import torch

    model_sr = 10
    tensor = torch.arange(40, dtype=torch.float32).unsqueeze(0)
    # Deliberately out of order — sorted() inside the function must fix this.
    vad_segments = [(2.0, 3.0), (0.0, 1.0)]  # samples [20:30) and [0:10)

    def mark_enhanced(model, state, chunk):
        return chunk * 100

    result = media_preprocess._enhance_speech_spans(
        object(), object(), tensor, model_sr, vad_segments, mark_enhanced,
    )

    assert torch.equal(result[:, 0:10], tensor[:, 0:10] * 100)
    assert torch.equal(result[:, 10:20], tensor[:, 10:20]), "gap between the two spans"
    assert torch.equal(result[:, 20:30], tensor[:, 20:30] * 100)
    assert torch.equal(result[:, 30:40], tensor[:, 30:40]), "trailing gap"


def test_enhance_speech_spans_passes_whole_tensor_through_when_no_vad_segments():
    import torch

    tensor = torch.arange(15, dtype=torch.float32).unsqueeze(0)
    enhance_fn = MagicMock()

    result = media_preprocess._enhance_speech_spans(
        object(), object(), tensor, model_sr=10, vad_segments=[], enhance_fn=enhance_fn,
    )

    enhance_fn.assert_not_called()
    assert torch.equal(result, tensor)


def test_enhance_speech_spans_delegates_each_span_through_the_chunk_size_backstop(monkeypatch):
    """A single VAD span longer than DENOISE_CHUNK_SECONDS must still be
    bounded by _enhance_in_chunks — VAD boundaries are the primary strategy,
    not a replacement for the hard memory-safety cap (e.g. one long
    uninterrupted monologue with no detected pause)."""
    import torch

    monkeypatch.setattr(media_preprocess, "DENOISE_CHUNK_SECONDS", 1)  # chunk_samples=10 at model_sr=10
    model_sr = 10
    tensor = torch.arange(25, dtype=torch.float32).unsqueeze(0)
    vad_segments = [(0.0, 2.5)]  # one 25-sample span, longer than the 10-sample backstop
    enhance_fn = MagicMock(side_effect=lambda model, state, chunk: chunk)

    media_preprocess._enhance_speech_spans(
        object(), object(), tensor, model_sr, vad_segments, enhance_fn,
    )

    assert enhance_fn.call_count == 3, (
        "one 25-sample VAD span must still be split by the 10-sample chunk "
        "backstop into 3 calls, not fed to enhance_fn whole"
    )
    chunk_sizes = [call.args[2].shape[-1] for call in enhance_fn.call_args_list]
    assert all(size <= 10 for size in chunk_sizes)
