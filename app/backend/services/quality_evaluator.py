"""COMET/xCOMET neural quality evaluation service (p2-comet-qe).

Design decisions:
  D-3: Dedicated module with narrow interface (load_model, score_blocks).
  D-4: Reference-free input shape (source=src, hypothesis=mt).
  D-5: Lazy, process-lifetime cached model load; never import comet at module top
       (BR-57: no model loaded when QE_ENABLED=false).

Mock seam: app.backend.services.quality_evaluator.load_model
"""

from __future__ import annotations

import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# Process-lifetime model cache: maps (model_name, device) → loaded model object.
_model_cache: Dict[Tuple[str, str], object] = {}

_VALID_DEVICES = {"cpu", "cuda", "mps"}


def load_model(model_name: str, device: str) -> object:
    """Load (or return cached) COMET model.

    Lazy loads ``comet`` INSIDE this function so that importing this module
    never loads torch (BR-57 — no model loaded when QE_ENABLED=false).

    Args:
        model_name: HuggingFace model identifier, e.g.
            ``"Unbabel/wmt22-cometkiwi-da"``.
        device: Torch device string.  Invalid values fall back to ``"cpu"``
            with a WARNING log (D-5).

    Returns:
        Loaded COMET model ready for prediction.

    Raises:
        Exception: Propagated on load failure so the caller (IP-5) records
            ``qe_status="unavailable"``.  The cache is NOT poisoned, so a
            later job may retry.
    """
    if device not in _VALID_DEVICES:
        logger.warning(
            "[QE] Invalid QE_DEVICE %r — falling back to 'cpu'.", device
        )
        device = "cpu"

    cache_key = (model_name, device)
    if cache_key in _model_cache:
        return _model_cache[cache_key]

    # Lazy import: comet (and therefore torch) is only imported when QE is
    # actually requested, never at module import time.
    from comet import load_from_checkpoint, download_model  # type: ignore[import]

    logger.info("[QE] Downloading/loading model %s on device=%s …", model_name, device)
    model_path = download_model(model_name)
    model = load_from_checkpoint(model_path)

    _model_cache[cache_key] = model
    logger.info("[QE] Model loaded and cached: %s", model_name)
    return model


def score_blocks(
    model: object,
    blocks: List[Tuple[str, str]],
    device: str = "cpu",
) -> List[float]:
    """Score translated blocks with a reference-free COMET model.

    Args:
        model: Loaded COMET model (returned by :func:`load_model`).
        blocks: List of ``(src, mt)`` pairs — NO block_id (block_id is owned
            by the caller in IP-5).
        device: Torch device string used at load time (``"cpu"`` or ``"cuda"``).
            When ``"cuda"``, prediction runs on 1 GPU (PyTorch Lightning gpus=1).

    Returns:
        List of float scores, one per input block.
        On any exception returns ``[]`` (QE failure path → caller maps to
        ``qe_status="unavailable"``).
    """
    if not blocks:
        return []
    try:
        data = [{"src": src, "mt": mt} for src, mt in blocks]
        gpus = 1 if device == "cuda" else 0
        prediction = model.predict(data, batch_size=8, gpus=gpus)  # type: ignore[union-attr]
        # unbabel-comet returns a ModelOutput with .scores list
        scores: List[float] = prediction.scores
        return scores
    except Exception as exc:
        logger.warning("[QE] score_blocks failed: %s: %s", type(exc).__name__, exc)
        return []
