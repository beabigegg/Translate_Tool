---
change-id: p2-renderer-convergence
schema-version: 0.1.0
last-changed: 2026-06-18
risk: medium
tier: 2
---

# Test Plan: p2-renderer-convergence

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | unit | `tests/test_renderer_convergence.py::TestIRBboxReflow` | 0 |
| AC-2 | unit | `tests/test_renderer_convergence.py::TestFitzPrimary` | 0 |
| AC-3 | resilience | `tests/test_renderer_convergence.py::TestFitzFallback` | 0 |
| AC-3 | resilience | `tests/test_pdf_generator.py::TestFallbackPath` | 0 |
| AC-4 | integration | `tests/test_renderer_convergence.py::TestLayoutEquivalence` | 1 |
| AC-5 | contract | `tests/test_ir_pipeline_decoupling.py::TestReadingOrderPreservedBothPaths` | 0 |
| AC-5 | contract | `tests/test_ir_pipeline_decoupling.py::TestElementTypingPreservedBothPaths` | 0 |
| AC-6 | data-boundary | `tests/test_ir_pipeline_decoupling.py::TestMalformedIRBothPaths` | 0 |
| AC-6 | data-boundary | `tests/test_renderer_convergence.py::TestMalformedIRDataBoundary` | 0 |
| AC-7 | regression | `tests/test_golden_regression.py` | 1 |
| AC-7 | regression | `tests/test_renderer_convergence.py::TestEquivalenceGolden` | 1 |

## Test Families Required

| family | tier | notes |
|---|---|---|
| unit | 0 | Shared IR-bbox reflow component in isolation; fitz-primary selection logic |
| resilience | 0 | fitz raises → WARNING logged → ReportLab output produced; no job abort |
| contract | 0 | reading_order and ElementType preserved identically on both paths for same IR |
| data-boundary | 0 | null bbox / null reading_order / unknown ElementType / null translated_content: deterministic and identical on both paths |
| integration | 1 | pdf_processor → fitz primary path; forced-fallback path via ReportLab; both from same IR |
| regression | 1 | Existing golden fixtures unchanged; new fitz vs ReportLab equivalence snapshots added |

## New Test File: tests/test_renderer_convergence.py

### TestIRBboxReflow (unit, tier 0)
- `test_shared_reflow_returns_placement_for_valid_bbox` — reflow(element with valid bbox) returns non-None placement
- `test_shared_reflow_skips_null_bbox` — reflow(element with bbox=None) returns None/sentinel, no raise
- `test_shared_reflow_deterministic` — same IR element in → same placement out on repeated calls

### TestFitzPrimary (unit, tier 0)
- `test_fitz_renderer_selected_by_default` — pdf_processor selects fitz path when fitz is importable
- `test_fitz_renderer_produces_valid_pdf` — fitz path renders a TranslatableDocument to a non-empty PDF file

### TestFitzFallback (resilience, tier 0)
- `test_fallback_to_reportlab_on_fitz_exception` — fitz path raises; ReportLab path invoked; PDF produced
- `test_fallback_emits_warning_log` — WARNING log contains fallback message on fitz failure
- `test_no_job_abort_on_fitz_failure` — fitz exception does not propagate; output file still created

### TestLayoutEquivalence (integration, tier 1)
- `test_element_count_equivalent_fitz_vs_reportlab` — both paths render same element count for same IR
- `test_bbox_placement_within_tolerance_fitz_vs_reportlab` — placement coords within tolerance defined in design.md

### TestMalformedIRDataBoundary (data-boundary, tier 0)
- `test_null_bbox_handled_identically_both_paths` — both paths skip element, no raise
- `test_null_reading_order_handled_identically_both_paths` — both paths fall back deterministically
- `test_unknown_element_type_handled_identically_both_paths` — both paths skip or use TEXT fallback identically
- `test_null_translated_content_handled_identically_both_paths` — both paths skip or pass through source content identically

### TestEquivalenceGolden (regression, tier 1)
- `test_golden_fitz_snapshot_stable` — fitz render of golden PDF fixture matches committed layout snapshot
- `test_golden_reportlab_snapshot_stable` — ReportLab render of golden PDF fixture matches committed layout snapshot

## Additions to Existing Test Files

### tests/test_pdf_generator.py — class TestFallbackPath (new, resilience, tier 0)
- `test_fallback_path_invoked_when_fitz_import_fails` — mock fitz import failure; ReportLab path produces output
- `test_fallback_path_warning_logged` — mock fitz import failure; WARNING present in log messages

### tests/test_ir_pipeline_decoupling.py — class TestReadingOrderPreservedBothPaths (new, contract, tier 0)
- `test_reading_order_preserved_fitz_path` — render via fitz; element order matches IR reading_order sequence
- `test_reading_order_preserved_reportlab_path` — render via ReportLab; element order matches IR reading_order sequence

### tests/test_ir_pipeline_decoupling.py — class TestElementTypingPreservedBothPaths (new, contract, tier 0)
- `test_element_type_routing_fitz` — TABLE/FIGURE/FORMULA elements routed correctly (skipped or typed) in fitz path
- `test_element_type_routing_reportlab` — TABLE/FIGURE/FORMULA elements routed identically in ReportLab path

### tests/test_ir_pipeline_decoupling.py — class TestMalformedIRBothPaths (new, data-boundary, tier 0)
- `test_malformed_ir_null_bbox_both_paths` — both paths: no raise, identical skip behavior
- `test_malformed_ir_null_reading_order_both_paths` — both paths handle missing reading_order identically
- `test_malformed_ir_unknown_element_type_both_paths` — both paths handle unrecognized ElementType identically

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| tests/test_pdf_generator.py (all classes) | extend only; no deletion | existing fitz-path tests remain valid; new fallback class added alongside |

## Out of Scope
- Non-PDF renderers (DOCX InlineRenderer, PPTX) — not affected by this convergence
- Font cache correctness — covered by existing `TestFontBufferCache`
- Parser correctness — IR is consumed, not produced, by this change
- Stress / soak / monkey — no queue or long-running surface (see change-classification.md)
- Byte-identical PDF output equivalence — tolerance-based per design.md only

## Notes
- BR-34 and BR-35 are the primary contract anchors for AC-3 and AC-5/AC-6 respectively.
- `TestIRBboxReflow` must fail before implementation (shared reflow component does not yet exist).
- Layout tolerance threshold must be defined in `design.md` before `TestLayoutEquivalence` has a numeric pass criterion.
- Golden equivalence snapshots (`*.layout.json`) are separate from existing `*.ir.json` IR snapshots.
