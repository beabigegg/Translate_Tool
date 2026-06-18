---
change-id: p2-layout-detection
schema-version: 0.1.0
last-changed: 2026-06-18
risk: medium
tier: 2
---

# Test Plan: p2-layout-detection

## Acceptance Criteria → Test Mapping
| criterion id | description | test family | test file path | tier |
|---|---|---|---|---|
| AC-1 | detector returns typed region boxes | unit | tests/test_layout_detector.py | 0 |
| AC-1 | known heron label → ElementType mapping | unit | tests/test_layout_detector.py | 0 |
| AC-1 | unknown heron label → defaults to `text` | unit | tests/test_layout_detector.py | 0 |
| AC-2 | ElementType written into IR elements | unit | tests/test_layout_detector.py | 0 |
| AC-2 | reading_order written into IR elements | unit | tests/test_layout_detector.py | 0 |
| AC-2 | no parallel data structure created | unit | tests/test_layout_detector.py | 0 |
| AC-3 | y0 heuristic replaced by detector on native-PDF path | integration | tests/test_pdf_parser.py | 1 |
| AC-4 | no network imports in layout_detector module | unit | tests/test_layout_detector.py | 0 |
| AC-4 | page image not retained after detect call | unit | tests/test_layout_detector.py | 0 |
| AC-5 | LAYOUT_DETECTOR_MODEL_PATH declared in env contract | contract | tests/test_env_contract.py | 0 |
| AC-5 | weight resolution: env var wins over HF cache | unit | tests/test_layout_detector.py | 0 |
| AC-5 | weight resolution: unset env var falls back to HF | unit | tests/test_layout_detector.py | 0 |
| AC-6 | old vs new reading-order dual-run regression | data-boundary | tests/test_golden_regression.py | 1 |
| AC-6 | multi-column reading-order accuracy >95% | data-boundary | tests/test_golden_regression.py | 1 |
| AC-7 | missing model → fail-soft, WARNING, job continues | resilience | tests/test_layout_detector.py | 1 |
| AC-7 | ONNX load error → fail-soft per page, WARNING | resilience | tests/test_layout_detector.py | 1 |
| AC-7 | OOM during inference → fail-soft, no crash | resilience | tests/test_layout_detector.py | 1 |
| AC-7 | unrasterisable page → fail-soft, WARNING | resilience | tests/test_layout_detector.py | 1 |
| AC-8 | ultralytics not imported anywhere | contract | tests/test_layout_detector.py | 0 |

## Test Files

### new: tests/test_layout_detector.py
- test_detect_regions_returns_typed_boxes
- test_label_mapping_all_known_labels
- test_unknown_label_defaults_to_text
- test_ir_element_type_written_from_region
- test_ir_reading_order_written_from_detector
- test_no_extra_fields_outside_ir
- test_no_network_imports_in_module
- test_page_image_not_retained_after_detect
- test_weight_resolution_env_var_takes_priority
- test_weight_resolution_fallback_to_hf
- test_missing_model_falls_back_to_heuristic
- test_onnx_load_error_falls_back_to_heuristic
- test_oom_inference_falls_back_to_heuristic
- test_unrasterisable_page_falls_back_to_heuristic
- test_ultralytics_not_imported
- test_detector_disabled_by_env_flag_uses_heuristic

### modified: tests/test_pdf_parser.py
- test_detector_order_replaces_y0_heuristic
- test_parse_invokes_layout_detector_on_native_pdf
- test_detector_failure_parse_still_returns_document

### modified: tests/test_golden_regression.py
- test_dual_run_layout_detector_vs_heuristic
- test_multi_column_reading_order_accuracy

### modified: tests/test_env_contract.py
- test_layout_detector_model_path_declared

## Test Families Required
| family | tier | notes |
|---|---|---|
| unit | 0 | mock ONNX session; covers label mapping, IR write, privacy boundary, weight resolution |
| contract | 0 | static checks: env-contract.md declares var; requirements.txt has no ultralytics |
| integration | 1 | pdf_parser → layout_detector → IR with real PyMuPDF, mocked ONNX session |
| data-boundary | 1 | multi-column golden fixtures; dual-run old-vs-new diff |
| resilience | 1 | inject missing model / ONNX error / OOM via mock; verify fail-soft + WARNING |

## Test Update Contract
| existing test | action | reason |
|---|---|---|
| tests/test_pdf_parser.py (reading-order assertions) | update | AC-3 replaces y0 heuristic; expected order changes on native-PDF path |
| tests/test_golden_regression.py | extend | add dual-run and multi-column accuracy assertions for AC-6 |

## Out of Scope
- Scanned/image-only PDF path (P3-1, separate change)
- GPU provider correctness (opt-in, operator responsibility)
- Live HuggingFace download network call (Tier 3 nightly only)
- ONNX model mAP benchmarking (validation artefact, not CI gate)
- Docker offline-bundle build verification (ci-cd-gatekeeper scope)

## Execution Ladder
| phase | command | required |
|---|---|---|
| collect | tests/test_layout_detector.py | yes |
| collect | tests/test_pdf_parser.py | yes |
| collect | tests/test_golden_regression.py | yes |
| collect | tests/test_env_contract.py | yes |
| targeted | pytest tests/test_layout_detector.py tests/test_env_contract.py -x | yes |
| full-tier-1 | pytest tests/test_layout_detector.py tests/test_pdf_parser.py tests/test_golden_regression.py tests/test_env_contract.py | yes |

## Notes
All ONNX session calls must be mocked at the `onnxruntime.InferenceSession` boundary — not at internal class boundaries — so the label-mapping and IR-write logic is exercised against real IR objects. Golden fixtures for AC-6 must include at least one two-column academic PDF sample.
