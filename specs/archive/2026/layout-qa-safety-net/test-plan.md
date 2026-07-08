---
change-id: layout-qa-safety-net
schema-version: 0.1.0
last-changed: 2026-07-08
risk: low
tier: 3
---

# Test Plan: layout-qa-safety-net

Ref: `change-classification.md` (AC-1..AC-9), `design.md` (seam + Decisions 1-5),
`docs/adr/0015-layout-qa-metric-core-in-runtime.md`. Do not restate here.

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | integration | tests/test_pdf_render_warnings.py::TestLayoutQaDisabled::test_flag_off_run_layout_qa_not_invoked_no_warning | 1 |
| AC-2 | unit | tests/test_layout_qa.py::test_biou_regression_below_budget_emits_one_aggregated_warning | 0 |
| AC-2 | integration | tests/test_pdf_render_warnings.py::TestLayoutQaWarning::test_biou_regression_warning_fires_through_real_seam | 1 |
| AC-3 | unit | tests/test_layout_qa.py::test_residual_source_text_emits_warning, ::test_biou_and_residual_both_present_aggregate_into_single_entry | 0 |
| AC-4 | resilience | tests/test_layout_qa.py::test_metric_exception_is_caught_returns_none_no_warning, ::test_corrupt_output_pdf_reopen_is_fail_soft | 0 |
| AC-4 | data-boundary | tests/test_layout_qa.py::test_empty_source_bboxes_no_raise, ::test_empty_rendered_bboxes_no_raise, ::test_mismatched_box_counts_no_raise, ::test_no_text_page_no_raise, ::test_page_over_max_boxes_per_page_short_circuits_without_raising | 0 |
| AC-4 | integration | tests/test_pdf_render_warnings.py::TestLayoutQaWarning::test_layout_qa_exception_never_fails_job_or_fabricates_warning | 1 |
| AC-5 | unit | tests/test_layout_qa.py::TestMetricCoreIdentity::test_biou_shim_same_object_as_runtime, ::test_residual_text_shim_same_object_as_runtime, ::test_truncation_rate_shim_same_object_as_runtime, ::test_iou_and_budget_importable_from_shim | 0 |
| AC-5 | unit (existing, must stay green) | tests/test_layout_metrics.py::TestModuleImports (L277-291; L19-21 constant import) — not duplicated, only kept passing | 0 |
| AC-6 | contract | tests/test_env_contract.py::TestEnvContractDeclared::test_layout_qa_enabled_declared, ::test_layout_qa_max_boxes_per_page_declared, ::test_layout_qa_enabled_wired_in_config_default_false | 0 |
| AC-7 | contract | tests/test_layout_qa.py::test_br_106_documented_in_business_rules | 0 |
| AC-8 | unit | tests/test_layout_qa.py::test_office_processors_do_not_import_run_layout_qa | 0 |
| AC-8 | integration (negative coverage) | tests/test_pdf_render_warnings.py::TestLayoutQaWarning (PDF-only fixtures; no docx/pptx/xlsx counterpart added) | 1 |
| AC-9 | unit | tests/test_layout_qa.py::test_biou_regression_budget_is_named_constant_and_consumed_by_run_layout_qa | 0 |

## Test Families Required

| family | tier | notes |
|---|---|---|
| unit | 0 | `run_layout_qa` signal composition (BIoU/residual/aggregation), named-constant consumption, metric-shim import identity — tests/test_layout_qa.py |
| data-boundary | 0 | degenerate bbox lists, no-text page, mismatched box counts, corrupt/unreadable output PDF, `LAYOUT_QA_MAX_BOXES_PER_PAGE` short-circuit — none raise — tests/test_layout_qa.py |
| resilience | 0 | forced metric/reopen exceptions caught+logged; job unaffected; no fabricated warning — tests/test_layout_qa.py |
| contract | 0 | env-contract.md + .env.example.template + env.schema.json declare `LAYOUT_QA_ENABLED`/`LAYOUT_QA_MAX_BOXES_PER_PAGE` (default off/500); BR-106 presence — tests/test_env_contract.py, tests/test_layout_qa.py |
| integration | 1 | real `_render_with_fallback` seam fires `run_layout_qa` exactly once per warranted file via `warnings_callback`→`_record_job_warning`; flag-off proves the metric functions are never invoked — tests/test_pdf_render_warnings.py (new `TestLayoutQaDisabled`/`TestLayoutQaWarning` classes, sibling to existing `TestTruncationDisclosureWarning`, reusing its `_make_doc`/`_make_job` helpers) |

## Test Execution Ladder

| phase | required | command source | max failures | result artifact |
|---|---:|---|---:|---|
| collect | yes | cdd-kit test select | 1 | test-runs/<run-id>/summary.json |
| targeted | yes | cdd-kit test select | 1 | test-evidence.yml |
| changed-area | yes | cdd-kit test select | 1 | test-evidence.yml |
| contract | if affected | cdd-kit validate | 1 | test-evidence.yml |
| quality | if configured | ci-gates.md | 1 | test-evidence.yml |
| full | final/CI | cdd-kit test run --phase full | 1 | test-evidence.yml |

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| — | none | Metric-core move (Decision 1) preserves all public names/behavior; `tests/metrics/*` become re-export shims. No existing test (incl. `tests/test_layout_metrics.py`) asserts internal file structure beyond public imports, so none require behavior updates — see AC-5. |

## Stop Rules

- Do not run broad pytest before targeted and changed-area phases pass.
- Do not investigate more than the first failure per phase.
- Do not classify any failure as known, pre-existing, waived, or allowed.
- If full suite fails, record the first failure and block the gate.

## Out of Scope

- Office (docx/pptx/xlsx) layout-QA wiring — non-goal; covered only by an absence check (AC-8) that those processors never import `run_layout_qa`.
- New API endpoint / UI component / `openapi.yml` re-export — non-goal, no test surface.
- E2E, visual/pixel regression, fuzz-monkey, stress, soak (Tier 3/4 test ladder) — fail-soft is fully provable at unit+integration; no real-infra/load harness per `change-classification.md` Required Tests.
- Re-verifying BR-104 truncation-disclosure behavior itself — already covered by existing `TestTruncationDisclosureWarning`; this plan adds the sibling layout-QA warning path alongside it, not a re-test of BR-104.
- PR #13 branch content — design reference only per `context-manifest.md`; not read, not ported wholesale.

## Notes

- Anti-tautology: integration tests must drive the real seam (`_render_with_fallback` via `job_manager.create_job`, per `test_orchestrator_judge.py`'s pattern), not a mock wrapper; the flag-off test asserts the metric functions are never called, not merely that `job.warnings` is empty.
- Warning assertions check WHICH content (affected page ids / BIoU-vs-residual signal named), not just entry count, per AC-2/AC-3.
- Extend `tests/test_pdf_render_warnings.py::TestTruncationDisclosureWarning`'s existing fixtures/helpers (`_make_doc`, `_make_job`) rather than duplicating setup.
- No Tier 3/4 (real-infra/soak): change is fail-soft, default-off, in-process only.
