---
change-id: p2-comet-qe
schema-version: 0.1.0
last-changed: 2026-06-19
risk: medium
tier: 2
---

# Test Plan: p2-comet-qe

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | unit | tests/test_quality_evaluation.py::test_qe_enabled_produces_one_score_per_block | 2 |
| AC-1 | data-boundary | tests/test_quality_evaluation.py::test_scores_array_has_one_entry_per_should_translate_element | 2 |
| AC-1 | data-boundary | tests/test_quality_evaluation.py::test_score_block_id_matches_element_id | 2 |
| AC-1 | integration | tests/test_translation_strategy.py::test_qe_hook_called_after_translate_document | 2 |
| AC-2 | endpoint | tests/test_quality_evaluation.py::test_quality_endpoint_returns_200_available_with_scores | 2 |
| AC-3 | endpoint | tests/test_quality_evaluation.py::test_quality_endpoint_returns_200_pending_when_job_running | 2 |
| AC-3 | endpoint | tests/test_quality_evaluation.py::test_quality_endpoint_returns_200_disabled_when_qe_off | 2 |
| AC-3 | endpoint | tests/test_quality_evaluation.py::test_quality_endpoint_returns_200_unavailable_when_scoring_failed | 2 |
| AC-3 | endpoint | tests/test_quality_evaluation.py::test_quality_endpoint_returns_404_for_unknown_job | 2 |
| AC-4 | contract | tests/contract/ (openapi export --check enforced by CI gate) | 2 |
| AC-5 | data-boundary | tests/test_quality_evaluation.py::test_score_block_id_matches_element_id | 2 |
| AC-6 | contract | tests/test_env_contract.py::TestEnvContractDeclared::test_qe_enabled_declared | 2 |
| AC-6 | contract | tests/test_env_contract.py::TestEnvContractDeclared::test_qe_model_name_declared | 2 |
| AC-6 | contract | tests/test_env_contract.py::TestEnvContractDeclared::test_qe_device_declared | 2 |
| AC-7 | unit | tests/test_quality_evaluation.py::test_qe_disabled_skips_scoring | 2 |
| AC-7 | resilience | tests/test_quality_evaluation.py::test_qe_model_load_failure_sets_unavailable | 2 |
| AC-7 | resilience | tests/test_quality_evaluation.py::test_qe_scoring_exception_sets_unavailable | 2 |
| AC-7 | resilience | tests/test_quality_evaluation.py::test_qe_invalid_device_falls_back_to_cpu | 2 |
| AC-7 | integration | tests/test_translation_strategy.py::test_qe_hook_not_called_when_disabled | 2 |
| AC-8 | unit | tests/test_quality_evaluation.py::test_qe_score_includes_model_name | 2 |
| AC-8 | unit | tests/test_quality_evaluation.py::test_qe_zero_translatable_elements_produces_empty_scores | 2 |
| AC-8 | integration | tests/test_translation_strategy.py::test_translate_texts_unaffected_by_qe_change | 2 |

## Test Families Required

| family | tier | notes |
|---|---|---|
| unit | 2 | New file tests/test_quality_evaluation.py: scorer logic, enable/disable flag, score shape, BR-54–BR-57 |
| endpoint | 2 | Same file: FastAPI TestClient, GET /api/jobs/{id}/quality, all qe_status variants and 404 |
| data-boundary | 2 | Same file: count assertion keyed to element_id; zero-should_translate case |
| resilience | 2 | Same file: model load exception, scoring exception, invalid QE_DEVICE; assert job stays completed |
| integration | 2 | Extend tests/test_translation_strategy.py: mock at quality_evaluator module boundary; assert call_count |
| contract | 2 | Extend tests/test_env_contract.py: QE_ENABLED, QE_MODEL_NAME, QE_DEVICE in env-contract.md and .env.example.template |

## Mock Discipline

- Patch COMET model at `app.backend.services.quality_evaluator.load_model`, NOT at the `comet` package source path — Python binds the name at import time (CLAUDE.md mock.patch lesson).
- Integration tests in test_translation_strategy.py MUST assert `mock.call_count` or use `assert_called_once_with` on the QE hook mock — asserting only on the job result is tautological (CLAUDE.md tautological-test selection lesson).

## TDD Sequence

Write all tests in tests/test_quality_evaluation.py and the new methods in tests/test_env_contract.py and tests/test_translation_strategy.py BEFORE implementation. All listed tests must fail (ImportError or assertion failure) until the implementation exists.

## Out of Scope

- GPU VRAM performance benchmarking
- COMET model download / first-run network behavior
- Frontend UI exposure of quality scores (deferred to future change)
- Stress / soak testing (Tier 2; not required per change-classification.md)
- E2E browser tests (no UI surface for QE scores)
- Verifying COMET numeric accuracy against ground-truth reference scores

## Notes

- Table P in contracts/business/business-rules.md is the authoritative decision table; each row maps to one test above.
- BR-57 default is `QE_ENABLED=false`; enabled-path tests must monkeypatch the flag explicitly.
- AC-4 openapi export --check is a CI gate command, not a pytest test; no duplicate pytest assertion needed.
