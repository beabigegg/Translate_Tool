# Change Classification

## Change Types
- primary: `ui-redesign`, `feature-add` (new backend endpoints)
- secondary: `api-only-change`, `env-policy-change` (secret-handling policy: DeepSeek key client-side only), `business-logic-change` (provider-test orchestration)

## Lane
- feature

## Risk Level
- medium

## Impact Radius
- cross-module

## Tier
- 2

(tier-floor-override applied — see Clarifications/Assumptions for written rationale.)

## Architecture Review Required
- yes
- reason: Three design decisions are non-obvious and have operational/security risk: (1) the secret-handling pattern — DeepSeek API key supplied via UI, stored only in localStorage, transmitted per-request to backend and NEVER persisted to backend .env; (2) the request shape and conservatism for POST /api/providers/test-translation (parallel asyncio.gather vs sequential, cost-guarding the paid DeepSeek path while PANJIT is free, synchronous response vs job_id/BackgroundTasks); (3) how provider health/model data flows from providers.yml and the COMET QE_ENABLED gate.

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

## Optional Artifacts (default: no — set yes only with explicit reason)
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | Existing Ollama-specific SettingsPage is removed wholesale; scope captured in design.md + implementation-plan.md. |
| proposal.md | no | Feature scope already decided in change-request. |
| spec.md | no | Endpoint/UI behavior specified in change-request; design.md + api-contract are the durable spec. |
| design.md | yes | Architecture Review Required = yes (secret-handling pattern, test-translation orchestration, module-boundary data flow). |
| qa-report.md | no | Routine pass/fail recorded in agent-log unless blocking/approved-with-risk finding arises. |
| regression-report.md | no | No existing-behavior change beyond removing dead Ollama UI. |
| visual-review-report.md | yes | Full page redesign — durable visual evidence bundle warranted. |
| monkey-test-report.md | no | Not high-fuzz surface; form interactions covered by unit/E2E. |
| stress-soak-report.md | no | test-translation is single-sentence synchronous; no high-load risk. |

## Required Contracts
- API: yes — add GET /api/providers/health, GET /api/providers/models, POST /api/providers/test-translation to contracts/api/api-contract.md; export openapi.
- CSS/UI: yes — record new component styling against contracts/css/css-contract.md and design-tokens.md.
- Env: yes (policy-only) — env-contract.md Secret Policy must document DeepSeek key is user-supplied client-stored, NOT a backend env var.
- Data shape: yes — define response shapes for the 3 endpoints in contracts/data/data-shape-contract.md.
- Business logic: yes — provider-test orchestration rule (parallel fan-out, cost-conservatism, COMET gate) in contracts/business/business-rules.md.
- CI/CD: no — no new gate; existing cdd-kit gate + openapi --check cover it.

## Required Tests
- unit: SettingsPage component (status indicators, model list render, DeepSeek key save/clear/disabled state, VRAM removal); backend handlers for 3 endpoints; system.js API client functions.
- contract: response-sample tests for 3 endpoints against api-contract + openapi.
- integration: test-translation endpoint e2e (parallel calls, COMET path, DeepSeek key per-request).
- E2E: settings flow — health status, enter+save DeepSeek key to localStorage, run single-sentence test.
- visual: redesigned page states.
- data-boundary: test-translation with malformed/missing fields, provider error responses.
- resilience: provider offline/timeout, DeepSeek 401 on bad key, partial fan-out failure.
- fuzz/monkey: none
- stress: none
- soak: none

## Required Agents
(execution order)
1. `spec-architect` — write design.md
2. Main Claude — write contract updates (API, data-shape, business, CSS, env)
3. `implementation-planner` — produce implementation-plan.md
4. `backend-engineer` — implement 3 endpoints, provider health/model logic, test-translation + COMET
5. `frontend-engineer` — rewrite SettingsPage, remove VramCalculator/VRAM/num_ctx UI
6. `test-strategist` — write test-plan.md, unit/contract/integration/E2E/data-boundary/resilience tests
7. `e2e-resilience-engineer` — E2E + resilience tests
8. `contract-reviewer` — verify all contract conformance
9. `ui-ux-reviewer` — interaction/copy/accessibility
10. `visual-reviewer` — produce visual-review-report.md
11. `qa-reviewer` — release readiness, dead-reference check
12. `ci-cd-gatekeeper` — finalize ci-gates.md

## Inferred Acceptance Criteria
- AC-1: SettingsPage no longer renders GPU VRAM selection, num_ctx slider, or VramCalculator; no orphaned import of VramCalculator.jsx remains.
- AC-2: Page displays PANJIT and DeepSeek health status (online/offline + latency); DeepSeek shows "not configured" when no key in localStorage.
- AC-3: GET /api/providers/health returns each provider's status and latency; GET /api/providers/models returns each provider's model list from providers.yml.
- AC-4: DeepSeek API key is entered via type="password" field, saved to localStorage key `deepseek_api_key`, clearable, NEVER auto-populated from backend .env, NEVER persisted to backend env; backend receives key per-request only.
- AC-5: When no DeepSeek key is set, DeepSeek model options and test are disabled in the UI.
- AC-6: POST /api/providers/test-translation accepts {text, src_lang, targets, profile, models[]}, runs models in parallel, returns results[] of {model_id, translation, duration_ms, comet_score}; COMET score is omitted when QE_ENABLED=false.
- AC-7: DeepSeek (paid) test path is cost-conservative — not invoked without a valid key; missing/invalid key yields a clean error without crashing other model results in the fan-out.
- AC-8: Three new endpoints conform to api-contract.md/openapi.yml (openapi --check passes) and response shapes match data-shape-contract.md.

## Tasks Not Applicable
- not-applicable: 3.5 (stress/soak tests — single-sentence synchronous endpoint, no load risk)

## Clarifications or Assumptions
- **Tier-floor-override rationale:** Change-request contains "api key", "endpoint", "integration" vocabulary. None reflects the high-risk pattern those tokens usually guard: (a) the "api key" is a user-supplied DeepSeek key held in client localStorage, explicitly NEVER written to backend env — not an auth-system change; (b) the 3 endpoints are additive read/test endpoints with no breaking change, no migration, no DDL; (c) "integration" is ordinary frontend↔backend wiring. Genuine risk is the secret-in-localStorage trade-off, addressed by design.md + env Secret Policy. Net actual risk = medium / cross-module → Tier 2, overriding any auto floor.
- Assumption: test-translation is synchronous (no job_id, no BackgroundTasks) — spec-architect to confirm in design.md.
- Assumption: PANJIT model list sourced from config/providers.yml; spec-architect decides if live /v1/models call is preferred.
- Dependencies (fallback-chain-cloud-providers, term-extraction-db-first) are confirmed archived/complete.
