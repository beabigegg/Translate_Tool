"""Voice-activity segmentation for the media STT pipeline (Silero VAD).

Lazy-import + process-lifetime model cache pattern copied from
quality_evaluator.py:25-65 — silero-vad must not be imported at module import
time, only when segment_by_voice_activity() is actually called.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from app.backend import config
from app.backend.utils.logging_utils import logger

# Process-lifetime model cache. silero-vad is CPU-only/ONNX with no device
# argument, so a single fixed key is enough (mirrors quality_evaluator's
# _model_cache shape without needing a device-keyed tuple).
_model_cache: Dict[str, object] = {}
_CACHE_KEY = "silero_vad"


def _load_vad_model() -> object:
    if _CACHE_KEY in _model_cache:
        return _model_cache[_CACHE_KEY]

    # Lazy import: silero-vad is only imported when VAD is actually requested,
    # never at module import time.
    from silero_vad import load_silero_vad  # type: ignore[import]

    logger.info("[VAD] Loading Silero VAD model...")
    model = load_silero_vad()
    _model_cache[_CACHE_KEY] = model
    logger.info("[VAD] Model loaded and cached.")
    return model


def _load_wav_as_tensor(wav_path: str, expected_sample_rate: int = 16000):
    """Load wav_path into the 1-D float32 torch.Tensor get_speech_timestamps
    expects.

    Deliberately does NOT use silero_vad's own read_audio() helper — that
    helper loads via torchaudio.load(), and current torchaudio versions
    require the separate `torchcodec` package for audio I/O (torchaudio >=2.9
    dropped its built-in decoders). Loading via soundfile instead (already a
    hard dependency, used by stt_engine.py) avoids adding torchcodec as
    another transitive dependency just for this one call.

    wav_path is always our own extract_audio()'s output (16kHz mono
    pcm_s16le), so no resampling/channel-mixing is attempted here.
    """
    import numpy as np  # type: ignore[import]
    import soundfile as sf  # type: ignore[import]
    import torch  # type: ignore[import]

    audio, sample_rate = sf.read(wav_path, dtype="float32")
    if sample_rate != expected_sample_rate:
        raise ValueError(
            f"vad_segmenter expects {expected_sample_rate}Hz mono audio "
            f"(extract_audio's output), got {sample_rate}Hz: {wav_path}"
        )
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)
    return torch.from_numpy(audio)


def segment_by_voice_activity(wav_path: str) -> List[Tuple[float, float]]:
    """Return speech-only (start_seconds, end_seconds) windows for wav_path."""
    # Lazy import: silero-vad is only imported when VAD is actually requested,
    # never at module import time.
    from silero_vad import get_speech_timestamps  # type: ignore[import]

    model = _load_vad_model()
    wav = _load_wav_as_tensor(wav_path)
    timestamps = get_speech_timestamps(
        wav,
        model,
        sampling_rate=16000,
        min_silence_duration_ms=config.VAD_MIN_SILENCE_MS,
        return_seconds=True,
    )
    return [(float(ts["start"]), float(ts["end"])) for ts in timestamps]


def unload_model() -> None:
    """Drop the cached Silero VAD model so its memory can be reclaimed.

    Call once the vad_segmenting stage has produced its segments — the model
    is never needed again for the rest of a media job's pipeline (denoise/STT/
    translate/render don't use it), unlike the STT/denoise model caches which
    stay resident for their own single stage only.
    """
    _model_cache.clear()
    import gc

    gc.collect()
