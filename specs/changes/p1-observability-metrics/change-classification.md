# Change Classification

## Change Types
- primary: feature-add (new `GET /api/metrics` endpoint)
- secondary: business-logic-change (new in-process counter module + counter increments at existing call sites)

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
- reason: Additive endpoint plus a small in-process counter module. No module-boundary redesign, no data-flow change, no migration/rollback, no operational trade-off. Counter increments are additive instrumentation hooks at existing call sites.

## Required Artifacts

Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

## Optional Artifacts (default: no — set yes only with explicit reason)

| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | Net-new endpoint; no existing behavior changed beyond additive increment hooks. |
| proposal.md | no | Scope fully specified in change-request. |
| spec.md | no | No user-facing behavior decision beyond documented success criterion. |
| design.md | no | Architecture review not required. |
| qa-report.md | no | Routine pass/fail in agent-log/qa-reviewer.yml unless blocking findings arise. |
| regression-report.md | no | Change is additive. |
| visual-review-report.md | no | No UI/visual surface. |
| monkey-test-report.md | no | No interactive UI surface. |
| stress-soak-report.md | no | In-process counters, no external store, no load introduced. |

## Required Contracts
- API: contracts/api/api-contract.md (new `GET /api/metrics` endpoint: method, path, response shape, status codes, no-auth note); contracts/api/api-inventory.md (register new endpoint); contracts/api/openapi.yml (regenerate via `cdd-kit openapi export` after api-contract edit)
- CSS/UI: none
- Env: none
- Data shape: none (counter response is an API contract concern, not a persisted data contract)
- Business logic: contracts/business/business-rules.md (counter semantics: what increments translation_count, latency mean computation, provider failure attribution, font cache hit/miss accounting, in-memory-only lifetime)
- CI/CD: none (existing gates apply; no new pipeline gate)

## Required Tests
- unit: counter module — increment/aggregate logic, latency mean computation, hit/miss accounting, reset/initial-state behavior
- contract: `GET /api/metrics` returns HTTP 200 with JSON body containing at least `translation_count`, `translation_latency_mean_ms`, `provider_failure_count`, `font_cache_hits`, `font_cache_misses`; field presence/type assertions
- integration: counters update after a translation call (latency + count) and after a font buffer load (hit/miss), reflected in endpoint response
- E2E: not applicable
- visual: not applicable
- data-boundary: not applicable
- resilience: not applicable
- fuzz/monkey: not applicable
- stress: not applicable
- soak: not applicable

## Required Agents
- contract-reviewer
- test-strategist
- ci-cd-gatekeeper
- implementation-planner
- backend-engineer
- qa-reviewer

## Inferred Acceptance Criteria
- AC-1: `GET /api/metrics` returns HTTP 200 with a JSON response body.
- AC-2: The response body contains at least the keys `translation_count`, `translation_latency_mean_ms`, `provider_failure_count`, `font_cache_hits`, `font_cache_misses`.
- AC-3: After each translation call, `translation_count` increments and `translation_latency_mean_ms` reflects the updated mean latency for the resolved model.
- AC-4: When a provider call fails, `provider_failure_count` increments; on success the provider call count increments without incrementing failure count.
- AC-5: A font buffer cache hit increments `font_cache_hits` and a miss increments `font_cache_misses`.
- AC-6: Counters are in-process memory only — no external store is read or written; counters initialize to zero at process start.
- AC-7: The endpoint and instrumentation are additive — existing translation and font-load behavior is unchanged except for counter side effects (existing tests still pass).

## Tasks Not Applicable
- not-applicable: 1.3, 2.2, 2.3, 2.4, 2.6, 3.3, 3.4, 3.5, 4.2, 4.3, 5.1, 5.2

## Clarifications or Assumptions
- The metrics endpoint is intentionally unauthenticated; document this in api-contract so the no-auth decision is contract-recorded, not an oversight.
- Counter module is a new file under app/backend/services/ (e.g. metrics.py); exact filename chosen by backend-engineer.
- `provider_failure_count` and per-model latency are exposed as flat keys; the five named keys are the minimum.
- After editing api-contract.md, run `cdd-kit openapi export --out contracts/api/openapi.yml` and commit — CI gate fails if openapi.yml is stale (see CLAUDE.md learnings).

## Context Manifest Draft

### Affected Surfaces
- backend API (new `GET /api/metrics` endpoint in app/backend/api/routes.py)
- backend services / instrumentation (new counter module; increment hooks in translation and font-load call sites)

### Allowed Paths
- specs/changes/p1-observability-metrics/
- specs/context/project-map.md
- specs/context/contracts-index.md
- contracts/api/api-contract.md
- contracts/api/api-inventory.md
- contracts/api/error-format.md
- contracts/api/openapi.yml
- contracts/business/business-rules.md
- app/backend/api/routes.py
- app/backend/api/schemas.py
- app/backend/services/model_router.py
- app/backend/services/translation_service.py
- app/backend/renderers/pdf_generator.py
- app/backend/services/
- tests/
- .github/workflows/contract-driven-gates.yml
- ci/

### Agent Work Packets

#### change-classifier
- specs/changes/p1-observability-metrics/
- specs/context/project-map.md
- specs/context/contracts-index.md

#### contract-reviewer
- specs/changes/p1-observability-metrics/
- contracts/api/api-contract.md
- contracts/api/api-inventory.md
- contracts/api/error-format.md
- contracts/api/openapi.yml
- contracts/business/business-rules.md

#### test-strategist
- specs/changes/p1-observability-metrics/
- contracts/api/api-contract.md
- contracts/business/business-rules.md
- tests/

#### implementation-planner
- specs/changes/p1-observability-metrics/
- contracts/api/api-contract.md
- contracts/business/business-rules.md

#### backend-engineer
- specs/changes/p1-observability-metrics/
- contracts/api/api-contract.md
- contracts/business/business-rules.md
- app/backend/api/routes.py
- app/backend/api/schemas.py
- app/backend/services/model_router.py
- app/backend/services/translation_service.py
- app/backend/renderers/pdf_generator.py
- app/backend/services/
- tests/

#### ci-cd-gatekeeper
- specs/changes/p1-observability-metrics/
- contracts/api/openapi.yml
- .github/workflows/contract-driven-gates.yml
- ci/

#### qa-reviewer
- specs/changes/p1-observability-metrics/
- contracts/api/api-contract.md
- tests/
