"""Layout detector using Docling heron-101 ONNX model (p2-layout-detection).

Design constraints (non-negotiable per design.md D-1..D-5):
  D-1  CPU-only onnxruntime declared; CPUExecutionProvider default.
  D-2  Fail-soft: any inference error → WARNING + fallback to heuristic; never raise.
  D-3  Privacy boundary: page pixmap created/consumed/discarded inside detect(); no
       network/IO client imports; page image never serialised or sent.
  D-4  HERON_LABEL_MAP is the single source of truth for label → ElementType wire value.
  D-5  3-tier weight resolution: env-var path → local HF cache → HF auto-download.

Forbidden imports: requests, httpx, urllib, socket, aiohttp, websockets (BR-32).
Forbidden packages: AGPL-licensed layout detectors (AC-8), GPU-only onnxruntime variants (AC-8 / dependency gate).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Optional

import numpy as np

from app.backend.models.translatable_document import (
    BoundingBox,
    ElementType,
    TranslatableElement,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# D-4: Label mapping — single source of truth (module constant)
# Docling heron-101 DocLayNet-style labels → ElementType wire values (lowercase)
# Unknown label → "text" (never raise)
# ---------------------------------------------------------------------------
HERON_LABEL_MAP: dict[str, str] = {
    "Text":           ElementType.TEXT.value,
    "Paragraph":      ElementType.TEXT.value,
    "Title":          ElementType.TITLE.value,
    "Section-header": ElementType.TITLE.value,
    "Page-header":    ElementType.HEADER.value,
    "Page-footer":    ElementType.FOOTER.value,
    "Table":          ElementType.TABLE.value,
    "Picture":        ElementType.FIGURE.value,
    "Figure":         ElementType.FIGURE.value,
    "Formula":        ElementType.FORMULA.value,
    "List-item":      ElementType.LIST_ITEM.value,
    "Caption":        ElementType.CAPTION.value,
    "Footnote":       ElementType.FOOTNOTE.value,
}

# heron-101 integer class index → label name (DocLayNet order)
_HERON_CLASS_NAMES: list[str] = [
    "Text",          # 0
    "Paragraph",     # 1
    "Title",         # 2
    "Section-header",# 3
    "Page-header",   # 4
    "Page-footer",   # 5
    "Table",         # 6
    "Picture",       # 7
    "Figure",        # 8
    "Formula",       # 9
    "List-item",     # 10
    "Caption",       # 11
    "Footnote",      # 12
]

# HuggingFace repo for weight auto-download (D-5 tier 3)
_HF_REPO_ID = "docling-project/docling-layout-heron-onnx"
_HF_FILENAME = "model.onnx"

# Score threshold for accepting a detection box
_SCORE_THRESHOLD = 0.4

# Minimum horizontal gap (normalised 0..1) to treat two region centres as separate columns
_COLUMN_GAP_THRESHOLD = 0.1


def _map_label(label_name: str) -> ElementType:
    """Map a heron label string to ElementType; unknown → TEXT (never raise)."""
    wire_value = HERON_LABEL_MAP.get(label_name, ElementType.TEXT.value)
    try:
        return ElementType(wire_value)
    except ValueError:
        return ElementType.TEXT


def _map_class_index(class_idx: int) -> ElementType:
    """Map an integer class index to ElementType."""
    if 0 <= class_idx < len(_HERON_CLASS_NAMES):
        return _map_label(_HERON_CLASS_NAMES[class_idx])
    return ElementType.TEXT


def _heuristic_reading_order(elements: List[TranslatableElement]) -> None:
    """Assign reading_order using the round(y0/10)*10 bucket heuristic (legacy fallback).

    Mutates elements in-place.  This is the retained fallback from pdf_parser.py
    (design.md D-2; implementation-plan.md §_sort_by_reading_order retained).
    """

    def _sort_key(e: TranslatableElement):
        if e.bbox:
            y_rounded = round(e.bbox.y0 / 10) * 10
            return (e.page_num, y_rounded, e.bbox.x0)
        return (e.page_num, 0, 0)

    sorted_elements = sorted(elements, key=_sort_key)
    for idx, elem in enumerate(sorted_elements):
        elem.reading_order = idx


class LayoutDetector:
    """Wraps the Docling heron-101 ONNX model for per-page layout detection.

    Stateless after __init__ (lazy load, cached session).  One public method:
      detect(page_pixmap_array, elements) -> None

    The page image is created, consumed, and discarded inside detect(); it is
    never stored as an attribute or sent externally (privacy boundary D-3).
    """

    def __init__(self, model_path: Optional[str] = None) -> None:
        """Initialise the detector.

        Args:
            model_path: Explicit path to ONNX weights directory.  When None,
                        the env var LAYOUT_DETECTOR_MODEL_PATH is consulted
                        before falling back to the HuggingFace cache (D-5).
        """
        self._explicit_model_path: Optional[str] = model_path
        self._session = None  # lazy-loaded on first detect() call
        self._session_load_failed: bool = False

    # ------------------------------------------------------------------
    # D-5: Weight resolution
    # ------------------------------------------------------------------

    def _resolve_model_path(self) -> Optional[str]:
        """Return resolved ONNX model file path (first-hit wins, D-5).

        Tier 1: explicit model_path argument OR LAYOUT_DETECTOR_MODEL_PATH env var.
        Tier 2: local HuggingFace cache (already downloaded).
        Tier 3: HuggingFace auto-download.
        """
        # Tier 1: explicit path from constructor or env var
        env_path = os.environ.get("LAYOUT_DETECTOR_MODEL_PATH", "")
        candidate = self._explicit_model_path or (env_path if env_path else None)
        if candidate:
            candidate_path = Path(candidate)
            # Accept a directory (look for .onnx inside) or a direct .onnx file
            if candidate_path.is_dir():
                onnx_files = list(candidate_path.glob("*.onnx"))
                if onnx_files:
                    return str(onnx_files[0])
                # Dir exists but empty — still return the dir so InferenceSession
                # can raise FileNotFoundError (triggers fail-soft in _load_session)
                return str(candidate_path / _HF_FILENAME)
            if candidate_path.is_file():
                return str(candidate_path)
            # Path given but does not exist — return it so we get a clear error
            return str(candidate_path)

        # Tier 2 + 3: HuggingFace cache / auto-download
        return self._resolve_hf_path()

    def _resolve_hf_path(self) -> Optional[str]:
        """Attempt HuggingFace cache lookup then auto-download (D-5 tiers 2/3)."""
        try:
            return hf_hub_download(
                repo_id=_HF_REPO_ID,
                filename=_HF_FILENAME,
            )
        except Exception as exc:
            logger.warning(
                "LayoutDetector: HuggingFace weight resolution failed (%s). "
                "Detector will be unavailable; heuristic fallback active.",
                exc,
            )
            return None

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def _load_session(self) -> bool:
        """Load ONNX session lazily; return True on success, False on failure (D-2)."""
        if self._session is not None:
            return True
        if self._session_load_failed:
            return False

        model_path = self._resolve_model_path()
        if model_path is None:
            logger.warning(
                "LayoutDetector: no model path resolved; "
                "heuristic fallback active for all pages."
            )
            self._session_load_failed = True
            return False

        try:
            import onnxruntime as ort

            providers = ["CPUExecutionProvider"]
            # Auto-select CUDA if onnxruntime-gpu is installed out-of-band (D-1)
            try:
                if "CUDAExecutionProvider" in ort.get_available_providers():
                    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            except Exception:
                pass

            self._session = ort.InferenceSession(model_path, providers=providers)
            logger.info("LayoutDetector: loaded model from %s", model_path)
            return True
        except Exception as exc:
            logger.warning(
                "LayoutDetector: failed to load ONNX model at %s: %s. "
                "Heuristic fallback active.",
                model_path,
                exc,
            )
            self._session_load_failed = True
            return False

    # ------------------------------------------------------------------
    # D-3: detect() — public API
    # ------------------------------------------------------------------

    def detect(
        self,
        page_pixmap_array: np.ndarray,
        elements: List[TranslatableElement],
    ) -> Optional[dict]:
        """Detect layout regions and assign element_type + reading_order in-place.

        The page_pixmap_array is consumed and discarded inside this method;
        it is never stored as an instance attribute (privacy boundary D-3).

        Args:
            page_pixmap_array: HxWx3 uint8 numpy array of the page raster.
                               None or invalid → fail-soft to heuristic.
            elements: Page elements to type and order in-place.

        Returns:
            Optional[dict]: viz page dict with "detector" and "boxes" keys,
                            or None when there is nothing to visualise.
        """
        # Check LAYOUT_DETECTOR_ENABLED flag
        enabled_raw = os.environ.get("LAYOUT_DETECTOR_ENABLED", "true").lower()
        if enabled_raw not in ("1", "true", "yes"):
            _heuristic_reading_order(elements)
            return {"detector": "disabled", "boxes": []}

        if not elements:
            return None

        # Validate pixmap (fail-soft on bad input, D-2)
        if page_pixmap_array is None:
            logger.warning(
                "LayoutDetector: page_pixmap_array is None (unrasterisable page); "
                "falling back to heuristic."
            )
            _heuristic_reading_order(elements)
            return {"detector": "heuristic", "boxes": []}

        try:
            if not isinstance(page_pixmap_array, np.ndarray) or page_pixmap_array.ndim != 3:
                raise ValueError(
                    f"Expected HxWx3 ndarray, got {type(page_pixmap_array)}"
                )
            page_height, page_width = page_pixmap_array.shape[:2]
        except Exception as exc:
            logger.warning(
                "LayoutDetector: invalid page_pixmap_array (%s); "
                "falling back to heuristic.",
                exc,
            )
            _heuristic_reading_order(elements)
            return {"detector": "heuristic", "boxes": []}

        # Load ONNX session (lazy, cached, fail-soft)
        if not self._load_session():
            _heuristic_reading_order(elements)
            return {"detector": "heuristic", "boxes": []}

        # Run inference (D-2: any error → WARNING + fallback)
        try:
            boxes, scores, labels = self._run_inference(
                page_pixmap_array, page_height, page_width
            )
        except Exception as exc:
            logger.warning(
                "LayoutDetector: inference failed on page (reason: %s); "
                "falling back to heuristic.",
                type(exc).__name__,
            )
            _heuristic_reading_order(elements)
            return {"detector": "heuristic", "boxes": []}
        # page_pixmap_array reference is no longer used; let GC reclaim it

        # Filter by confidence threshold
        accepted_regions = [
            (box, score, label_idx)
            for box, score, label_idx in zip(boxes, scores, labels)
            if score >= _SCORE_THRESHOLD
        ]

        if not accepted_regions:
            # No confident detections — fall back to heuristic
            _heuristic_reading_order(elements)
            return {"detector": "heuristic", "boxes": []}

        # Assign element_type from enclosing region (geometric containment, D-3)
        self._assign_element_types(
            elements, accepted_regions, page_height, page_width
        )

        # Assign reading_order: column-aware ordering (D-3)
        self._assign_reading_order(elements, accepted_regions, page_height, page_width)

        # Build viz dict for ONNX detections
        return {
            "detector": "onnx",
            "boxes": [
                {
                    "type": _map_class_index(int(label_idx)).value,
                    "bbox": box.tolist(),
                    "score": float(score),
                    "preview": "",
                }
                for box, score, label_idx in accepted_regions
            ],
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_inference(
        self,
        page_pixmap_array: np.ndarray,
        page_height: int,
        page_width: int,
    ):
        """Run ONNX session and return (boxes, scores, labels).

        Model: docling-layout-heron-onnx (RT-DETRv2 variant).
        Inputs:  images (batch,3,640,640) uint8
                 orig_target_sizes (batch,2) int64  — original [W, H] (width first)
        Outputs: labels (batch,300) int64
                 boxes  (batch,300,4) float — pixel coords in original image space
                 scores (batch,300) float
        Boxes are returned normalised [x0,y0,x1,y1] 0..1 for compatibility.
        """
        # Preprocess: resize to 640x640, keep uint8 (model requires uint8 input)
        try:
            import cv2  # optional; fall back to PIL if not installed
            img = cv2.resize(page_pixmap_array, (640, 640))
        except (ImportError, Exception):
            # PIL fallback (always available via Pillow)
            from PIL import Image
            pil = Image.fromarray(page_pixmap_array)
            pil = pil.resize((640, 640))
            img = np.array(pil)

        # HWC uint8 → CHW uint8 (do NOT convert to float; model expects uint8)
        img = np.transpose(img, (2, 0, 1))  # CHW
        img = np.expand_dims(img, 0)        # 1CHW uint8

        # orig_target_sizes: this heron model variant uses [W, H] order (width first),
        # NOT the standard [H, W] that most RT-DETR implementations use.
        # Evidence: with [H, W], x values exceed 1.0 and y values max at W/H ≈ 0.76.
        orig_sizes = np.array([[page_width, page_height]], dtype=np.int64)
        input_names = [inp.name for inp in self._session.get_inputs()]
        feed = {input_names[0]: img, input_names[1]: orig_sizes}

        outputs = self._session.run(None, feed)

        # Output order: labels (batch,300), boxes (batch,300,4), scores (batch,300)
        pred_labels = outputs[0][0].astype(np.int32)   # (300,) int
        pred_boxes  = outputs[1][0].astype(np.float32) # (300, 4) pixel coords
        pred_scores = outputs[2][0].astype(np.float32) # (300,) float

        # Normalise boxes to [0,1] so the rest of the pipeline is unchanged
        norm_boxes = pred_boxes.copy()
        norm_boxes[:, [0, 2]] /= max(page_width, 1)
        norm_boxes[:, [1, 3]] /= max(page_height, 1)

        return norm_boxes, pred_scores, pred_labels

    def _assign_element_types(
        self,
        elements: List[TranslatableElement],
        regions,
        page_height: int,
        page_width: int,
    ) -> None:
        """For each element, find its enclosing region and set element_type."""
        for elem in elements:
            if elem.bbox is None:
                continue
            best_region = self._find_best_region(
                elem.bbox, regions, page_height, page_width
            )
            if best_region is not None:
                box, score, label_idx = best_region
                element_type = _map_class_index(int(label_idx))
                # Don't overwrite TABLE_CELL (set by _detect_and_mark_tables)
                if elem.element_type != ElementType.TABLE_CELL:
                    elem.element_type = element_type
                    # Figures and formulas contain no translatable text
                    if element_type in (ElementType.FIGURE, ElementType.FORMULA):
                        elem.should_translate = False
                # Store provenance in metadata (D-3 — no parallel struct)
                elem.metadata["layout_region"] = [float(v) for v in box]
                elem.metadata["layout_confidence"] = float(score)

    def _find_best_region(
        self,
        elem_bbox: BoundingBox,
        regions,
        page_height: int,
        page_width: int,
    ):
        """Return the region that best contains the element (largest overlap)."""
        best = None
        best_overlap = 0.0

        for box, score, label_idx in regions:
            # box is normalised [x0,y0,x1,y1]
            rx0 = float(box[0]) * page_width
            ry0 = float(box[1]) * page_height
            rx1 = float(box[2]) * page_width
            ry1 = float(box[3]) * page_height

            overlap = self._overlap_area(elem_bbox, rx0, ry0, rx1, ry1)
            if overlap > best_overlap:
                best_overlap = overlap
                best = (box, score, label_idx)

        return best

    @staticmethod
    def _overlap_area(
        elem: BoundingBox,
        rx0: float,
        ry0: float,
        rx1: float,
        ry1: float,
    ) -> float:
        """Compute overlap area between element bbox and a region rect."""
        ix0 = max(elem.x0, rx0)
        iy0 = max(elem.y0, ry0)
        ix1 = min(elem.x1, rx1)
        iy1 = min(elem.y1, ry1)
        if ix1 <= ix0 or iy1 <= iy0:
            return 0.0
        return (ix1 - ix0) * (iy1 - iy0)

    def _assign_reading_order(
        self,
        elements: List[TranslatableElement],
        regions,
        page_height: int,
        page_width: int,
    ) -> None:
        """Column-aware reading order assignment (D-3).

        Algorithm:
        1. Sort regions by x-centre to detect column layout.
        2. Group regions into columns (gap between x-centres > threshold).
        3. Within each column, sort regions by y-centre (top to bottom).
        4. Order columns left to right.
        5. Within each region, sort elements by (y0, x0).
        6. Assign 0-based sequential reading_order.
        """
        # Filter to accepted regions
        accepted = [
            (box, score, label_idx)
            for box, score, label_idx in regions
            if score >= _SCORE_THRESHOLD
        ]

        if not accepted:
            _heuristic_reading_order(elements)
            return

        # Compute region centres (normalised)
        def _region_centre(box):
            return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)

        regions_with_centre = [
            (box, score, label_idx, _region_centre(box))
            for box, score, label_idx in accepted
        ]

        # Sort regions by x-centre to detect columns
        regions_by_x = sorted(regions_with_centre, key=lambda r: r[3][0])

        # Group into columns: new column when x-centre gap > threshold
        columns: list[list] = []
        current_col: list = []
        prev_x = None
        for region in regions_by_x:
            cx = region[3][0]
            if prev_x is None or (cx - prev_x) > _COLUMN_GAP_THRESHOLD:
                if current_col:
                    columns.append(current_col)
                current_col = [region]
            else:
                current_col.append(region)
            prev_x = cx
        if current_col:
            columns.append(current_col)

        # Within each column, sort regions top-to-bottom by y-centre
        for col in columns:
            col.sort(key=lambda r: r[3][1])

        # Build ordered list of regions across all columns (left col first)
        ordered_regions = [region for col in columns for region in col]

        # Map each element to its best region index
        elem_region_idx: dict[str, int] = {}
        for elem in elements:
            if elem.bbox is None:
                continue
            best_idx = -1
            best_overlap = 0.0
            for r_idx, (box, score, label_idx, centre) in enumerate(ordered_regions):
                rx0 = float(box[0]) * page_width
                ry0 = float(box[1]) * page_height
                rx1 = float(box[2]) * page_width
                ry1 = float(box[3]) * page_height
                overlap = self._overlap_area(elem.bbox, rx0, ry0, rx1, ry1)
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_idx = r_idx
            elem_region_idx[elem.element_id] = best_idx

        # Sort elements: (region_index, y0, x0); unassigned elements (-1) go last
        def _order_key(e: TranslatableElement):
            r_idx = elem_region_idx.get(e.element_id, -1)
            y0 = e.bbox.y0 if e.bbox else 0.0
            x0 = e.bbox.x0 if e.bbox else 0.0
            return (r_idx if r_idx >= 0 else 9999, y0, x0)

        sorted_elements = sorted(elements, key=_order_key)
        for idx, elem in enumerate(sorted_elements):
            elem.reading_order = idx


# ---------------------------------------------------------------------------
# Lazy import of huggingface_hub — only for weight resolution, never for page data
# ---------------------------------------------------------------------------

def hf_hub_download(repo_id: str, filename: str) -> str:
    """Thin wrapper so tests can patch app.backend.parsers.layout_detector.hf_hub_download."""
    from huggingface_hub import hf_hub_download as _hf_hub_download
    return _hf_hub_download(repo_id=repo_id, filename=filename)
