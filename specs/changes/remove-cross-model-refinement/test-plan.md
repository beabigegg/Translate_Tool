---
change-id: remove-cross-model-refinement
schema-version: 0.1.0
last-changed: 2026-06-20
risk: medium
tier: 2
---

# Test Plan: remove-cross-model-refinement

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | unit | tests/test_env_contract.py | 0 |
| AC-2 | unit | tests/test_provider_fallback.py | 0 |
| AC-3 | unit | tests/test_ollama_client_dynamic_strategy.py | 0 |
| AC-3 (protocol) | unit | tests/test_llm_client_protocol.py | 0 |
| AC-4 | unit | tests/test_model_router.py | 0 |
| AC-5 | dead-reference | tests/test_dead_references.py | 0 |
| AC-6 | dead-reference | tests/test_dead_references.py | 0 |
| AC-7 | integration | tests/test_translation_strategy.py | 1 |
| AC-7 | integration | tests/test_sentence_mode_consistency.py | 1 |
| AC-8 | contract | tests/test_env_contract.py | 1 |
| AC-8 | contract | tests/test_term_audit.py | 1 |
| BR-41 replacement | unit | tests/test_glossary_enforcement.py | 0 |
| BR-44 replacement | unit | tests/test_glossary_enforcement.py | 0 |

## Test Families Required

| family | tier | notes |
|---|---|---|
| unit | 0 | RouteGroup shape, ollama client, LLM protocol, env contract, glossary/critique coverage |
| dead-reference | 0 | grep-based assertions: removed symbols return zero hits in app/ and tests/ |
| integration | 1 | Cloud (PANJIT) path unchanged: sentence mode, translation strategy cache key |
| contract | 1 | env-contract + API conformance via `cdd-kit validate --contracts` |

## New vs Modified Test Files

**NEW — must be created and green before `test_hy_mt_quality_refinement.py` is deleted (R-1):**

`tests/test_dead_references.py` (NEW) — AC-5 / AC-6. One test per symbol; each invokes
`rg` in a subprocess and asserts returncode 1 (zero hits in `app/` and `tests/`). Symbols:
`refine_translation`, `refine_client`, `refine_model`, `CROSS_MODEL_REFINEMENT_ENABLED`,
`REFINEMENT_ENABLED`, `REFINEMENT_MIN_CHARS`, `_build_refine_prompt`,
`_build_refine_system_prompt`, `refiner_num_ctx`, `HY-MT`, `TranslateGemma`.

`tests/test_glossary_enforcement.py` (NEW) — replacement proof anchor for BR-41 and BR-44,
replacing all 6 orphaned Table M / Table N rows. Required test names and coverage:

- `test_critique_loop_runs_with_glossary_terms` — BR-44 / Table M row 1
- `test_critique_loop_runs_without_glossary_terms` — BR-44 / Table M row 2
- `test_critique_iterations_total_incremented` — BR-44 / Table M row 3
- `test_critique_exception_degrades_gracefully` — BR-44 / Table M row 4
- `test_critique_terminates_at_max_iterations` — BR-44 / Table M row 5
- `test_glossary_term_present_in_output_accepted` — BR-41 / Table N row 1
- `test_glossary_term_missing_triggers_substitution` — BR-41 / Table N row 2
- `test_no_terms_in_db_is_noop` — BR-41 / Table N row 5

Mock boundary: `app.backend.services.translation_service.translate_blocks_batch`.
Entry point: `translate_texts()` with `CRITIQUE_LOOP_ENABLED=True` (not `translate_document()`).
See CLAUDE.md tautological-test lesson: mock at the bound name in the consumer module.

**MODIFIED — existing tests that reference removed symbols:**

| existing test | action | reason |
|---|---|---|
| tests/test_model_router.py::TestLegacyOllamaPath (lines 502-514) | update | After HY-MT/TGEMMA rows removed, vi/de/ja fall to DEFAULT_MODEL; assert that, not HYMT — R-2 |
| tests/test_llm_client_protocol.py (lines 48-50, 75, 135, 186-189) | update | `refine_translation` removed from protocol — R-3 |
| tests/test_sentence_mode_consistency.py (lines 265, 276) | update | `refine_client` removed from `translate_texts` signature |
| tests/test_term_audit.py (lines 462, 516) | update | `refine_model=None` removed from `RouteGroup(...)` construction |
| tests/test_ollama_client_dynamic_strategy.py (lines 37, 45) | check/update | Verify HY-MT model fixture does not depend on removed symbols |
| tests/test_hy_mt_quality_refinement.py | delete | Entire file retired (AC-5); only after test_glossary_enforcement.py is green |

## business-rules.md Pointer Retargeting (R-1 prerequisite)

Contract-reviewer must retarget these rows to `tests/test_glossary_enforcement.py`
before backend-engineer deletes `tests/test_hy_mt_quality_refinement.py`:

| location | row / rule | current pointer |
|---|---|---|
| line 56 | BR-41 proof column | tests/test_hy_mt_quality_refinement.py |
| line 59 | BR-44 proof column | tests/test_hy_mt_quality_refinement.py |
| Table M lines 211-215 | all 5 critique-loop rows | tests/test_hy_mt_quality_refinement.py |
| Table N lines 221-222, 225 | 3 glossary enforcement rows | tests/test_hy_mt_quality_refinement.py |

Table M line 216 (`test_translation_strategy.py`) and Table N lines 223-224
(`test_term_state_machine.py`) are already correctly pointed — do not change them.

## Test Execution Ladder

| phase | required | command source | max failures | result artifact |
|---|---:|---|---:|---|
| collect | yes | cdd-kit test select | 1 | test-runs/<run-id>/summary.json |
| targeted | yes | cdd-kit test select | 1 | test-evidence.yml |
| changed-area | yes | cdd-kit test select | 1 | test-evidence.yml |
| contract | yes (env + business touched) | cdd-kit validate | 1 | test-evidence.yml |
| full | final/CI | cdd-kit test run --phase full | 1 | test-evidence.yml |

Gate: `cdd-kit gate remove-cross-model-refinement`

## Out of Scope

- Local Ollama refinement behavior (never on cloud path; no regression coverage required).
- Layout detection, PDF rendering, chunking, QE scoring paths — untouched.
- `scripts/` and `docs/` directories — dead-reference grep bounded to `app/` and `tests/` per AC-6.

## Notes

- `test_glossary_enforcement.py` and retargeted business-rules.md rows are both required before the deletion of `test_hy_mt_quality_refinement.py` (R-1 ordering from implementation-plan.md).
- `test_dead_references.py` must FAIL before the symbols are removed (confirming non-tautology), then pass after.
- `TestLegacyOllamaPath` update is an expected test-update, not a waiver — see R-2 in implementation-plan.md.
- Do not conflate `CRITIQUE_LOOP_ENABLED` (live feature, BR-44) with `CROSS_MODEL_REFINEMENT_ENABLED` (dead code, AC-1).
