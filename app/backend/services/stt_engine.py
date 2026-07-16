"""Dual-engine STT abstraction (Qwen3-ASR default, faster-whisper fallback).

Lazy-import + process-lifetime model cache pattern copied from
quality_evaluator.py:25-65 — neither engine's package is imported at module
import time, only inside the loader that actually needs it.

Both engines call the model ONCE PER vad_segments entry (not once for the
whole file) so that TranscriptSegment.language is detected independently per
segment — required for multi-language meeting support (a recording can
switch speaker language mid-file).
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from app.backend import config
from app.backend.models.media_transcript import TranscriptSegment
from app.backend.utils.logging_utils import logger

# Process-lifetime model caches, keyed by (model_name, device) — mirrors
# quality_evaluator._model_cache.
_qwen3_asr_cache: Dict[Tuple[str, str], object] = {}
_faster_whisper_cache: Dict[Tuple[str, str], object] = {}


def transcribe(wav_path: str, vad_segments: List[Tuple[float, float]]) -> List[TranscriptSegment]:
    """Transcribe each VAD speech window, dispatching on config.STT_ENGINE."""
    if config.STT_ENGINE == "faster-whisper":
        return _transcribe_faster_whisper(wav_path, vad_segments)
    return _transcribe_qwen3_asr(wav_path, vad_segments)


def _load_audio(wav_path: str):
    # Lazy import: soundfile is only needed once a transcription is actually
    # requested, never at module import time. Decodes the whole file ONCE per
    # transcribe() call — callers slice segments from the returned array via
    # _slice_chunk() instead of re-decoding per VAD segment (a 150-segment
    # meeting would otherwise re-read/re-decode the full file 150 times).
    import soundfile as sf  # type: ignore[import]

    return sf.read(wav_path, dtype="float32")


def _slice_chunk(audio, sample_rate: int, start: float, end: float):
    return audio[int(start * sample_rate):int(end * sample_rate)]


def _resolve_device() -> str:
    """Fall back to CPU if config.STT_DEVICE requests CUDA but no CUDA device
    is actually available on this machine — mirrors quality_evaluator.load_model's
    invalid-device fallback, but checks runtime availability rather than just
    string validity. STT_DEVICE defaults to "cuda" (Qwen3-ASR's autoregressive
    decode only ever saturates ~1 CPU core regardless of core count — see
    config.py's STT_DEVICE comment), so a GPU-less machine must not hard-crash
    on that default.
    """
    if config.STT_DEVICE == "cpu":
        return "cpu"
    import torch  # type: ignore[import]

    if torch.cuda.is_available():
        return config.STT_DEVICE
    logger.warning(
        "[STT] STT_DEVICE=%r requested but no CUDA device is available — falling back to CPU.",
        config.STT_DEVICE,
    )
    return "cpu"


# ---------------------------------------------------------------------------
# Qwen3-ASR (default engine)
# ---------------------------------------------------------------------------


def _load_qwen3_asr_model() -> object:
    device = _resolve_device()
    cache_key = (config.STT_MODEL_NAME, device)
    if cache_key in _qwen3_asr_cache:
        return _qwen3_asr_cache[cache_key]

    # Lazy import: qwen_asr is only imported when STT_ENGINE="qwen3-asr" is
    # actually invoked, never at module import time.
    from qwen_asr import Qwen3ASRModel  # type: ignore[import]

    logger.info(
        "[STT] Loading Qwen3-ASR model %s on device=%s ...",
        config.STT_MODEL_NAME, device,
    )
    # device_map (not "device") is the kwarg AutoModel.from_pretrained()
    # actually recognizes for placement — verified against the installed
    # qwen-asr package's Qwen3ASRModel.from_pretrained(**kwargs -> AutoModel).
    # torch_dtype: fp32 is AutoModel's default when unspecified, which loads
    # Qwen3-ASR-1.7B at ~9.4GB peak VRAM (verified) — over an 8GB card's
    # capacity. fp16 on CUDA roughly halves that; CPU keeps fp32 (no fp16
    # kernel support / benefit on CPU).
    dtype = "float16" if device != "cpu" else "float32"
    model = Qwen3ASRModel.from_pretrained(
        config.STT_MODEL_NAME, device_map=device, dtype=dtype,
    )
    _qwen3_asr_cache[cache_key] = model
    logger.info("[STT] Qwen3-ASR model loaded and cached.")
    return model


def _qwen3_asr_infer_chunk(model: object, audio_array, sample_rate: int):
    # Verified against the installed qwen-asr package: Qwen3ASRModel.transcribe
    # takes `audio` as a single (ndarray, sample_rate) tuple (or a path, or a
    # list of either for batching) — there is no `sample_rate=` kwarg — and
    # always returns a List[ASRTranscription], one entry per input, even for
    # a single chunk. ASRTranscription.language is a human-readable name
    # (e.g. "Chinese"), unlike faster-whisper's ISO code (e.g. "zh") below —
    # both are stored as-is in TranscriptSegment.language; this is informational
    # only (translate_transcript() always passes src_lang=None/auto).
    results = model.transcribe((audio_array, sample_rate), language=None, return_time_stamps=False)
    return results[0]


def _transcribe_qwen3_asr(wav_path: str, vad_segments: List[Tuple[float, float]]) -> List[TranscriptSegment]:
    if not vad_segments:
        return []

    model = _load_qwen3_asr_model()
    audio, sample_rate = _load_audio(wav_path)

    segments: List[TranscriptSegment] = []
    for start, end in vad_segments:
        # One model call per VAD segment — see module docstring.
        chunk = _slice_chunk(audio, sample_rate, start, end)
        result = _qwen3_asr_infer_chunk(model, chunk, sample_rate)
        segments.append(
            TranscriptSegment(
                start=start,
                end=end,
                text=result.text,
                language=result.language,
            )
        )
    return segments


# ---------------------------------------------------------------------------
# faster-whisper (optional fallback engine)
# ---------------------------------------------------------------------------


def _load_faster_whisper_model() -> object:
    device = _resolve_device()
    cache_key = (config.STT_MODEL_NAME, device)
    if cache_key in _faster_whisper_cache:
        return _faster_whisper_cache[cache_key]

    # Lazy import: faster_whisper is only imported when STT_ENGINE=
    # "faster-whisper" is actually invoked, never at module import time.
    from faster_whisper import WhisperModel  # type: ignore[import]

    logger.info(
        "[STT] Loading faster-whisper model %s on device=%s ...",
        config.STT_MODEL_NAME, device,
    )
    model = WhisperModel(
        config.STT_MODEL_NAME,
        device=device,
        compute_type=config.STT_COMPUTE_TYPE,
    )
    _faster_whisper_cache[cache_key] = model
    logger.info("[STT] faster-whisper model loaded and cached.")
    return model


def _transcribe_faster_whisper(wav_path: str, vad_segments: List[Tuple[float, float]]) -> List[TranscriptSegment]:
    if not vad_segments:
        return []

    model = _load_faster_whisper_model()
    audio, sample_rate = _load_audio(wav_path)

    segments: List[TranscriptSegment] = []
    for start, end in vad_segments:
        # One model call per VAD segment (language=None + vad_filter=False —
        # vad_segments already came from our own external VAD pass, so
        # double-VAD-ing here would just re-run silence detection for no
        # benefit) — see module docstring.
        chunk = _slice_chunk(audio, sample_rate, start, end)
        segment_iter, info = model.transcribe(chunk, language=None, vad_filter=False)
        text = "".join(piece.text for piece in segment_iter).strip()
        segments.append(
            TranscriptSegment(
                start=start,
                end=end,
                text=text,
                language=info.language,
            )
        )
    return segments


def unload_model() -> None:
    """Drop cached STT models (both engines) and release their GPU/CPU memory.

    Call once the transcribing stage has produced its segments — neither
    engine's model is needed again for the rest of a media job's pipeline
    (translate/render don't use it). Both caches are cleared regardless of
    config.STT_ENGINE since a job could in principle have warmed either one.
    """
    _qwen3_asr_cache.clear()
    _faster_whisper_cache.clear()

    import gc

    gc.collect()

    try:
        import torch  # type: ignore[import]

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass
