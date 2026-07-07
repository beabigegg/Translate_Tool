---
change-id: translation-progress-detail-ui
schema-version: 0.1.0
last-changed: 2026-07-07
risk: medium
tier: 2
---

# Test Plan: translation-progress-detail-ui

> Implementation is DEFERRED (change-request.md Constraints). Tests below are
> written now so they exist as failing/pending specs before backend-engineer /
> frontend-engineer are commissioned in a later session.

## Acceptance Criteria → Test Mapping
| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | unit | tests/test_jobstatus_stage_detail.py::TestJobStatusAdditiveFields::test_new_fields_present_when_populated | 0 |
| AC-1 | unit | tests/test_jobstatus_stage_detail.py::TestJobStatusAdditiveFields::test_current_stage_enum_values_translate_critique_qe_adopt | 0 |
| AC-1 | integration | tests/test_translation_service_stage_snapshot.py::test_status_callback_emits_structured_snapshot_at_each_stage_transition | 1 |
| AC-2 | contract | tests/test_jobstatus_stage_detail.py::TestJobStatusAdditiveFields::test_existing_fields_unchanged_when_new_fields_absent | 1 |
| AC-2 | contract | contracts/api/openapi.yml (`cdd-kit openapi export --check`) | 1 |
| AC-3 | unit | app/frontend/src/components/domain/TranslationProgress.test.jsx::test_renders_stage_detail_panel_with_current_segment_content | 0 |
| AC-3 | unit | app/frontend/src/components/domain/TranslationProgress.test.jsx::test_stage_badge_label_matches_current_stage | 0 |
| AC-4 | unit | app/frontend/src/components/domain/TranslationProgress.test.jsx::test_shows_in_progress_indicator_when_segments_done_equals_total_but_stage_is_critique | 0 |
| AC-5 | unit | tests/test_eta_multi_phase_heuristic.py::test_translate_phase_only_rate_before_critique_starts | 0 |
| AC-5 | unit | tests/test_eta_multi_phase_heuristic.py::test_blended_two_phase_estimate_once_critique_rate_observed | 0 |
| AC-5 | unit | tests/test_eta_multi_phase_heuristic.py::test_critique_phase_estimated_via_max_iterations_factor_before_observed | 0 |
| AC-5 | unit | tests/test_eta_multi_phase_heuristic.py::test_eta_omits_critique_phase_when_critique_and_qe_disabled | 0 |
| AC-6 | unit | tests/test_job_manager_current_segment.py::test_snapshot_capture_is_reference_assignment_negligible_overhead | 0 |
| AC-7 | data-boundary | tests/test_jobstatus_stage_detail.py::TestJobStatusAdditiveFields::test_new_fields_null_when_job_just_started | 0 |
| AC-7 | data-boundary | tests/test_jobstatus_stage_detail.py::TestJobStatusAdditiveFields::test_new_fields_null_when_critique_and_qe_disabled | 0 |
| AC-7 | resilience | app/frontend/src/components/domain/TranslationProgress.test.jsx::test_renders_without_error_when_new_fields_absent_or_partial_mid_transition | 0 |
| AC-8 | unit | tests/test_job_manager_current_segment.py::test_current_segment_snapshot_overwritten_not_appended_across_calls | 0 |
| AC-9 | unit | tests/test_jobstatus_stage_detail.py::TestJobStatusAdditiveFields::test_current_stage_enum_includes_judge | 0 |
| AC-9 | unit | tests/test_jobstatus_stage_detail.py::TestJobStatusAdditiveFields::test_judge_fields_shape_when_judge_stage_active | 0 |
| AC-9 | data-boundary | tests/test_jobstatus_stage_detail.py::TestJobStatusAdditiveFields::test_judge_fields_null_outside_judge_stage | 0 |
| AC-9 | integration | tests/test_job_manager_current_segment.py::test_judge_snapshot_written_onto_jobrecord_at_scoring_and_retranslating_substeps | 1 |
| AC-9 | unit | tests/test_eta_multi_phase_heuristic.py::test_judge_phase_estimated_via_max_iterations_factor_before_observed | 0 |
| AC-9 | unit | tests/test_eta_multi_phase_heuristic.py::test_judge_phase_blended_estimate_once_observed_rate_available | 0 |
| AC-9 | unit | tests/test_eta_multi_phase_heuristic.py::test_eta_omits_judge_phase_when_judge_disabled | 0 |
| AC-9 | unit | tests/test_eta_multi_phase_heuristic.py::test_eta_omits_judge_phase_when_winning_provider_is_deepseek | 0 |
| AC-9 | unit | tests/test_quality_judge_snapshot_callback.py::test_callback_none_is_complete_noop | 0 |
| AC-9 | unit | tests/test_quality_judge_snapshot_callback.py::test_callback_invoked_at_scoring_and_retranslating_substeps_with_attempt_index | 0 |
| AC-9 | resilience | tests/test_quality_judge_snapshot_callback.py::test_callback_that_raises_does_not_break_judge_loop | 0 |
| AC-9 | unit | app/frontend/src/components/domain/TranslationProgress.test.jsx::test_renders_judge_tier_badge_attempt_counter_and_substep_label | 0 |
| AC-9 | resilience | app/frontend/src/components/domain/TranslationProgress.test.jsx::test_renders_without_error_when_judge_fields_absent_non_judge_stage_or_older_job | 0 |

## Test Families Required
| family | tier | notes |
|---|---|---|
| unit | 0 | JobStatus schema field shape/enum values incl. `current_stage="judge"` and the 3 judge-only fields; multi-phase ETA (BR-98) pure calc table cases incl. phase-3 judge term (max-iterations estimate before observed, blended rate once observed, `JUDGE_ENABLED=false`/`deepseek`-provider omission per BR-97); JobRecord single-struct capture + overhead assertion; frontend StageDetailPanel/StageBadge render + label mapping incl. judge tier badge/attempt counter/substep label; `run_judge_loop` optional snapshot-callback no-op and invocation-shape checks |
| contract | 1 | Additive JobStatus compatibility via `TestClient` with `job_manager` mocked at consumer binding (`app.backend.api.routes.job_manager`), matching `tests/test_jobstatus_download_url.py::_make_job()` pattern — covers the 3 new judge-only fields and the `judge` enum value; `openapi.yml`/`openapi.json` export-freshness gate; BR-98 (renamed `eta-multi-phase-pipeline`), data-shape-contract.md, and css-contract.md doc entries verified by `cdd-kit validate` (gate-level, not a pytest node) |
| integration | 1 | Critique-loop → structured snapshot: call `translate_texts()` directly (not `translate_document()`, per wrong-entry-point guard); mock only at the LLM-client boundary (`patch.object`, collection-time reference), asserting `status_callback` receives distinct stage/source/draft/score/adopted values at translate→critique→qe-score→adopt transitions; separately, `job_manager`'s wiring of the optional snapshot callback into `run_judge_loop` writes the judge sub-step snapshot onto `JobRecord` at both the scoring and retranslating sub-steps |
| data-boundary | 1 | New fields null in all documented legitimate cases: job just started, `CRITIQUE_LOOP_ENABLED=false`/`QE_ENABLED=false`, mid-transition; the 3 judge-only fields additionally null when `JUDGE_ENABLED=false`, winning provider is `deepseek` (BR-97), or the job is not currently in the judge stage |
| resilience | 1 | Frontend does not throw when backend response has the new fields (incl. the 3 judge fields) absent, partially populated, or transitioning between polls; `run_judge_loop`'s optional snapshot callback is fail-soft — default `None` is a complete no-op, and a callback that raises must not abort the judge loop |

## Test Update Contract
| existing test | action | reason |
|---|---|---|
| tests/test_jobstatus_download_url.py | none | additive-only change; `_make_job()` helper already sets `status_detail=None`, unaffected by new fields (`getattr(..., None)` default) |
| tests/test_eta_two_phase_heuristic.py | rename → tests/test_eta_multi_phase_heuristic.py | BR-98 renamed to `eta-multi-phase-pipeline` (translate / critique+QE / judge, 3 phases not 2); existing phase-1/phase-2 test cases carry over unchanged under the new filename, phase-3 (judge) cases are additive |
| tests/test_jobstatus_stage_detail.py | extend | add `current_stage="judge"` enum coverage + shape/null-tolerance for the 3 new judge-only fields |
| tests/test_job_manager_current_segment.py | extend | add judge snapshot-write assertion at the scoring and retranslating sub-steps |
| tests/test_quality_judge_snapshot_callback.py | new | additive optional snapshot-callback param on `run_judge_loop`; null-safety (`None`=no-op) and fail-soft (raising callback must not break the loop) |
| app/frontend/src/components/domain/TranslationProgress.test.jsx | extend | judge stage rendering (tier badge, attempt counter, substep label) + null-tolerance when the 3 judge fields are absent |

## Out of Scope
- Rolling/scrollback history of past segments (explicit non-goal; AC-8 confirms current-only single-struct design)
- New endpoint or SSE/websocket streaming transport (rejected alternatives in design.md ADR-0010)
- Full browser E2E monitoring flow (optional/nightly; no bounded target this pass)
- `batch-critique-qe-scoring`'s round-based batching correctness (sibling change, coordinated via CER-002, not this change's scope)
- Stress / soak / fuzz-monkey tiers (none per change-classification)
- Visual evidence bundle (owned by visual-reviewer / visual-review-report.md, deferred agent)

## Notes
- Mock boundary: HTTP-layer tests mock `app.backend.api.routes.job_manager` (consumer binding); the critique-loop integration test mocks only the LLM client — never internal `translation_service` helper functions.
- Anti-tautology: assert exact `current_stage`/snapshot field values (not mere presence); AC-8 test calls the widened callback 3x and asserts only the last snapshot survives on `JobRecord`, guarding against an accidental list/append implementation.
- `qualityTier`'s existing hardcoded hex (`TranslationProgress.jsx` L4-7) is migrated to CSS tokens as IN-SCOPE cleanup per design.md's Affected Components table (file is already being touched for StageDetailPanel); `TranslationProgress.test.jsx` includes a static no-hardcoded-hex assertion covering both the new and migrated code.
- New backend test files follow `tests/test_jobstatus_download_url.py`'s `_make_job()` mock-shape convention; extend that shape rather than inventing a parallel one.
- Judge-phase amendment (AC-9, added post-incident): `test_eta_two_phase_heuristic.py` is renamed to `test_eta_multi_phase_heuristic.py` to track BR-98's rename; the callback fail-soft test (`test_callback_that_raises_does_not_break_judge_loop`) mirrors this repo's established fail-soft pattern — a raising hook must never propagate into the judge loop.
