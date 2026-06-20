---
change-id: fallback-chain-cloud-providers
schema-version: 0.1.0
last-changed: 2026-06-20
risk: medium
tier: 2
---

# Test Plan: fallback-chain-cloud-providers

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1: fallback_chain is [panjit, deepseek]; ollama-local absent | unit | tests/test_provider_fallback.py::TestFallbackChainConfig::test_fallback_chain_is_panjit_deepseek | 0 |
| AC-2: ollama-local retained with role:layout_assist_only | unit | tests/test_provider_fallback.py::TestFallbackChainConfig::test_ollama_local_role_is_layout_assist_only | 0 |
| AC-3: deepseek excluded from active chain when DEEPSEEK_ENABLED=false | unit | tests/test_provider_fallback.py::TestFallbackChainConfig::test_deepseek_excluded_when_disabled | 0 |
| AC-3: deepseek included in active chain when DEEPSEEK_ENABLED=true | unit | tests/test_provider_fallback.py::TestFallbackChainConfig::test_deepseek_included_when_enabled | 0 |
| AC-4: DEEPSEEK_ENABLED declared in env-contract.md | contract | tests/test_env_contract.py::TestEnvContractDeclared::test_deepseek_enabled_declared | 0 |
| AC-5: ollama-local break-branch absent from orchestrator traversal | contract | tests/test_provider_fallback.py::TestOrchestratorFallbackTraversal::test_ollama_local_branch_absent_from_orchestrator | 0 |
| AC-5/AC-8: selection — orchestrator resolves deepseek as fallback, not ollama-local | unit | tests/test_provider_fallback.py::TestOrchestratorFallbackTraversal::test_fallback_order_selection_at_orchestrator_seam | 0 |
| AC-6: PANJIT failure + DeepSeek disabled → graceful failure, no local attempt | resilience | tests/test_provider_fallback.py::TestOrchestratorFallbackTraversal::test_panjit_fail_deepseek_disabled_graceful | 1 |
| AC-7: layout_detector.py unchanged | contract | tests/test_provider_fallback.py::TestLayoutDetectorUnchanged::test_layout_detector_source_unmodified | 0 |

## Test Families Required

| family | tier | notes |
|---|---|---|
| unit | 0 | Selection-style: assert WHICH provider is chosen, not just count. Patch `load_providers_config` at the consumer binding `app.backend.processors.orchestrator` per CLAUDE.md mock-boundary rule. |
| contract | 0 | Text-inspection: `DEEPSEEK_ENABLED` in env-contract.md; ollama-local break-guard absent from orchestrator.py:431-466; layout_detector.py landmark string stable. |
| resilience | 1 | PANJIT ConnectionError + deepseek disabled → process_files failure; assert no Ollama/localhost endpoint contacted. |

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| tests/test_provider_fallback.py::TestOrchestratorProviderWiring::_PANJIT_PROVIDERS_CONFIG | update | Class-level fixture has `fallback_chain: [panjit, ollama-local]`; update to `[panjit, deepseek]` to reflect post-change config shape. |

## Test Execution Ladder

| phase | required | command source | max failures | result artifact |
|---|---:|---|---:|---|
| collect | yes | cdd-kit test select | 1 | test-runs/<run-id>/summary.json |
| targeted | yes | `pytest tests/test_provider_fallback.py tests/test_env_contract.py -x -q` | 1 | test-evidence.yml |
| changed-area | yes | cdd-kit test select | 1 | test-evidence.yml |
| contract | yes | cdd-kit validate | 1 | test-evidence.yml |
| quality | if configured | ci-gates.md | 1 | test-evidence.yml |
| full | final/CI | cdd-kit test run --phase full | 1 | test-evidence.yml |

## Stop Rules

- Do not run broad pytest before targeted and changed-area phases pass.
- Do not investigate more than the first failure per phase.
- Do not classify any failure as known, pre-existing, waived, or allowed.
- If full suite fails, record the first failure and block the gate.

## Out of Scope

- DeepSeek API key UI (belongs to settings-page-cloud-redesign)
- E2E / browser tests
- Stress, soak, monkey tests

## Notes

New test classes go in `tests/test_provider_fallback.py` (extend, do not duplicate). `test_deepseek_enabled_declared` extends `TestEnvContractDeclared` in `tests/test_env_contract.py`. AC-5 branch-removal test reads orchestrator source via `Path(__file__).parent.parent` — never a hardcoded path (per CLAUDE.md). The existing `test_ollama_used_when_no_cloud_provider` (provider_id=None path) remains valid and is NOT the same scenario as AC-5/AC-8; do not delete it.
