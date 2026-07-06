"""Post-render layout QA — output-side layout-fidelity confirmation.

Canonical home of the layout-fidelity metrics (BIoU, residual source text,
truncation rate). ``tests/metrics/`` re-exports from this module so the CI
gate commands referenced in ``contracts/ci/ci-gate-contract.md`` keep working.

Runtime entry point
-------------------
run_layout_qa(doc, output_path, target_lang, layout_mode, draw_mask) -> dict|None
    Re-opens the rendered output PDF and measures how faithfully the layout
    survived translation insertion. Fail-soft: any exception is logged and
    ``None`` is returned; layout QA must never fail a job.

Metric API (stdlib-only, duck-typed — unchanged from tests/metrics/)
--------------------------------------------------------------------
BIOU_REGRESSION_BUDGET : float
compute_biou(source_bboxes, rendered_bboxes) -> float
check_residual_text(page, whiteover_bboxes) -> list[dict]
compute_truncation_rate(elements) -> dict
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

BIOU_REGRESSION_BUDGET: float = 0.8

# Length of the normalized source-text prefix used for residual detection.
_RESIDUAL_PREFIX_LEN = 20


def layout_qa_enabled() -> bool:
    """Read the LAYOUT_QA_ENABLED flag at runtime (mirrors LAYOUT_DETECTOR_ENABLED)."""
    return os.environ.get("LAYOUT_QA_ENABLED", "true").lower() in ("1", "true", "yes")


# ---------------------------------------------------------------------------
# BIoU — bounding-box IoU layout-fidelity metric
# ---------------------------------------------------------------------------

def _iou(a, b) -> float:
    """Compute IoU between two bounding boxes (duck-typed x0/y0/x1/y1)."""
    inter_x = max(0.0, min(a.x1, b.x1) - max(a.x0, b.x0))
    inter_y = max(0.0, min(a.y1, b.y1) - max(a.y0, b.y0))
    intersection = inter_x * inter_y
    area_a = (a.x1 - a.x0) * (a.y1 - a.y0)
    area_b = (b.x1 - b.x0) * (b.y1 - b.y0)
    union = area_a + area_b - intersection
    if union == 0.0:
        return 0.0
    return intersection / union


def compute_biou(source_bboxes: list, rendered_bboxes: list) -> float:
    """Return mean best-match IoU for each source bbox against rendered bboxes.

    For each source bbox, find the rendered bbox with the highest IoU.
    Return the mean of those per-source best-match scores.

    Returns 0.0 when either list is empty.
    """
    if not source_bboxes or not rendered_bboxes:
        return 0.0

    total = 0.0
    for src in source_bboxes:
        best = max(_iou(src, rnd) for rnd in rendered_bboxes)
        total += best
    return total / len(source_bboxes)


# ---------------------------------------------------------------------------
# Residual-text detection
# ---------------------------------------------------------------------------

def check_residual_text(page, whiteover_bboxes: list) -> list:
    """Detect text that remains visible inside white-over bounding-box regions.

    For each bbox in *whiteover_bboxes*, queries ``page.get_text("blocks",
    clip=(bbox.x0, bbox.y0, bbox.x1, bbox.y1))``.  If any text blocks are
    returned, a record is appended to the result list.

    Parameters
    ----------
    page:
        A page object with a ``get_text(mode, clip=...)`` method.
    whiteover_bboxes:
        Iterable of bbox objects with x0, y0, x1, y1 attributes.

    Returns
    -------
    list of dict
        Each dict has keys ``bbox``, ``text``, and ``blocks``.
        Empty list when no residual text is found.
    """
    records = []
    for bbox in whiteover_bboxes:
        blocks = page.get_text("blocks", clip=(bbox.x0, bbox.y0, bbox.x1, bbox.y1))
        if blocks:
            text = " ".join(b[4] for b in blocks if len(b) > 4)
            records.append({"bbox": bbox, "text": text, "blocks": blocks})
    return records


# ---------------------------------------------------------------------------
# Truncation rate
# ---------------------------------------------------------------------------

def compute_truncation_rate(elements: list) -> dict:
    """Compute the truncation rate across a list of translatable elements.

    Parameters
    ----------
    elements:
        Iterable of element objects.  Each must have:
        - ``render_truncated`` (bool)
        - ``metadata`` (dict, optional via .get)
        - ``bbox`` (may be None; does not affect counting)

    Returns
    -------
    dict with keys:
        count             -- number of elements where render_truncated is True
        total             -- total number of elements
        ratio             -- count / total (0.0 when total == 0)
        overflow_area_sum -- sum of metadata["overflow_area"] for truncated elements
    """
    total = len(elements)
    count = 0
    overflow_area_sum = 0.0

    for el in elements:
        if el.render_truncated:
            count += 1
            overflow_area_sum += getattr(el, "metadata", {}).get("overflow_area", 0.0)

    ratio = count / total if total > 0 else 0.0

    return {
        "count": count,
        "total": total,
        "ratio": ratio,
        "overflow_area_sum": overflow_area_sum,
    }


# ---------------------------------------------------------------------------
# Runtime output-side QA (fail-soft)
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Whitespace-insensitive normalization for residual-source matching."""
    return "".join(text.split()).lower()


def _residual_source_blocks(out_page, page_elements) -> int:
    """Count elements whose SOURCE text is still readable inside their bbox.

    In overlay mode with masking enabled the original text is removed via
    redaction and the translation is written into the same bbox, so text
    found in the region is normally the translation. A residual is flagged
    only when the source content itself (normalized prefix) survives in the
    extracted text — the exact redaction-failure mode this metric targets.
    """
    residual = 0
    for elem in page_elements:
        bbox = elem.bbox
        source = _normalize(elem.content.strip())[:_RESIDUAL_PREFIX_LEN]
        if not source or bbox is None:
            continue
        records = check_residual_text(out_page, [bbox])
        if records and source in _normalize(records[0]["text"]):
            residual += 1
    return residual


def run_layout_qa(
    doc,
    output_path: str,
    target_lang: str,
    layout_mode: str,
    draw_mask: bool,
) -> Optional[dict]:
    """Measure layout fidelity of a rendered output PDF (fail-soft).

    Metrics per layout_mode:
    - ``overlay``: BIoU (source element bboxes vs output text-block bboxes,
      page-aligned), residual source text (only when ``draw_mask`` — without
      masking the source text intentionally remains), truncation rate.
    - ``side_by_side``: truncation rate only — pages are recomposed, so
      bbox-identity metrics do not apply (reported as ``None``).

    Returns a JSON-serializable dict, or ``None`` when QA could not run.
    ``passed`` is True when every *measured* check is clean: BIoU >= budget,
    zero residual blocks, zero truncated blocks.
    """
    try:
        import fitz

        elements = [
            e for e in doc.get_elements_in_reading_order()
            if e.should_translate and e.content.strip()
        ]
        truncation = compute_truncation_rate(elements)

        biou_score: Optional[float] = None
        residual_blocks: Optional[int] = None

        if layout_mode == "overlay":
            with fitz.open(output_path) as out_pdf:
                by_page: dict = {}
                for e in elements:
                    if e.bbox is not None:
                        by_page.setdefault(e.page_num, []).append(e)

                scores = []
                residual_total = 0
                for page_num, page_elements in by_page.items():
                    page_index = page_num - 1
                    if page_index < 0 or page_index >= out_pdf.page_count:
                        continue
                    out_page = out_pdf[page_index]
                    rendered = [
                        fitz.Rect(b[:4]) for b in out_page.get_text("blocks")
                        if len(b) > 4 and str(b[4]).strip()
                    ]
                    src = [e.bbox for e in page_elements]
                    page_biou = compute_biou(src, rendered)
                    scores.append((page_biou, len(src)))
                    if draw_mask:
                        residual_total += _residual_source_blocks(
                            out_page, page_elements
                        )

                if scores:
                    weight = sum(n for _, n in scores)
                    biou_score = (
                        sum(s * n for s, n in scores) / weight if weight else 0.0
                    )
                if draw_mask:
                    residual_blocks = residual_total

        checks = []
        if biou_score is not None:
            checks.append(biou_score >= BIOU_REGRESSION_BUDGET)
        if residual_blocks is not None:
            checks.append(residual_blocks == 0)
        checks.append(truncation["count"] == 0)

        return {
            "file": os.path.basename(output_path),
            "target_lang": target_lang,
            "layout_mode": layout_mode,
            "biou": round(biou_score, 4) if biou_score is not None else None,
            "biou_budget": BIOU_REGRESSION_BUDGET,
            "residual_text_blocks": residual_blocks,
            "truncated_blocks": truncation["count"],
            "total_blocks": truncation["total"],
            "truncation_ratio": round(truncation["ratio"], 4),
            "passed": all(checks),
        }
    except Exception as exc:
        logger.warning(f"[LayoutQA] skipped for {output_path}: {exc}")
        return None
