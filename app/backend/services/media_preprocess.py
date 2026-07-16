"""Media preprocessing: ffmpeg audio extraction + optional DeepFilterNet3 denoise."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.backend.config import DENOISE_CHUNK_SECONDS, FFMPEG_PATH
from app.backend.utils.logging_utils import logger

FFMPEG_TIMEOUT = 600  # seconds; media files run far longer than office documents

# ---------------------------------------------------------------------------
# ffmpeg binary detection (mirrors libreoffice_helpers._find_libreoffice_binary)
# ---------------------------------------------------------------------------

_FFMPEG_BINARY: Optional[str] = None
_DETECTION_DONE = False


def _find_ffmpeg_binary() -> Optional[str]:
    """Detect the ffmpeg binary.

    Search order:
    1. FFMPEG_PATH env var / config
    2. PATH lookup
    """
    if FFMPEG_PATH:
        if os.path.isfile(FFMPEG_PATH) and os.access(FFMPEG_PATH, os.X_OK):
            return FFMPEG_PATH
        logger.warning("FFMPEG_PATH=%s is not executable", FFMPEG_PATH)

    found = shutil.which("ffmpeg")
    if found:
        return found

    return None


def is_ffmpeg_available() -> bool:
    """Return True if a usable ffmpeg binary was found (cached)."""
    global _FFMPEG_BINARY, _DETECTION_DONE  # noqa: PLW0603
    if not _DETECTION_DONE:
        _FFMPEG_BINARY = _find_ffmpeg_binary()
        _DETECTION_DONE = True
        if _FFMPEG_BINARY:
            logger.info("ffmpeg found: %s", _FFMPEG_BINARY)
        else:
            logger.info("ffmpeg not found")
    return _FFMPEG_BINARY is not None


def _get_binary() -> str:
    if not is_ffmpeg_available():
        raise RuntimeError("ffmpeg is not available")
    assert _FFMPEG_BINARY is not None
    return _FFMPEG_BINARY


# ---------------------------------------------------------------------------
# Audio extraction
# ---------------------------------------------------------------------------


def extract_audio(input_path: Path, output_dir: Path) -> Path:
    """Extract a 16kHz mono, loudness-normalized WAV from input_path via ffmpeg.

    output_dir must be a caller-owned directory (e.g. inside the job's own
    working dir) rather than a fresh system-tempdir the callee mkdtemp()s
    itself — the caller is responsible for cleanup (job dir teardown already
    covers this), so no intermediate file is ever orphaned in /tmp.
    """
    binary = _get_binary()
    input_path = Path(input_path).resolve()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{input_path.stem}.wav"

    cmd = [
        binary,
        "-y",
        "-i", str(input_path),
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        "-c:a", "pcm_s16le",
        "-af", "loudnorm",
        str(output_path),
    ]
    logger.debug("ffmpeg command: %s", " ".join(cmd))

    # Same start_new_session=True + process-group kill pattern as
    # libreoffice_helpers._libreoffice_convert — ffmpeg can spawn child
    # processes for some codecs and a plain proc.kill() on timeout would
    # leave those orphaned.
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=FFMPEG_TIMEOUT)
        returncode = proc.returncode
    except subprocess.TimeoutExpired:
        if hasattr(os, "killpg"):
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass  # process already gone
        else:
            proc.kill()  # best effort on non-POSIX platforms
        proc.communicate()  # reap the zombie
        raise RuntimeError(
            f"ffmpeg audio extraction timed out after {FFMPEG_TIMEOUT}s and was killed"
        )

    if returncode != 0:
        raise RuntimeError(
            f"ffmpeg audio extraction failed (rc={returncode}): "
            f"{stderr.strip() or stdout.strip()}"
        )

    if not output_path.is_file():
        raise RuntimeError(f"ffmpeg produced no output file: {output_path}")

    return output_path


# ---------------------------------------------------------------------------
# Denoise (DeepFilterNet3) — optional, never hard-fails the pipeline
# ---------------------------------------------------------------------------

# Process-lifetime model cache, same shape as quality_evaluator._model_cache.
_denoise_model_cache: Dict[str, tuple] = {}


def _shim_torchaudio_backend() -> None:
    """Work around an upstream compatibility break: DeepFilterNet3's `df.io`
    module does `from torchaudio.backend.common import AudioMetaData` at
    IMPORT TIME (verified against the installed deepfilternet==0.5.6, the
    latest release on PyPI — it has not been updated for torchaudio's newer
    versions, which removed the `torchaudio.backend` subpackage entirely).
    Without this shim, `from df.enhance import ...` raises
    ModuleNotFoundError unconditionally, and denoise_audio()'s graceful
    fallback (by design) would silently no-op on EVERY call.

    AudioMetaData is only used by `df.io.load_audio`/`save_audio` as a type
    hint — this module deliberately never calls those (see _run_deepfilternet:
    audio I/O goes through soundfile instead, since `df.io.load_audio` itself
    calls `torchaudio.load()`, which independently requires the `torchcodec`
    package on this torchaudio version — the same issue vad_segmenter.py
    works around). A dummy placeholder class is therefore sufficient; nothing
    ever constructs or inspects a real AudioMetaData instance.
    """
    import sys
    import types

    if "torchaudio.backend" in sys.modules:
        return
    common = types.ModuleType("torchaudio.backend.common")
    common.AudioMetaData = type("AudioMetaData", (), {})
    backend_pkg = types.ModuleType("torchaudio.backend")
    backend_pkg.common = common
    sys.modules["torchaudio.backend"] = backend_pkg
    sys.modules["torchaudio.backend.common"] = common


def _load_denoise_model() -> tuple:
    if "model" in _denoise_model_cache:
        return _denoise_model_cache["model"]

    _shim_torchaudio_backend()
    # Lazy import: df (DeepFilterNet3) is only imported when denoising is
    # actually requested, never at module import time.
    from df.enhance import init_df  # type: ignore[import]

    logger.info("[denoise] Loading DeepFilterNet3 model...")
    loaded = init_df()
    _denoise_model_cache["model"] = loaded
    logger.info("[denoise] Model loaded and cached.")
    return loaded


def _enhance_in_chunks(model: object, df_state: object, tensor, model_sr: int, enhance_fn):
    """Run DeepFilterNet3's enhance() over fixed-size time chunks instead of
    feeding it the whole tensor at once.

    enhance() holds STFT features and model activations for EVERY timestep of
    its input simultaneously — an uninterrupted span longer than
    DENOISE_CHUNK_SECONDS (e.g. one long monologue with no pause) would still
    exhaust GPU memory regardless of card size (observed: CUDA OOM on an 8GB
    card denoising a 64-minute recording in one call, before VAD-aware
    splitting existed). This is now a BACKSTOP under _enhance_speech_spans'
    VAD-aligned splitting, not the primary chunk boundary — see that
    function's docstring for why VAD pause boundaries are preferred over
    fixed time windows. The model already resets its recurrent state
    (`reset_h0`) at the start of every single enhance() call regardless of
    chunking, so calling it once per chunk only costs a brief re-adaptation
    at each chunk boundary.
    """
    import torch  # type: ignore[import]

    chunk_samples = max(1, int(DENOISE_CHUNK_SECONDS * model_sr))
    total_samples = tensor.shape[-1]
    if total_samples <= chunk_samples:
        return enhance_fn(model, df_state, tensor)

    chunks = [
        enhance_fn(model, df_state, tensor[:, start : start + chunk_samples])
        for start in range(0, total_samples, chunk_samples)
    ]
    return torch.cat(chunks, dim=-1)


def _enhance_speech_spans(model: object, df_state: object, tensor, model_sr: int,
                           vad_segments: List[Tuple[float, float]], enhance_fn):
    """Denoise only the VAD-detected speech spans of `tensor`; non-speech
    audio (silence, background noise between utterances) passes through
    unchanged.

    Chunking by VAD span instead of a fixed time window fixes the same OOM
    (bounded memory per call) while also avoiding an audible artifact a fixed
    window can introduce: DeepFilterNet3 resets its recurrent state at the
    start of every enhance() call, so a chunk boundary that lands mid-word
    causes a brief "re-adaptation" moment right where the cut speech is. VAD
    spans are bounded by silence/pauses by construction, so a span boundary
    here never lands mid-utterance. A single VAD span can still occasionally
    exceed DENOISE_CHUNK_SECONDS (e.g. one long uninterrupted monologue) —
    _enhance_in_chunks covers that remaining case as a backstop.

    vad_segments are (start_seconds, end_seconds) in the ORIGINAL wav_path's
    timeline — the same timeline stt_engine.transcribe() will later slice by
    — so the output tensor must stay the same total length and alignment as
    the input; only the speech spans' samples change.
    """
    import torch  # type: ignore[import]

    total_samples = tensor.shape[-1]
    if not vad_segments:
        return tensor  # nothing detected as speech; nothing to denoise

    pieces = []
    cursor = 0
    for start_s, end_s in sorted(vad_segments):
        start = max(0, min(total_samples, int(start_s * model_sr)))
        end = max(start, min(total_samples, int(end_s * model_sr)))
        if start > cursor:
            pieces.append(tensor[:, cursor:start])  # passthrough gap (non-speech)
        if end > start:
            pieces.append(_enhance_in_chunks(model, df_state, tensor[:, start:end], model_sr, enhance_fn))
        cursor = max(cursor, end)
    if cursor < total_samples:
        pieces.append(tensor[:, cursor:total_samples])
    return torch.cat(pieces, dim=-1)


def _run_deepfilternet(wav_path: Path, output_dir: Path, vad_segments: List[Tuple[float, float]]) -> Path:
    _shim_torchaudio_backend()
    from df.enhance import enhance  # type: ignore[import]

    # Audio I/O via soundfile (not df.enhance.load_audio/save_audio — both
    # call torchaudio.load()/save(), which need the separate `torchcodec`
    # package on this torchaudio version; see _shim_torchaudio_backend's
    # docstring). enhance() itself needs no file I/O, only a tensor.
    import soundfile as sf  # type: ignore[import]
    import torch  # type: ignore[import]
    import torchaudio.functional as taf  # type: ignore[import]

    model, df_state, _ = _load_denoise_model()
    model_sr = df_state.sr()  # DeepFilterNet3's native rate (48kHz), not ours

    audio, sample_rate = sf.read(str(wav_path), dtype="float32")
    tensor = torch.from_numpy(audio).unsqueeze(0)  # [1, T] mono
    if sample_rate != model_sr:
        tensor = taf.resample(tensor, sample_rate, model_sr)

    # vad_segments are (start_seconds, end_seconds) — resampling changed the
    # sample RATE, not the timeline itself, so the seconds values need no
    # conversion; _enhance_speech_spans converts seconds -> samples using
    # model_sr directly.
    enhanced = _enhance_speech_spans(model, df_state, tensor, model_sr, vad_segments, enhance)

    if sample_rate != model_sr:
        enhanced = taf.resample(enhanced, model_sr, sample_rate)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / wav_path.name
    sf.write(str(output_path), enhanced.squeeze(0).numpy(), sample_rate, subtype="PCM_16")
    return output_path


def denoise_audio(wav_path: Path, output_dir: Path, vad_segments: List[Tuple[float, float]]) -> Path:
    """Denoise the VAD speech spans of wav_path via DeepFilterNet3, writing
    into output_dir (see extract_audio's docstring — caller-owned dir, no
    orphaned /tmp files). vad_segments are (start_seconds, end_seconds) pairs
    from vad_segmenter.segment_by_voice_activity(wav_path) — the caller must
    run VAD BEFORE denoising (not after) so denoising can align its chunk
    boundaries to VAD's silence/pause boundaries instead of a fixed time
    window; see _enhance_speech_spans' docstring.

    Denoising must never hard-fail the pipeline: on any failure (package not
    installed, model load error, runtime error) this logs a warning and
    returns the original wav_path unchanged.
    """
    wav_path = Path(wav_path)
    try:
        return _run_deepfilternet(wav_path, output_dir, vad_segments)
    except Exception as exc:
        logger.warning(
            "[denoise] DeepFilterNet3 failed: %s: %s — using original audio",
            type(exc).__name__, exc,
        )
        # Best-effort: an OOM leaves PyTorch's caching allocator holding
        # fragmented/reserved GPU memory for the rest of the process
        # lifetime (mirrors quality_evaluator.score_blocks' OOM-retry
        # cleanup) — release it so a later job in this same process isn't
        # starved by a failure that already happened here.
        try:
            import torch  # type: ignore[import]
            torch.cuda.empty_cache()
        except Exception:
            pass
        return wav_path
