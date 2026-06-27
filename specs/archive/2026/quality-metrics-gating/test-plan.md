---
change-id: quality-metrics-gating
schema-version: 0.1.0
last-changed: 2026-06-27
risk: medium
tier: 2
---

# Test Plan: quality-metrics-gating

## Acceptance Criteria → Test Mapping
| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | unit | tests/test_quality_evaluation.py::test_per_segment_score_blocks_called_with_src_hyp_pairs | 0 |
| AC-2 | unit | tests/test_quality_evaluation.py::test_below_threshold_triggers_retranslation | 0 |
| AC-2 | unit | tests/test_quality_evaluation.py::test_threshold_env_var_parsed_as_float | 0 |
| AC-3 | contract | tests/test_env_contract.py::TestQeDefault::test_qe_enabled_default_true_in_contract | 1 |
| AC-3 | unit | tests/test_quality_evaluation.py::test_qe_enabled_config_default_is_true | 0 |
| AC-4 | contract | tests/test_env_contract.py::TestQeDefault::test_qe_rescore_threshold_declared_in_contract | 1 |
| AC-4 | unit | tests/test_quality_evaluation.py::test_rescore_threshold_out_of_range_rejected | 0 |
| AC-5 | unit | tests/test_quality_judge.py::test_per_block_judge_calls_evaluate_once_per_block_with_correct_pair_args | 0 |
| AC-5 | data-boundary | tests/test_quality_judge.py::test_per_block_judge_score_array_length_equals_block_count | 1 |
| AC-6 | unit | tests/test_quality_judge.py::test_judge_layout_receives_pil_image_object_not_path | 0 |
| AC-6 | unit | tests/test_quality_judge.py::test_judge_layout_returns_int_score_between_1_and_5 | 0 |
| AC-7 | unit | tests/test_critique_gate.py::test_gate_adopts_revised_when_revised_score_strictly_higher | 0 |
| AC-7 | unit | tests/test_critique_gate.py::test_gate_keeps_original_when_revised_score_lower | 0 |
| AC-7 | unit | tests/test_critique_gate.py::test_gate_keeps_original_on_exact_tie | 0 |
| AC-8 | resilience | tests/test_critique_gate.py::test_comet_import_error_falls_back_to_heuristic | 1 |
| AC-8 | resilience | tests/test_critique_gate.py::test_heuristic_penalises_empty_output_and_failure_markers | 1 |
| AC-8 | resilience | tests/test_critique_gate.py::test_pipeline_completes_with_no_exception_when_qe_unavailable | 1 |
| AC-9 | integration | tests/test_translate_document_parity.py::test_translate_document_calls_term_substitution | 1 |
| AC-10 | integration | tests/test_translate_document_parity.py::test_translate_document_calls_critique_loop | 1 |
| AC-11 | integration | tests/test_translate_document_parity.py::test_translate_document_passes_overlap_tokens_as_context | 1 |

## Test Families Required
| family | tier | notes |
|---|---|---|
| unit | 0 | per-segment QE call shape; rescore threshold parsing; per-block judge call args; critique gate score comparison incl. tie; judge_layout PIL input/output |
| contract | 1 | env-contract.md: QE_ENABLED default true; QE_RESCORE_THRESHOLD declared with type + default + validation |
| integration | 1 | translate_document() parity hooks; critique gate end-to-end keeps better revision, discards worse |
| data-boundary | 1 | per-block judge score array len == input block count; layout score 1-5 int bound |
| resilience | 1 | QE ImportError → heuristic; heuristic scoring rule; pipeline always completes |

## Test Update Contract
| existing test | action | reason |
|---|---|---|
| tests/test_quality_evaluation.py | extend | add AC-1 call-shape, AC-2 rescore routing, AC-3 default, AC-4 threshold tests |
| tests/test_quality_judge.py | extend | add AC-5 per-block call_args_list, AC-6 judge_layout PIL tests |
| tests/test_env_contract.py | extend | add TestQeDefault class for AC-3 default-true and AC-4 threshold declaration |

## Out of Scope
- Frontend quality display (no UI surface)
- Stress/soak latency and VRAM benchmarks (stress-soak-report.md, not unit gate)
- E2E full-pipeline job submission with QE on (optional nightly; no bounded target)
- PDF rasterisation internals (Track B harness; only judge_layout seam tested here)
- CER-001 API response schema extension (pending contract-reviewer confirmation)

## Notes
- Tautology guard AC-1: mock `app.backend.services.quality_evaluator.score_blocks`; assert `call_args` is list of `(src, translated_content)` tuples — not just call count.
- Tautology guard AC-5: use `call_args_list` on `QualityJudge.evaluate`; assert each call receives `(src[i], tgt[i])` individually — not a joined whole-doc string.
- Tautology guard AC-6: assert `isinstance(mock.call_args[0][0], PIL.Image.Image)` — a file-path string must fail the assertion.
- Tautology guard AC-7: `score_blocks` mock returns two distinct floats; assert **adopted text identity**, not just that translation ran.
- Tautology guard AC-9/10/11: patch `app.backend.services.translation_service.translate_texts` (consumer-module binding per CLAUDE.md); assert it is reached with expected args — inspecting translate_document() output alone is the wrong-entry-point trap.
