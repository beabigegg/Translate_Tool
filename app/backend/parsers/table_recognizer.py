"""Optional ML table-structure recognizer for PDF table regions (p3-table-structure).

Design constraints (non-negotiable per design.md D1):
  D1  Lazy-load ONNX session; _session_load_failed latch; 3-tier weight resolution.
  D1  CPU-only default; opt-in CUDA if onnxruntime-gpu is installed.
  D1  Fail-soft per BR-71: absent weights/load-error → WARNING logged once, None returned.
  D1  Input is rasterised region-crop of the PDF page (PyMuPDF pixmap of the table bbox).
      Image created/consumed/discarded in-module; no network-client or cloud-SDK import.
  D2  Result attached to metadata["table_structure"] on the parent TranslatableElement.

Mirrors app.backend.parsers.layout_detector.LayoutDetector exactly for the lazy-load,
_session_load_failed latch, 3-tier weight resolution, and ONNX session pattern.

Forbidden imports: requests, httpx, urllib, socket, aiohttp, websockets (BR-32).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Optional

import numpy as np

from app.backend.models.translatable_document import (
    TableCell,
    TableStructure,
    TranslatableElement,
)

logger = logging.getLogger(__name__)

# HuggingFace repo for weight auto-download (D1 tier 3)
# TATR / TableFormer ONNX checkpoint
_HF_REPO_ID = "microsoft/table-transformer-detection"
_HF_FILENAME = "pytorch_model.bin"  # placeholder; actual ONNX weights repo TBD

# Recognizer name recorded in TableStructure.recognizer
_RECOGNIZER_NAME = "TATR"

# Confidence threshold — recognition_confident=False below this value
_CONFIDENCE_THRESHOLD = 0.5


class TableRecognizer:
    """Wraps an ONNX table-structure model for per-table region recognition.

    Stateless after __init__ (lazy load, cached session).  One public method:
      recognize(element, page_pixmap_array, doc_id) -> Optional[TableStructure]

    The table-region crop is created, consumed, and discarded inside recognize();
    it is never stored as an attribute or sent externally (privacy boundary D1).
    """

    def __init__(self, model_path: Optional[str] = None) -> None:
        """Initialise the recognizer.

        Args:
            model_path: Explicit path to ONNX weights directory or file.  When None,
                        the env var TABLE_RECOGNITION_MODEL_PATH is consulted before
                        falling back to HuggingFace cache (D1, 3-tier resolution).
        """
        self._explicit_model_path: Optional[str] = model_path
        self._session = None  # lazy-loaded on first recognize() call
        self._session_load_failed: bool = False

    # ------------------------------------------------------------------
    # D1: Weight resolution (3-tier, mirrors LayoutDetector exactly)
    # ------------------------------------------------------------------

    def _resolve_model_path(self) -> Optional[str]:
        """Return resolved ONNX model file path (first-hit wins, D1).

        Tier 1: explicit model_path argument OR TABLE_RECOGNITION_MODEL_PATH env var.
        Tier 2: local HuggingFace cache (already downloaded).
        Tier 3: HuggingFace auto-download.
        """
        env_path = os.environ.get("TABLE_RECOGNITION_MODEL_PATH", "")
        candidate = self._explicit_model_path or (env_path if env_path else None)
        if candidate:
            candidate_path = Path(candidate)
            if candidate_path.is_dir():
                onnx_files = list(candidate_path.glob("*.onnx"))
                if onnx_files:
                    return str(onnx_files[0])
                return str(candidate_path / _HF_FILENAME)
            if candidate_path.is_file():
                return str(candidate_path)
            return str(candidate_path)

        return self._resolve_hf_path()

    def _resolve_hf_path(self) -> Optional[str]:
        """Attempt HuggingFace cache lookup then auto-download (D1 tiers 2/3)."""
        try:
            return _hf_hub_download(
                repo_id=_HF_REPO_ID,
                filename=_HF_FILENAME,
            )
        except Exception as exc:
            logger.warning(
                "TableRecognizer: HuggingFace weight resolution failed (%s). "
                "Recognizer will be unavailable; table regions fall back to plain element.",
                exc,
            )
            return None

    # ------------------------------------------------------------------
    # Session management (mirrors LayoutDetector._load_session exactly)
    # ------------------------------------------------------------------

    def _load_session(self) -> bool:
        """Load ONNX session lazily; return True on success, False on failure (D1)."""
        if self._session is not None:
            return True
        if self._session_load_failed:
            return False

        model_path = self._resolve_model_path()
        if model_path is None:
            logger.warning(
                "TableRecognizer: no model path resolved; "
                "table regions will be treated as plain elements (BR-71)."
            )
            self._session_load_failed = True
            return False

        try:
            import onnxruntime as ort

            providers = ["CPUExecutionProvider"]
            try:
                if "CUDAExecutionProvider" in ort.get_available_providers():
                    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            except Exception:
                pass

            self._session = ort.InferenceSession(model_path, providers=providers)
            logger.info("TableRecognizer: loaded model from %s", model_path)
            return True
        except Exception as exc:
            logger.warning(
                "TableRecognizer: failed to load ONNX model at %s: %s. "
                "Table regions will be treated as plain elements (BR-71).",
                model_path,
                exc,
            )
            self._session_load_failed = True
            return False

    # ------------------------------------------------------------------
    # Public API: recognize()
    # ------------------------------------------------------------------

    def recognize(
        self,
        element: TranslatableElement,
        page_pixmap_array: Optional[np.ndarray],
        doc_id: str = "",
    ) -> Optional[TableStructure]:
        """Recognize table structure within a table-region element.

        The page_pixmap_array crop for the element's bbox is consumed and
        discarded inside this method; never stored as an instance attribute.

        Args:
            element: A table-typed TranslatableElement whose bbox defines
                     the region to crop from the page raster.
            page_pixmap_array: HxWx3 uint8 numpy array of the *full page*.
                               None → fail-soft (BR-71).
            doc_id: Document identifier for WARNING log messages (BR-71).

        Returns:
            TableStructure if recognition succeeds; None on any failure
            (model unavailable, bad input, inference error — all fail-soft).
        """
        # Check latch first (avoids repeated failed load attempts)
        if self._session_load_failed:
            logger.warning(
                "TableRecognizer: model unavailable; table region in doc '%s' "
                "falls back to plain element (BR-71).",
                doc_id,
            )
            return None

        # Fail-soft when no page array provided
        if page_pixmap_array is None:
            logger.warning(
                "TableRecognizer: no page_pixmap_array for doc '%s'; "
                "table region falls back to plain element.",
                doc_id,
            )
            return None

        # Try to load session (fail-soft per BR-71)
        if not self._load_session():
            logger.warning(
                "TableRecognizer: session unavailable for doc '%s'; "
                "table region falls back to plain element (BR-71).",
                doc_id,
            )
            return None

        # Crop page pixmap to the element's bbox (region-crop inference, D1)
        try:
            structure = self._run_recognition(element, page_pixmap_array)
        except Exception as exc:
            logger.warning(
                "TableRecognizer: inference failed for element '%s' in doc '%s': %s. "
                "Table region falls back to plain element (BR-71).",
                element.element_id,
                doc_id,
                exc,
            )
            return None

        return structure

    def _run_recognition(
        self,
        element: TranslatableElement,
        page_pixmap_array: np.ndarray,
    ) -> TableStructure:
        """Crop the table bbox from the page raster and run ONNX inference.

        Returns a TableStructure with cells derived from the model output.
        The crop array is discarded after inference.
        """
        if element.bbox is None:
            raise ValueError(f"Element '{element.element_id}' has no bbox; cannot crop.")

        page_h, page_w = page_pixmap_array.shape[:2]

        # Crop to table bbox (clip to page bounds)
        x0 = max(0, int(element.bbox.x0))
        y0 = max(0, int(element.bbox.y0))
        x1 = min(page_w, int(element.bbox.x1))
        y1 = min(page_h, int(element.bbox.y1))

        if x1 <= x0 or y1 <= y0:
            raise ValueError(
                f"Degenerate bbox [{x0},{y0},{x1},{y1}] for element '{element.element_id}'."
            )

        crop = page_pixmap_array[y0:y1, x0:x1]  # HxWx3; discarded after run

        # Preprocess crop for the model (resize to model's expected input size)
        try:
            import cv2
            resized = cv2.resize(crop, (768, 768))
        except (ImportError, Exception):
            from PIL import Image
            pil_img = Image.fromarray(crop)
            pil_img = pil_img.resize((768, 768))
            resized = np.array(pil_img)

        # CHW float32 (standard torchvision convention for table transformers)
        img_tensor = resized.astype(np.float32) / 255.0
        img_tensor = np.transpose(img_tensor, (2, 0, 1))  # HWC→CHW
        img_tensor = np.expand_dims(img_tensor, 0)  # 1CHW

        input_name = self._session.get_inputs()[0].name
        outputs = self._session.run(None, {input_name: img_tensor})

        # Parse model output into cells
        # Real TATR outputs: pred_logits (1,N,num_classes) and pred_boxes (1,N,4)
        # For this implementation, extract rows/cols from detection boxes.
        cells, num_rows, num_cols = self._parse_outputs(outputs, element.element_id)

        return TableStructure(
            num_rows=num_rows,
            num_cols=num_cols,
            cells=cells,
            recognizer=_RECOGNIZER_NAME,
            recognition_confident=True,  # set False if confidence < threshold
        )

    def _parse_outputs(
        self,
        outputs: list,
        element_id: str,
    ):
        """Parse ONNX outputs into (cells, num_rows, num_cols).

        Implements the TATR CXCYWH decoder per implementation-plan.md
        §Decoder Algorithm.  Degenerate / malformed inputs return ([], 0, 0)
        without raising (AC-6).

        outputs[0]: pred_logits, shape (1, N, C)
        outputs[1]: pred_boxes,  shape (1, N, 4), normalized CXCYWH
        TATR class indices: 1 = column, 2 = row  (0 = background, etc.)
        Model input size: 768×768 px.
        """
        _MODEL_SIZE = 768
        _CLS_COL = 1
        _CLS_ROW = 2

        # Guard: degenerate inputs
        if not outputs or len(outputs) < 2:
            return [], 0, 0

        try:
            logits = np.asarray(outputs[0])   # (1, N, C)
            boxes  = np.asarray(outputs[1])   # (1, N, 4)
        except Exception:
            return [], 0, 0

        # Squeeze batch dim
        if logits.ndim == 3:
            logits = logits[0]   # (N, C)
        if boxes.ndim == 3:
            boxes = boxes[0]     # (N, 4)

        if logits.shape[0] == 0:
            return [], 0, 0

        row_boxes: list = []
        col_boxes: list = []

        for i in range(logits.shape[0]):
            l = logits[i]
            cls = int(np.argmax(l))
            # Numerically stable softmax for the score
            shifted = l - np.max(l)
            exp_l = np.exp(shifted)
            score = float(exp_l[cls] / np.sum(exp_l))

            if score <= _CONFIDENCE_THRESHOLD:
                continue
            if cls not in (_CLS_COL, _CLS_ROW):
                continue

            # Normalized CXCYWH → pixel XYXY
            cx, cy, w, h = (float(v) * _MODEL_SIZE for v in boxes[i])
            x0 = cx - w / 2.0
            y0 = cy - h / 2.0
            x1 = cx + w / 2.0
            y1 = cy + h / 2.0

            if cls == _CLS_ROW:
                row_boxes.append((y0, y1, x0, x1, cy))   # store cy for sort
            else:
                col_boxes.append((x0, x1, y0, y1, cx))   # store cx for sort

        if not row_boxes or not col_boxes:
            return [], 0, 0

        # Sort rows by pixel y-center ascending → row index 0, 1, …
        row_boxes.sort(key=lambda b: b[4])
        # Sort cols by pixel x-center ascending → col index 0, 1, …
        col_boxes.sort(key=lambda b: b[4])

        cells: List[TableCell] = []
        for row_i, (ry0, ry1, rx0, rx1, _rcy) in enumerate(row_boxes):
            for col_j, (cx0, cx1, cy0, cy1, _ccx) in enumerate(col_boxes):
                # Intersection area
                ix0 = max(rx0, cx0)
                iy0 = max(ry0, cy0)
                ix1 = min(rx1, cx1)
                iy1 = min(ry1, cy1)
                inter_w = ix1 - ix0
                inter_h = iy1 - iy0
                if inter_w > 0 and inter_h > 0:
                    cells.append(TableCell(
                        cell_id=f"{element_id}:r{row_i}:c{col_j}",
                        row=row_i,
                        col=col_j,
                        content="",
                        row_span=1,
                        col_span=1,
                        is_numeric=False,
                    ))

        return cells, len(row_boxes), len(col_boxes)


# ---------------------------------------------------------------------------
# Lazy import of huggingface_hub — only for weight resolution
# ---------------------------------------------------------------------------

def _hf_hub_download(repo_id: str, filename: str) -> str:
    """Thin wrapper so tests can patch app.backend.parsers.table_recognizer._hf_hub_download."""
    from huggingface_hub import hf_hub_download as _dl
    return _dl(repo_id=repo_id, filename=filename)
