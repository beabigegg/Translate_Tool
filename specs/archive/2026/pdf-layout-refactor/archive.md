---
artifact: archive
change-id: pdf-layout-refactor
tier: 1
merged-pr: "https://github.com/beabigegg/Translate_Tool/pull/8"
archived-date: 2026-06-27
---

# Archive: pdf-layout-refactor

> **Cold Data Warning**: This archive is historical evidence. Current requirements live in `contracts/` and active project guidance.

## Change Summary

Wave 2 Track G overhauled the PDF layout renderer across 7 sequential items (3.1–3.7) from the improvement-plan. The change moved from PyMuPDF `search_for`-based whitening to IR bbox-exact whitening, introduced a BabelDOC-style paragraph aggregation IR, replaced the linear font-shrink cascade with an 8pt-floor binary search, added `is_underline` to `StyleInfo`, introduced a `LayoutReader` column-aware reading-order model, upgraded render DPI from 72 to 150 (with a coordinate back-mapping fix that the DPI change itself exposed), and added FORMULA element path-independent pass-through plus a lazy-import OCR seam (`ocr_backend.py`) for future scanned-PDF support.

## Final Behavior

- **Whitening**: `fitz_renderer._generate_overlay` uses `add_redact_annot` on `element.bbox` (and per-line bboxes from `metadata["lines"]`) — no `search_for` calls; residual source-text count = 0.
- **Paragraph IR**: `pdf_parser._extract_page_elements` groups all fitz block lines into one `TranslatableElement`; individual line bboxes in `metadata["lines"]`.
- **Scale-fit**: `text_region_renderer.fit_text_cascade` binary-searches between `MIN_READABLE_FONT_PT=8` and original size; `render_truncated=True` only at 8pt floor.
- **StyleInfo**: `is_underline: bool = False` added with backward-compat `from_dict`/`to_dict`; IR correctly stores all 7 style fields.
- **Reading order**: `LayoutReader.sort_elements()` in `layout_detector.py` uses x-gap column detection; replaces single-threshold heuristic.
- **DPI**: `PDF_RENDER_DPI=150` default; `detect()` accepts `page_width_pt`/`page_height_pt` for correct point-space coordinate mapping at any DPI.
- **FORMULA**: `pdf_processor._apply_formula_passthrough` sets `should_translate=False` on all paths (detector and heuristic).
- **OCR seam**: `ocr_backend.py::run_ocr()` lazy-imports surya/paddleocr; `OCR_ENABLED=False` default — CI never needs OCR installed.

## Final Contracts Updated

| Contract | Version | Change |
|---|---|---|
| `contracts/data/data-shape-contract.md` | 0.14.0 → 0.15.0 | `is_underline` in StyleInfo; FORMULA active pass-through; paragraph IR; `ocr_backend.py` known consumer |
| `contracts/business/business-rules.md` | 0.20.0 → 0.21.0 | BR-84..88 added; BR-36 amended (8pt binary-search floor); Tables J/L/W updated |
| `contracts/env/env-contract.md` | 0.10.0 → 0.11.0 | `PDF_RENDER_DPI=150`, `OCR_ENABLED=false` rows added |
| `contracts/ci/ci-gate-contract.md` | 0.4.3 → 0.5.0 | `residual-text` + `ocr-absent` required; `biou`/`truncation`/`reading-order` informational |

## Final Tests Added / Updated

- `tests/test_pdf_layout_refactor.py` — 29 new tests (AC-1..AC-8): `TestBboxWhitening`, `TestParagraphAggregation`, `TestIterativeScaleFit`, `TestSpanStyleFidelity`, `TestReadingOrderModel`, `TestDpiUpgrade`, `TestFormulaAndOcr`
- `tests/test_layout_detector.py::TestDpiCoordinateBackMapping` — DPI coordinate back-mapping behavioral test at 3× DPI
- `tests/fixtures/test_multiline.pdf` — new fixture for paragraph aggregation tests
- Full suite: 991 passed, 4 skipped (pre-existing fixture-availability), 0 failures

## Final CI/CD Gates

| Gate | Required | Result |
|---|---|---|
| residual-text | yes | pass |
| ocr-absent-gate | yes | pass |
| full-regression | yes | pass (991/0/4) |
| biou-layout-fidelity | informational | deferred (no golden fixtures yet) |
| truncation-rate | informational | deferred |
| reading-order-edit-distance | informational | deferred |

## Production Reality Findings

**DPI coordinate mismatch (found and fixed in-change)**: Upgrading `PDF_RENDER_DPI` from 72 to 150 exposed a latent bug where `LayoutDetector.detect()` used pixmap pixel dimensions to denormalize ONNX region boxes — correct at 72 DPI (1px≈1pt) but wrong at 150 DPI (2.08× offset). Fix: `detect()` now accepts `page_width_pt`/`page_height_pt`; `pdf_parser.py` passes `page.rect.width/height`. New behavioral test `TestDpiCoordinateBackMapping` verifies correctness at 3× DPI.

**AC-4 per-span renderer gap**: `_insert_text_in_rect` does not consume `element.style` (color/bold/italic). IR stores all fields correctly; pre-change output was also unstyled — no regression. Tracked as follow-on.

**Style fidelity**: IR-level round-trip complete; renderer-level style application deferred to a follow-on change.

## Lessons Promoted to Standards

None promoted to CLAUDE.md. All durable rules are captured in the four updated contracts:
- BR-84..88 in `contracts/business/business-rules.md` (whitening, scale-fit floor, formula pass-through, OCR routing, readable-font threshold)
- `PDF_RENDER_DPI` and `OCR_ENABLED` in `contracts/env/env-contract.md`
- `is_underline`, paragraph IR, `ocr_backend.py` consumer in `contracts/data/data-shape-contract.md`
- `residual-text` + `ocr-absent` required gates in `contracts/ci/ci-gate-contract.md`

DPI coordinate fix (pass pt dims to `detect()`) is in code + `TestDpiCoordinateBackMapping`. No new agent-workflow patterns not covered by existing CLAUDE.md entries.

## Follow-up Work

1. Wire `element.style` consumption into `_insert_text_in_rect` (per-span color/bold/italic application) — follow-on change.
2. Commit golden PDF fixtures with `.ir.json` snapshots to promote `biou`/`truncation`/`reading-order` informational gates to required.
3. Implement OCR path when `OCR_ENABLED=True` (surya/paddleocr integration in `ocr_backend.py`).
