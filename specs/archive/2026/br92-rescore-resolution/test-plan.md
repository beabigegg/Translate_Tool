---
change-id: br92-rescore-resolution
schema-version: 0.1.0
last-changed: 2026-07-07
risk: medium
tier: 2
---

# Test Plan: br92-rescore-resolution

Direction confirmed: **RETIRE** (change-request Open Questions). This plan
covers only "prove BR-92 / QE_RESCORE_THRESHOLD is gone everywhere" — no new
behavioral coverage (no build path).

## Acceptance Criteria → Test Mapping
| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-4 | unit | tests/test_quality_evaluation.py::test_qe_rescore_threshold_not_in_config | 0 |
| AC-4 | contract | tests/test_env_contract.py::TestQeRescoreThresholdRetired::test_qe_rescore_threshold_removed_from_contract | 0 |
| AC-4 | contract | tests/test_env_contract.py::TestQeRescoreThresholdRetired::test_qe_rescore_threshold_removed_from_schema | 0 |
| AC-4 | contract | tests/test_env_contract.py::TestQeRescoreThresholdRetired::test_qe_rescore_threshold_removed_from_env_template | 0 |
| AC-4 | contract | tests/test_env_contract.py::TestQeRescoreThresholdRetired::test_qe_rescore_threshold_removed_from_config | 0 |
| AC-2 | contract | tests/test_quality_evaluation.py::test_br_92_removed_from_business_rules | 0 |
| AC-2 | contract | tests/test_env_contract.py::test_env_contract_qe_enabled_row_scrubbed_of_rescore_claim | 0 |
| AC-6 | contract | tests/test_env_contract.py::test_qe_rescore_threshold_zero_references_repo_wide | 0 |
| AC-3 | unit | tests/test_quality_evaluation.py (deletion, no replacement — see Test Update Contract) | 0 |
| AC-2 (data-shape) | contract-review (manual, no pytest) | contracts/data/data-shape-contract.md:780,787 | gate-review |

## Test Families Required
| family | tier | notes |
|---|---|---|
| unit | 0 | `config.py` no longer exposes `QE_RESCORE_THRESHOLD` (`hasattr` false); replaces the 4 deleted presence/parsing tests |
| contract | 0 | env-contract.md, env.schema.json, `.env.example.template`, business-rules.md all scrubbed; one repo-scoped grep sweep confirms no residual reference on the live surface |

## Test Update Contract
| existing test | action | reason |
|---|---|---|
| tests/test_quality_evaluation.py::test_below_threshold_triggers_retranslation | delete | tautological (asserts a bare list comprehension, not production routing); BR-92 retired |
| tests/test_quality_evaluation.py::test_threshold_env_var_parsed_as_float | delete | asserts presence/parsing of a var being removed |
| tests/test_quality_evaluation.py::test_rescore_threshold_has_correct_type_and_default | delete | asserts presence of a var being removed |
| tests/test_quality_evaluation.py::test_rescore_threshold_out_of_range_rejected | delete | asserts parsing of a var being removed |
| tests/test_env_contract.py::TestQeDefault::test_qe_rescore_threshold_declared_in_contract | delete→replace | inverted into `test_qe_rescore_threshold_removed_from_contract` |
| tests/test_env_contract.py::TestQeDefault::test_qe_rescore_threshold_in_schema | delete→replace | inverted into `test_qe_rescore_threshold_removed_from_schema` |
| tests/test_env_contract.py::TestQeDefault::test_qe_rescore_threshold_in_env_template | delete→replace | inverted into `test_qe_rescore_threshold_removed_from_env_template` |
| tests/test_env_contract.py::TestQeDefault::test_qe_rescore_threshold_wired_in_config | delete→replace | inverted into `test_qe_rescore_threshold_removed_from_config` |
| tests/test_env_contract.py::TestQeDefault::test_qe_enabled_default_true_in_contract | keep | asserts AC-3 QE_ENABLED default, unrelated to BR-92 |
| tests/test_env_contract.py::TestQeDefault::test_qe_enabled_default_true_in_config | keep | asserts AC-3 QE_ENABLED default, unrelated to BR-92 |

## Out of Scope
- Any build-path test (integration/resilience for a rescore→re-translate hook) — direction is retire, not build.
- BR-89/90 critique loop, BR-72-77 LLM-judge gate, BR-55/56 dashboard COMET scoring — non-goals, untouched, no test changes.
- `.cdd/code-map.yml:306` — auto-regenerates, no test needed.

## Notes
- Grep-verified full list of live (non-archived) references before writing this
  plan: `app/backend/config.py:133-136`, `contracts/business/business-rules.md:104`,
  `contracts/env/env-contract.md:37-38`, `.env.example.template`, `env.schema.json`,
  `contracts/data/data-shape-contract.md:780,787`, plus the 8 test functions listed above.
  `specs/archive/2026/quality-metrics-gating/*` and `specs/changes/*` narrative
  docs are historical and intentionally excluded from the zero-reference sweep.
- `env-contract.md:37` (QE_ENABLED row) keeps the var but must drop the
  "post-job rescore threshold (AC-2)" clause; the contract test asserts the
  substring "rescore" is absent from the whole file, not just the deleted row.
- data-shape-contract.md correction is prose (two lines: intro sentence at 780
  and table cell at 787, both citing BR-92) — a contract-authoring fix verified
  by contract-reviewer/qa-reviewer at gate time, not a pytest assertion.
