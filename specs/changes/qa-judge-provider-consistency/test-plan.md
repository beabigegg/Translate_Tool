---
change-id: qa-judge-provider-consistency
schema-version: 0.1.0
last-changed: 2026-07-07
risk: medium
tier: 2
---

# Test Plan: qa-judge-provider-consistency

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | unit | tests/test_quality_judge.py::test_translation_client_resolves_cloud_provider_and_translate_model | 0 |
| AC-1 | integration | tests/test_orchestrator_judge.py::test_translate_fn_uses_judge_translation_client_not_last_client | 1 |
| AC-2 | integration | tests/test_orchestrator_judge.py::test_translate_fn_request_params_unchanged_when_last_client_already_panjit | 1 |
| AC-3 | unit | tests/test_quality_judge.py::test_translation_client_reuses_existing_config_symbols_only | 0 |
| AC-4 | unit | tests/test_quality_judge.py::test_translation_client_model_may_differ_from_scoring_client_same_provider | 0 |
| AC-4 | unit | tests/test_quality_judge.py::test_translation_client_falls_back_to_judge_model_when_translate_key_absent | 0 |
| AC-5 | integration | tests/test_orchestrator_judge.py::test_judge_skipped_when_provider_is_deepseek | 1 |
| AC-5 | integration | tests/test_orchestrator_judge.py::test_judge_still_fires_when_provider_is_panjit | 1 |
| AC-6 | contract | contracts/business/business-rules.md (cdd-kit validate --contracts) | 1 |
| AC-7 | integration | tests/test_orchestrator_judge.py::test_translate_fn_no_ollama_default_fallback_when_judge_runs | 1 |
| AC-7 | unit | tests/test_quality_judge.py::test_translation_client_never_none | 0 |

## Test Families Required

Applicable: unit, integration, contract.
Not applicable: e2e, data-boundary, resilience, monkey, stress, soak (see Out of Scope).

| family | tier | notes |
|---|---|---|
| unit | 0 | `QualityJudge.translation_client` property + generalized `_build_cloud_client(model=...)`: provider/model resolution, `models.translate`→`JUDGE_MODEL` fallback, ollama-provider symmetry, no-new-config-surface. Extend tests/test_quality_judge.py (existing `test_judge_client_is_ollama_not_model_router` is the closest precedent for construction-style assertions). |
| integration | 1 | `_translate_fn` closure wiring inside `job_manager._run_job`: assert it calls `_judge.translation_client.translate_once(...)`, never `last_client`/`OllamaClient(DEFAULT_MODEL)`. Extend tests/test_orchestrator_judge.py using its existing `_run_job_with_judge_check` harness — give the fake judge's `run_judge_loop` a `side_effect` that actually invokes the passed `translate_fn` callback so the real closure body executes (anti-tautology: current harness's `run_judge_loop` mock returns a canned result without invoking the callback). |
| contract | 1 | BR-98 present in Rule Inventory + Table U row, cross-referenced from BR-97; env-contract.md review-only cross-ref, no new var. Runs under `cdd-kit validate --contracts`. |

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
| tests/test_orchestrator_judge.py::test_judge_skipped_when_provider_is_deepseek | update | add assertion that `translation_client` is never accessed on the mock judge, proving BR-97 still skips scoring AND re-translation together (AC-5) — same outcome, stronger assertion |

## Stop Rules

- Do not run broad pytest before targeted and changed-area phases pass.
- Do not investigate more than the first failure per phase.
- Do not classify any failure as known, pre-existing, waived, or allowed.
- If full suite fails, record the first failure and block the gate.

## Out of Scope
- `model_router.py` main-translation routing/fallback chain (non-goal; covered by tests/test_provider_fallback.py, untouched here).
- In-line critique loop / `_critique_gate_adopt` (`translation_service.py`) — sibling `batch-critique-qe-scoring` change.
- Cancellation/timeout behavior in the judge call site — sibling `qa-judge-hang-recovery` (depends on this change landing first).
- BR-92 rescore resolution — sibling `br92-rescore-resolution`.
- `judge_layout()` / image scoring (BR-95, always-local) — untouched by this change.
- E2E, resilience, monkey, stress, soak — no new failure surface; existing job-lifecycle E2E coverage unaffected.

## Notes
- **Mock-boundary risk**: `_build_cloud_client()`/`translation_client` lazily import `OpenAICompatibleClient` *inside* the method (not module-level in `quality_judge.py`). Patch at the definition module — `app.backend.clients.openai_compatible_client.OpenAICompatibleClient` — never `app.backend.services.quality_judge.OpenAICompatibleClient` (no such module attribute exists to patch).
- **Production-flow finding**: `job_manager.py` L405-406 unconditionally resets `last_client = None` at the end of every route-group loop iteration, before the judge hook (L472+) runs — at judge-invocation time `last_client` is always `None` today regardless of winning provider. AC-2's "already-panjit" no-op is therefore proven by comparing constructed request parameters (base_url/model/prompt) between `translation_client` and the old `last_client`-sourced panjit client, not by driving `create_job()` into a non-None `last_client` state at judge time (unreachable pre- and post-fix alike).
- Extend `tests/test_quality_judge.py` and `tests/test_orchestrator_judge.py` in place — no new test files; matches this repo's existing D4/BR-97 coverage precedent and the shared `_run_job_with_judge_check` harness.
