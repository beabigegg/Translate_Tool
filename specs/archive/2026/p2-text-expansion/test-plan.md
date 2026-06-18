---
change-id: p2-text-expansion
schema-version: 0.1.0
last-changed: 2026-06-18
risk: medium
tier: 2
---

# Test Plan: p2-text-expansion

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | unit | tests/test_text_region_renderer.py::TestFitCascade::test_ende_no_overflow | 0 |
| AC-1 | data-boundary | tests/test_golden_regression.py::TestGoldenPDFParseIRStable | 1 |
| AC-2 | unit | tests/test_text_region_renderer.py::TestFitCascade::test_enes_no_overflow | 0 |
| AC-3 | unit | tests/test_font_utils.py::TestMetricFallbackChain::test_missing_glyph_selects_noto | 0 |
| AC-3 | unit | tests/test_font_utils.py::TestMetricFallbackChain::test_fallback_no_tofu_metric_drift | 0 |
| AC-4 | unit | tests/test_text_region_renderer.py::TestFitCascade::test_cascade_order_font_size_first | 0 |
| AC-4 | unit | tests/test_text_region_renderer.py::TestFitCascade::test_cascade_order_line_spacing_after_font_min | 0 |
| AC-4 | unit | tests/test_text_region_renderer.py::TestFitCascade::test_cascade_order_letter_spacing_after_line_floor | 0 |
| AC-4 | unit | tests/test_text_region_renderer.py::TestFitCascade::test_cascade_order_overflow_before_truncation | 0 |
| AC-4 | unit | tests/test_text_region_renderer.py::TestFitCascade::test_cascade_truncation_last_resort_only | 0 |
| AC-4 | contract | tests/test_text_region_renderer.py::TestFitCascadeContract::test_cascade_decision_fields_present | 0 |
| AC-5 | unit | tests/test_text_region_renderer.py::TestTruncationMarker::test_truncation_sets_render_truncated_true | 0 |
| AC-5 | unit | tests/test_text_region_renderer.py::TestTruncationMarker::test_no_truncation_render_truncated_false | 0 |
| AC-5 | contract | tests/test_text_region_renderer.py::TestTruncationMarker::test_render_truncated_field_in_to_dict | 0 |
| AC-6 | integration | tests/test_renderer_convergence.py::TestLayoutEquivalence::test_both_paths_call_reflow_document | 1 |
| AC-6 | integration | tests/test_renderer_convergence.py::TestLayoutEquivalence::test_reportlab_path_calls_reflow_document | 1 |
| AC-6 | unit | tests/test_text_region_renderer.py::TestSinglePathEnforcement::test_no_cascade_logic_in_legacy_paths | 0 |
| AC-7 | unit | tests/test_font_utils.py::TestMetricFallbackChain::test_fallback_reuses_lru_cache | 0 |
| AC-7 | unit | tests/test_font_utils.py::TestMetricFallbackChain::test_fallback_no_redundant_font_io | 0 |
| AC-8 | unit | tests/test_font_utils.py::TestExpansionFactorTable::test_en_de_factor | 0 |
| AC-8 | unit | tests/test_font_utils.py::TestExpansionFactorTable::test_en_es_factor | 0 |
| AC-8 | unit | tests/test_font_utils.py::TestExpansionFactorTable::test_en_fr_factor | 0 |
| AC-8 | unit | tests/test_font_utils.py::TestExpansionFactorTable::test_unknown_pair_default_factor | 0 |
| AC-8 | contract | tests/test_font_utils.py::TestExpansionFactorTable::test_default_factor_is_documented | 0 |

## Test Families Required

| family | tier | notes |
|---|---|---|
| unit | 0 | cascade step boundaries, truncation marker, expansion table, metric fallback — extends test_text_region_renderer.py and test_font_utils.py |
| contract | 0 | CascadeDecision struct fields; render_truncated present in to_dict(); expansion-factor default matches business-rules.md |
| integration | 1 | per-backend mock.patch wiring in test_renderer_convergence.py; extends existing TestLayoutEquivalence |
| data-boundary | 1 | render_truncated absent from existing golden IR snapshots must appear after implementation; test_golden_regression.py |
| visual | manual | en→de/es benchmark render comparison (0 overflow, 0 tofu); visual-reviewer evidence only, not in automated gate |

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| tests/test_font_utils.py::TestFitTextToBbox | extend | fit_text_to_bbox now returns a CascadeDecision; add assertions for new fields |
| tests/test_renderer_convergence.py::TestLayoutEquivalence | extend | add cascade-wiring mock assertion (AC-6) without breaking existing placement tests |

## Out of Scope

- CJK vertical writing (P3-5)
- RTL mirroring (P3-4)
- Table border protection (p2-table-border-protection)
- Frontend, API, CSS, and env changes
- E2E, monkey, stress, and soak tests
- DOCX/PPTX golden fixture expansion (no new fixtures required by this change)

## Notes

- AC-4/AC-5 tests must FAIL before `fit_cascade()` and `render_truncated` field exist (TDD gate).
- AC-6 legacy-path enforcement: `test_no_cascade_logic_in_legacy_paths` uses import inspection to assert cascade helper is not imported in `coordinate_renderer.py`, `inline_renderer.py`, or `pdf_generator.py`.
- AC-7 cache test uses `mock.patch` on `_load_font_buffer` asserting call count ≤ 1 per face across repeated fallback calls.
- Visual tier is manual; it does not block the automated gate. Visual-reviewer writes `visual-review-report.md` as evidence.
