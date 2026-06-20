# Archive — fallback-chain-cloud-providers

## Change Summary

Replaced `ollama-local` as the translation fallback provider with `deepseek` in `config/providers.yml.example`. The `ollama-local` provider entry is retained with `role: layout_assist_only` (layout detection still uses it). The `ollama-local` break-guard was removed from the fallback traversal loop in `orchestrator.py:438-440`. DeepSeek participation in the chain is gated by `DEEPSEEK_ENABLED` (default `false`); when disabled, PANJIT failure causes the job to fail with no local translation fallback attempt.

## Final Behavior

- `fallback_chain: [panjit, deepseek]` (was `[panjit, ollama-local]`)
- `ollama-local` is `role: layout_assist_only` and is never attempted as a translation fallback
- DeepSeek is only active when `DEEPSEEK_ENABLED=true` and a valid key is configured
- PANJIT failure + `DEEPSEEK_ENABLED=false` → job fails gracefully; no local fallback attempt
- Layout detection Ollama path: unchanged

## Final Contracts Updated

- `contracts/business/business-rules.md` — BR-14 updated to name active chain `[panjit, deepseek]`; Table C gained two rows: misconfiguration guard + graceful-failure when both PANJIT and DeepSeek unavailable. schema-version 0.12.1 → 0.13.0
- `contracts/env/env-contract.md` — OLLAMA_BASE_URL annotated: "OLLAMA_BASE_URL is not used by the translation fallback chain." last-changed 2026-06-20
- `contracts/env/.env.example.template` — DeepSeek section comment updated to note fallback chain position 2 and graceful-failure consequence when disabled

## Final Tests Added / Updated

- `tests/test_provider_fallback.py` — stale `_PANJIT_PROVIDERS_CONFIG` fixture updated; new `TestFallbackChainConfig` (4 tests: AC-1/2/3); new `TestOrchestratorFallbackTraversal` (3 tests: AC-5/6/8); new `TestLayoutDetectorUnchanged` (1 test: AC-7); tests now read `providers.yml.example` (tracked) not gitignored `providers.yml` (CI-reproducible)
- `tests/test_env_contract.py` — added `test_deepseek_enabled_declared` (AC-4)

## Final CI/CD Gates

- contract-validation: `cdd-kit validate --contracts`
- env-schema-sync: DEEPSEEK_ENABLED present in `.env.example.template` + `env.schema.json`
- targeted-tests: `pytest tests/test_provider_fallback.py tests/test_env_contract.py -x -q`
- full-test-suite: `pytest tests/ -x -q` (725 pass, 4 skipped)
- change-gate: `cdd-kit gate fallback-chain-cloud-providers`

## Production Reality Findings

- QA blocked initially on: (1) tests reading gitignored `providers.yml` instead of tracked `.example`; (2) `tier-floor-override` absent from tasks.yml; (3) missing `contract` test phase; (4) `providers.yml.example` still had old `[panjit, ollama-local]` chain. All four fixed: tests updated to read `.example`, `tier-floor-override` added, contract phase run, `.example` updated.
- `model_router.py` has no `fallback_chain` reference — confirmed clean, no edits needed.
- `config.py:473-476` already correctly coerces `enabled: "false"` → Python `False` via YAML expansion.

## Lessons Promoted to Standards

- Added to `CLAUDE.md` learnings: "Tests asserting config-file content must read the tracked template (`providers.yml.example`), not the gitignored runtime file (`providers.yml`) — the gitignored file is absent on a fresh CI checkout and causes FileNotFoundError." Evidence: QA blocker finding; tests read gitignored file, producing false-green locally but would error on CI.

## Follow-up Work

- `settings-page-cloud-redesign` change is unblocked (depends on `DEEPSEEK_ENABLED` gate): when the user supplies a DeepSeek API key via the settings UI, `DEEPSEEK_ENABLED=true` activates the chain.

## Cold Data Warning

This archive is historical evidence. Current requirements live in `contracts/` and active project guidance.
