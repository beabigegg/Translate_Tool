---
change-id: p3-llm-judge
schema-version: 0.1.0
last-changed: 2026-06-22
risk: medium
tier: 2
---

# Test Plan: p3-llm-judge

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 (judge records score/feedback/attempts) | unit | tests/test_quality_judge.py::test_judge_records_result_on_job_record | 0 |
| AC-1 | unit | tests/test_quality_judge.py::test_judge_score_high_terminates_loop | 0 |
| AC-2 (中/低 re-translates, 高 stops) | unit | tests/test_quality_judge.py::test_judge_score_mid_triggers_retranslation | 0 |
| AC-2 | unit | tests/test_quality_judge.py::test_judge_score_high_no_retranslation | 0 |
| AC-2 | unit | tests/test_quality_judge.py::test_feedback_fed_back_to_translation_model | 0 |
| AC-3 (cap at 3, final state recorded) | unit | tests/test_quality_judge.py::test_judge_iteration_cap_enforced | 0 |
| AC-3 | unit | tests/test_quality_judge.py::test_attempts_field_equals_iteration_count | 0 |
| AC-4 (flag=false or Gemma unavailable → job completes) | unit | tests/test_quality_judge.py::test_judge_disabled_flag_skips_judge | 0 |
| AC-4 | unit | tests/test_quality_judge.py::test_judge_exception_degrades_gracefully | 0 |
| AC-4 | unit | tests/test_quality_judge.py::test_judge_parse_failure_degrades_gracefully | 0 |
| AC-5 (GET /judge schema, POST /apply schema) | contract | tests/test_judge_api.py::test_get_judge_available_response_shape | 1 |
| AC-5 | contract | tests/test_judge_api.py::test_get_judge_disabled_response_shape | 1 |
| AC-5 | contract | tests/test_judge_api.py::test_get_judge_unavailable_response_shape | 1 |
| AC-5 | contract | tests/test_judge_api.py::test_get_judge_unknown_job_returns_404 | 1 |
| AC-5 | contract | tests/test_judge_api.py::test_post_apply_202_when_preconditions_pass | 1 |
| AC-5 | contract | tests/test_judge_api.py::test_post_apply_409_job_not_completed | 1 |
| AC-5 | contract | tests/test_judge_api.py::test_post_apply_409_judge_not_available | 1 |
| AC-5 | contract | tests/test_judge_api.py::test_post_apply_409_retranslated_blocks_empty | 1 |
| AC-5 | contract | tests/test_judge_api.py::test_post_apply_409_source_evicted | 1 |
| AC-5 | contract | tests/test_judge_api.py::test_post_apply_idempotent_while_applying | 1 |
| AC-5 | data-boundary | tests/test_job_record_judge.py::test_job_status_includes_judge_score_summary | 1 |
| AC-6 (frontend judge panel) | out of scope | — | — |
| AC-7 (wired into all 4 processors) | integration | tests/test_orchestrator_judge.py::test_judge_hook_fires_docx | 1 |
| AC-7 | integration | tests/test_orchestrator_judge.py::test_judge_hook_fires_pptx | 1 |
| AC-7 | integration | tests/test_orchestrator_judge.py::test_judge_hook_fires_xlsx | 1 |
| AC-7 | integration | tests/test_orchestrator_judge.py::test_judge_hook_fires_pdf | 1 |
| AC-8 (coexists with QE + CRITIQUE_LOOP) | integration | tests/test_orchestrator_judge.py::test_judge_does_not_alter_qe_scoring | 1 |
| AC-8 | integration | tests/test_orchestrator_judge.py::test_critique_loop_unaffected_when_judge_disabled | 1 |
| AC-9 (frontend confirm dialog) | out of scope | — | — |
| AC-10 (apply re-renders, overwrites zip) | integration | tests/test_judge_apply.py::test_apply_rerenders_and_swaps_output_zip | 1 |
| AC-10 | integration | tests/test_judge_apply.py::test_apply_fail_soft_preserves_original_zip | 1 |
| AC-10 | integration | tests/test_judge_apply.py::test_apply_block_id_mismatch_fails_soft | 1 |
| AC-10 | data-boundary | tests/test_job_record_judge.py::test_judge_apply_status_transitions | 1 |

## Additional Rule Coverage

| rule | test name | file |
|---|---|---|
| BR-72 score parse (JSON-first) | test_score_json_parse_valid | tests/test_quality_judge.py |
| BR-72 score parse (raw scan fallback) | test_score_raw_scan_fallback | tests/test_quality_judge.py |
| BR-72 no token → unavailable | test_score_no_token_unavailable | tests/test_quality_judge.py |
| BR-72 synonyms not accepted | test_score_synonym_not_accepted | tests/test_quality_judge.py |
| BR-77 apply uses stored map, no LLM call | test_apply_uses_stored_block_map_not_llm | tests/test_judge_apply.py |
| D4 judge routes via OllamaClient, not model_router | test_judge_client_is_ollama_not_model_router | tests/test_quality_judge.py |
| Backward-compat: JobRecord without judge field | test_job_record_without_judge_field_valid | tests/test_job_record_judge.py |

## Test Families Required

| family | tier | notes |
|---|---|---|
| unit | 0 | Score parsing, iteration cap, feedback reflection, graceful degradation, disabled-flag branch; mock boundary is `OllamaClient.generate`, not the full Ollama process |
| contract | 1 | GET /judge and POST /judge/apply response shapes and status codes; mirror FastAPI TestClient pattern from `test_quality_evaluation.py` |
| integration | 1 | Judge hook fires in `job_manager._run_job` for all 4 processor paths (anti-orphan wiring check); QE/CRITIQUE_LOOP coexistence; apply temp-then-swap |
| data-boundary | 1 | JobRecord additive field backward-compat; `judge_apply_status` enum values; `JobStatus.judge_score` summary null when no judge run |

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| tests/test_quality_evaluation.py | read-only / no change | coexistence verified by AC-8 integration tests; no behavior altered |

## Out of Scope

- AC-6 and AC-9 (frontend panel + confirm dialog) — visual reviewer handles; no backend test surface.
- Tasks 3.3 (E2E), 3.4 (monkey), 3.5 (stress/soak) — marked not-applicable in change-classification.md.
- Per-block/cell-level judging granularity — design decision D3 explicit non-goal.
- VRAM / model-load contention — open risk tracked in design.md; not testable at unit tier.

## Notes

- AC-7 wiring: `test_orchestrator_judge.py` must assert the judge callable is invoked via `_run_job`, not just that a unit mock ran. Mirror the anti-tautology pattern from `test_renderer_convergence.py`.
- AC-3 selection: assert `JudgeResult.attempts == JUDGE_MAX_ITERATIONS` when cap fires; asserting loop terminated without checking count is insufficient (CLAUDE.md tautology anti-pattern).
- BR-75 reflection: assert the re-translation LLM call received the judge feedback string in its prompt argument.
- D4 isolation: assert `model_router.resolve_route_groups` is NOT called during judge execution.
