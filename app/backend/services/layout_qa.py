"""Layout-QA safety net for the PDF->PDF render path (layout-qa-safety-net, BR-106).

Runtime, output-side quality check: after a PDF is rendered, ``run_layout_qa()``
re-opens the rendered output and measures (a) mean best-match bounding-box IoU
(BIoU) regression against the source IR bboxes and (b) residual untranslated
source text still visible inside its own bbox. On regression it emits exactly
ONE aggregated warning string via the existing ``warnings_callback`` ->
``_record_job_warning`` plumbing (BR-96, BR-104). Additive, observational,
fail-soft: never raises, never alters the rendered output, never fails a job.

Metric core (``BIOU_REGRESSION_BUDGET``, ``_iou``, ``compute_biou``,
``check_residual_text``, ``compute_truncation_rate``) is promoted here
(ADR-0015) from ``tests/metrics/*`` verbatim -- this module is the single
source of truth; ``tests/metrics/{biou,residual_text,truncation_rate}.py`` are
now thin re-export shims so the CI-gate tests and this runtime service share
one implementation. Metric bodies are stdlib-only and duck-typed; ``fitz`` is
imported lazily inside ``run_layout_qa`` so importing this module never pulls
in a hard PyMuPDF dependency (ADR-0015).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Callable, Dict, List, Optional

from app.backend.config import LAYOUT_QA_MAX_BOXES_PER_PAGE

# ---------------------------------------------------------------------------
# Metric core (moved verbatim from tests/metrics/biou.py, residual_text.py,
# truncation_rate.py -- do NOT "improve" this math; see implementation-plan.md
# "Metric bodies move verbatim").
# ---------------------------------------------------------------------------

BIOU_REGRESSION_BUDGET: float = 0.8


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
# run_layout_qa composition (BR-106)
# ---------------------------------------------------------------------------

# Mirrors TEXT_TRUNCATION_WARNING_TEMPLATE (pdf_processor.py) shape: names the
# doc id + affected page numbers in one aggregated string.
LAYOUT_QA_WARNING_TEMPLATE = (
    "'{doc_id}' page(s) {pages}: layout-QA safety net detected {signal} in the "
    "rendered output"
)

_BIOU_SIGNAL_TEXT = "layout fidelity regression (mean BIoU below budget)"
_RESIDUAL_SIGNAL_TEXT = "residual untranslated source text"


@dataclass
class LayoutQAResult:
    """Return value of ``run_layout_qa`` for test/caller assertions."""

    mean_biou: float
    biou_regressed: bool
    residual_pages: List[int] = field(default_factory=list)
    warned: bool = False


def _normalize(text: str) -> str:
    """Strip + casefold + collapse internal whitespace for text comparison."""
    return " ".join((text or "").strip().casefold().split())


def _rendered_page_bboxes(page) -> list:
    """Extract bounding boxes of every text block on a rendered fitz page."""
    blocks = page.get_text("blocks")
    return [SimpleNamespace(x0=b[0], y0=b[1], x1=b[2], y1=b[3]) for b in blocks]


def run_layout_qa(
    doc,
    output_path: str,
    doc_id: str,
    warnings_callback: Optional[Callable[[str], None]],
    log=None,
) -> Optional[LayoutQAResult]:
    """Post-render layout-QA safety net (BR-106). PDF->PDF path only.

    Re-opens ``output_path`` (lazy ``import fitz``) and, per page, compares
    the source IR bboxes (``doc.elements``) against the rendered output:
    mean best-match BIoU regression and residual untranslated source text
    remaining inside its own bbox region. Pages whose source or rendered box
    count exceeds ``LAYOUT_QA_MAX_BOXES_PER_PAGE`` are skipped and logged.

    On regression (mean BIoU below ``BIOU_REGRESSION_BUDGET`` and/or residual
    source text found), emits exactly ONE aggregated string via
    ``warnings_callback`` naming the doc id and affected page numbers — both
    signals combine into the SAME entry when both fire.

    Fail-soft: ANY exception (corrupt/unreadable output, metric error) is
    caught, logged, and the pass is skipped -- never raises, never alters the
    rendered output, never fabricates a warning.

    Returns ``None`` when skipped (no ``doc``/``warnings_callback``, or a
    fail-soft exception); returns a ``LayoutQAResult`` otherwise.
    """
    if log is None:
        log = lambda s: None  # noqa: E731

    if doc is None or not warnings_callback:
        return None

    rendered_doc = None
    try:
        import fitz  # lazy import (ADR-0015) -- no hard fitz dependency at module import time

        rendered_doc = fitz.open(output_path)

        by_page: Dict[int, list] = {}
        for elem in getattr(doc, "elements", None) or []:
            page_num = getattr(elem, "page_num", None)
            if page_num is None:
                continue
            by_page.setdefault(page_num, []).append(elem)

        biou_scores: List[float] = []
        biou_regressed_pages: set = set()
        residual_pages: set = set()

        for page_num, page_elements in sorted(by_page.items()):
            page_index = page_num - 1
            if page_index < 0 or page_index >= rendered_doc.page_count:
                log(
                    f"[layout-qa] '{doc_id}' page {page_num} skipped: "
                    "not present in rendered output"
                )
                continue

            source_bboxes = []
            elem_by_bbox_id = {}
            for elem in page_elements:
                bbox = getattr(elem, "bbox", None)
                if bbox is None:
                    continue
                source_bboxes.append(bbox)
                elem_by_bbox_id[id(bbox)] = elem

            if not source_bboxes:
                # Nothing measurable on this page -- no raise, no fabricated signal.
                continue

            page = rendered_doc[page_index]
            rendered_bboxes = _rendered_page_bboxes(page)

            if (
                len(source_bboxes) > LAYOUT_QA_MAX_BOXES_PER_PAGE
                or len(rendered_bboxes) > LAYOUT_QA_MAX_BOXES_PER_PAGE
            ):
                log(
                    f"[layout-qa] '{doc_id}' page {page_num} skipped: box count "
                    f"exceeds LAYOUT_QA_MAX_BOXES_PER_PAGE={LAYOUT_QA_MAX_BOXES_PER_PAGE}"
                )
                continue

            page_biou = compute_biou(source_bboxes, rendered_bboxes)
            biou_scores.append(page_biou)
            if page_biou < BIOU_REGRESSION_BUDGET:
                biou_regressed_pages.add(page_num)

            # Residual-source-text disambiguation (implementation-plan.md):
            # only flag a bbox whose OWN normalized source string still
            # appears inside its own rendered clip -- never warn from raw
            # check_residual_text output (that would flag every correctly
            # TRANSLATED box too).
            residual_records = check_residual_text(page, source_bboxes)
            for record in residual_records:
                elem = elem_by_bbox_id.get(id(record.get("bbox")))
                if elem is None:
                    continue
                source_str = _normalize(getattr(elem, "content", "") or "")
                if not source_str:
                    continue
                rendered_text = _normalize(record.get("text", ""))
                if source_str in rendered_text:
                    residual_pages.add(page_num)

        mean_biou = (sum(biou_scores) / len(biou_scores)) if biou_scores else 1.0
        biou_regressed = bool(biou_regressed_pages)
        warned = biou_regressed or bool(residual_pages)

        if warned:
            affected_pages = sorted(biou_regressed_pages | residual_pages)
            signals = []
            if biou_regressed:
                signals.append(_BIOU_SIGNAL_TEXT)
            if residual_pages:
                signals.append(_RESIDUAL_SIGNAL_TEXT)
            pages_str = ", ".join(str(p) for p in affected_pages)
            warnings_callback(
                LAYOUT_QA_WARNING_TEMPLATE.format(
                    doc_id=doc_id, pages=pages_str, signal=" and ".join(signals)
                )
            )

        return LayoutQAResult(
            mean_biou=mean_biou,
            biou_regressed=biou_regressed,
            residual_pages=sorted(residual_pages),
            warned=warned,
        )
    except Exception as exc:
        log(f"[layout-qa] layout-QA pass failed for '{doc_id}': {exc}")
        return None
    finally:
        if rendered_doc is not None:
            try:
                rendered_doc.close()
            except Exception:
                pass
