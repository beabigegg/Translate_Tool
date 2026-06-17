# Change Classification — p1-cloud-providers

## Change Types
- primary: feature-add, business-logic-change
- secondary: api-change, env-change, config-externalization, data-shape-change

## Lane
- feature

## Risk Level
- high

## Impact Radius
- cross-module

## Tier
- 1

## Risk Factors
- Cloud provider becomes the **primary** translation path (Ollama demoted to fallback) — this rewires the core translation data-flow, not an additive side feature.
- Fallback chain on primary-offline: silent degradation risk, partial-failure handling, and "which provider actually ran" must be recorded in JobStatus (data-shape + observability surface).
- Removing the hardcoded `model_router.py` routing table in favor of `config/providers.yml` is a module-boundary + data-flow change consumed by `translation_service.py` and `model_router.py`.
- Secret handling: Panjit/DeepSeek API keys must stay in `.env` only, env-var interpolation (`${VAR:-default}`) in YAML — misconfiguration leaks keys or silently disables a provider.
- External network dependency (paid DeepSeek endpoint) — timeout, auth failure, rate-limit, and offline behavior need resilience tests.
- This change is a hard dependency for `p1-provider-routing` and `p1-observability-metrics`; a leaky Protocol or config schema here propagates downstream.

## Architecture Review Required
- yes
- reason: Rewires the core translation routing data-flow (config-driven provider registry replacing hardcoded table), introduces a multi-provider fallback chain with provider-attribution recording, and locks the `providers.yml` schema + fallback semantics that two downstream P1 changes depend on.

## Optional Artifacts

| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | Existing routing behavior described in change-request Known Context + design.md |
| proposal.md | no | Product decision already made; captured in change-request |
| spec.md | no | Behavior decisions fit in design.md + implementation-plan |
| design.md | yes | Architecture Review = yes: provider registry schema, fallback chain semantics, offline detection, provider-attribution shape |
| qa-report.md | no | Promote to yes at QA time only if blocking/approved-with-risk findings arise |
| regression-report.md | no | model_router behavior covered by updated contract tests |
| visual-review-report.md | no | No frontend/UI change |
| monkey-test-report.md | no | Not UI-interaction-heavy |
| stress-soak-report.md | no | Load deferred to observability/routing changes |

## Required Contracts
- API: yes — `/route-info` gains `provider` field; JobStatus exposes provider used
- CSS/UI: no
- Env: yes — document `PANJIT_LLM_BASE_URL`, `PANJIT_API`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_API`; secret-handling rules
- Data shape: yes — JobStatus gains `provider` field
- Business logic: yes — config-driven provider routing rules + fallback chain decision table
- CI/CD: no

## Required Tests
- unit: yes — `OpenAICompatibleClient` (request/response, error mapping), `config.py` providers.yml loading + env interpolation, `model_router` config-driven selection
- contract: yes — Protocol conformance of `OpenAICompatibleClient`; `/route-info` provider field; JobStatus provider field
- integration: yes — translation_service → model_router → provider selection → fallback end-to-end (mocked)
- E2E: no
- visual: no
- data-boundary: yes — JobStatus provider field shape; malformed/missing providers.yml entries
- resilience: yes — primary offline / timeout / auth-failure → fallback → provider recorded
- fuzz/monkey: no
- stress: no
- soak: no

## Required Agents
1. spec-architect — write `design.md` (provider registry schema, fallback semantics, provider-attribution shape)
2. contract-reviewer — update API/env/data/business contracts before implementation
3. test-strategist — author test-plan.md with AC→test mapping
4. ci-cd-gatekeeper — write ci-gates.md
5. implementation-planner — turn design + contracts + tests into execution packet
6. backend-engineer — implement `openai_compatible_client.py`, `config/providers.yml` loading, `model_router.py` refactor, JobStatus provider recording, `/route-info` field
7. qa-reviewer — release readiness, fallback-path verification, secret-handling check

## Tasks Not Applicable
- 2.2 (CSS/UI contract) — no frontend
- 2.6 (CI/CD contract) — no CI/CD contract change
- 3.5 (Stress/soak) — no load surface in this change
- 4.2 (Frontend) — no frontend
- 4.4 (CI/CD workflows) — no new workflow files
- 5.1 (UI/UX review) — no UI
- 5.2 (Visual review) — no UI

## Inferred Acceptance Criteria
- AC-1: `OpenAICompatibleClient` implements the full `LLMClient` Protocol and is verified by a Protocol-conformance/contract test, with no dependency on `OllamaClient` internals.
- AC-2: `OpenAICompatibleClient` successfully translates via OpenAI-compatible `/v1/chat/completions` for both Panjit (gpt-oss:120b / Qwen3.6-35B-A3B-4bit) and DeepSeek (deepseek-v4-flash) endpoints using mocked responses.
- AC-3: `config/providers.yml` is loaded by `config.py` with `${VAR:-default}` env-var interpolation; provider endpoints/keys come from `.env` and no API key appears in source or version control.
- AC-4: `model_router.py` selects model/provider from `providers.yml` (config-driven); previously hardcoded language→model mapping is removed; updated tests cover the config-driven path.
- AC-5: When the primary provider is offline/unreachable, translation automatically falls back to the next provider in the configured chain without failing the job.
- AC-6: The provider actually used for a job is recorded in `JobStatus` and surfaced via the API.
- AC-7: `GET /route-info` returns a `provider` field consistent with the routing decision and documented in the API contract.
- AC-8: No frontend changes, no DB schema changes, and no new env vars beyond those already present in `.env`.

## Dependency Check
- Upstream (satisfied): `p1-llm-client-abstraction` complete — `LLMClient(Protocol)` exists at `app/backend/clients/base_llm_client.py`
- Downstream (this change blocks): `p1-provider-routing`, `p1-observability-metrics`

## Assumptions
- `config/providers.yml` is a new file under new directory `config/` at repo root.
- Panjit/DeepSeek env vars already exist in `.env`; env-contract must still document them.
- JobStatus `provider` field is additive (new optional field) — backward-compatible.
