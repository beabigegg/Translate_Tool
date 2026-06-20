# Change Classification

## Change Types
- primary: business-logic-change
- secondary: env-change, config-change

## Lane
- feature

## Risk Level
- medium

## Impact Radius
- module-level

## Tier
- 2

## Architecture Review Required
- no

## Required Artifacts

| artifact | create? |
|---|---|
| design.md | no |
| qa-report.md | no |
| visual-review-report.md | no |

## Required Contracts
- API: no
- CSS/UI: no
- Env: yes — add `DEEPSEEK_ENABLED` (default `false`) + sync `.env.example.template` + `env.schema.json`
- Data shape: no
- Business logic: yes — update fallback-chain rule to `[panjit, deepseek]`; document DeepSeek conditional activation
- CI/CD: no

## Required Tests
- unit: fallback-chain resolution — `ollama-local` never selected; DeepSeek excluded when `DEEPSEEK_ENABLED=false`; selection-style assertions at orchestrator seam
- contract: env-contract validation (`tests/test_env_contract.py`); orchestrator traversal no longer has ollama-local branch
- resilience: PANJIT-failure with DeepSeek disabled → graceful failure, no attempt at local provider

## Required Agents
1. `contract-reviewer` — env + business contract updates before implementation
2. `test-strategist` — test-plan.md covering AC-1 through AC-8
3. `ci-cd-gatekeeper` — ci-gates.md
4. `implementation-planner` — implementation-plan.md after contracts + test plan
5. `backend-engineer` — edit providers.yml, orchestrator.py, config.py
6. `qa-reviewer` — release readiness; confirm layout detection untouched

## Inferred Acceptance Criteria
- AC-1: `config/providers.yml` `fallback_chain` is `[panjit, deepseek]`; `ollama-local` is absent from `fallback_chain`
- AC-2: `ollama-local` provider entry remains in providers.yml with `role: layout_assist_only`
- AC-3: `deepseek` provider configured `enabled: ${DEEPSEEK_ENABLED:-false}`; excluded from active chain when no key / `DEEPSEEK_ENABLED=false`
- AC-4: `DEEPSEEK_ENABLED` registered in `contracts/env/env-contract.md`, `env.schema.json`, `.env.example.template`, defaulting to `false`
- AC-5: `ollama-local` branch removed from fallback traversal in `orchestrator.py:431-466`; orchestrator never attempts `ollama-local` as translation fallback
- AC-6: When PANJIT fails and DeepSeek disabled, system fails gracefully without attempting a local translation model
- AC-7: `layout_detector.py` and its Ollama layout path unchanged
- AC-8: Selection-style test asserts resolved fallback ordering at orchestrator consumer seam (not tautological)

## Tasks Not Applicable
- 1.3 (no architecture review)
- 2.1 (no API contract change)
- 2.2 (no CSS/UI)
- 2.4 (no data shape)
- 2.6 (no CI/CD contract)
- 3.3 (no E2E)
- 3.4 (no monkey)
- 3.5 (no stress/soak)
- 4.2 (no frontend)
- 4.3 (no deploy change)
- 5.1 (no UI/UX)
- 5.2 (no visual)
- 6.4 (no nightly/weekly)
