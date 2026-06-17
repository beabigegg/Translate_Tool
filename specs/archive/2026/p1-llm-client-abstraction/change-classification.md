---
change-id: p1-llm-client-abstraction
classified: 2026-06-17
---

# Change Classification

## Change Types
- primary: `refactor` (introduce `LLMClient(Protocol)` abstraction, decouple `translation_service.py` from `OllamaClient` internals)
- secondary: `interface-extraction` / `dependency-inversion`

## Risk Level
- medium

Rationale: Pure refactor on the critical translation path. Removing direct private-method calls (`_build_no_system_payload` / `_call_ollama`) risks silent behavior drift if the Protocol surface does not faithfully cover what those calls did. No data/env/API-route change, no new dependency (stdlib only).

## Impact Radius
- module-level — `app/backend/clients/` + `app/backend/services/translation_service.py`

## Tier
- 3

Rationale: medium risk + module-level radius. No contract-artifact change, no migration, no new dependency, no cross-module fan-out. Public `OllamaClient` API frozen; regression suite covers behavior parity.

## Architecture Review Required
- yes
- reason: Introduces a new module-boundary interface (`LLMClient` Protocol) via dependency inversion. The Protocol method set and the repositioning of formerly-private payload logic are non-obvious design decisions that directly shape `p1-cloud-providers`. Getting the abstraction wrong propagates rework into every future provider. `spec-architect` must write `design.md` before `implementation-planner` runs.

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

## Optional Artifacts (default: no — set yes only with explicit reason)
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | Behavior unchanged by design; parity baseline is existing test suite |
| proposal.md | no | No product/user-facing decision; scope fixed by improvement-plan P1-2 |
| spec.md | no | No user-facing behavior spec; interface spec belongs in design.md |
| design.md | yes | Architecture Review Required = yes; spec-architect writes before implementation-planner |
| qa-report.md | no | Prefer agent-log/qa-reviewer.yml; upgrade only if blocking finding appears |
| regression-report.md | no | Record via agent-log pointer; upgrade only if behavior delta discovered |
| visual-review-report.md | no | No UI |
| monkey-test-report.md | no | No UI/interaction surface |
| stress-soak-report.md | no | No load surface; structural refactor only |

## Required Contracts
- API: none — no governed contract modified; contract-reviewer confirms read-only (no route/schema change, no OllamaClient public API breaking change)
- CSS/UI: none
- Env: none
- Data shape: none
- Business logic: none (translation rules unchanged)
- CI/CD: none

Note: `LLMClient` Protocol is an internal code-level contract boundary, NOT one of the 6 governed contract artifacts.

## Required Tests
- unit: yes — Protocol conformance assertion; structural check that translation_service.py has zero calls to private methods
- contract: yes — code-interface conformance (all 6 Protocol methods implemented with compatible signatures)
- integration: yes (light) — translation_service exercising LLMClient through translate_once/translate_batch/refine_translation
- regression: ALL existing translation tests pass unchanged (mandatory)
- E2E: none
- visual: none
- data-boundary: none
- resilience: none
- fuzz/monkey: none
- stress: none
- soak: none

Existing regression suite:
- tests/test_ollama_client_dynamic_strategy.py
- tests/test_translation_strategy.py
- tests/test_hy_mt_quality_refinement.py
- tests/test_translation_profiles_scenarios.py
- tests/test_model_router.py

## Required Agents
1. `spec-architect` — writes design.md: LLMClient Protocol surface (6 methods + signatures), repositioning of private payload logic, parity guarantee, forward-compat for p1-cloud-providers. Must run before implementation-planner.
2. `test-strategist` — writes test-plan.md: Protocol conformance unit/contract tests + regression-parity strategy mapped to AC-1..7.
3. `ci-cd-gatekeeper` — writes ci-gates.md.
4. `implementation-planner` — writes implementation-plan.md after design, test-plan, ci-gates are ready.
5. `backend-engineer` — implements base_llm_client.py, refactors ollama_client.py, rewires translation_service.py (TDD: failing tests first).
6. `contract-reviewer` — read-only: confirms no governed contract touched, OllamaClient public API unchanged.
7. `qa-reviewer` — release-readiness: full regression suite + new tests green; behavior-preserving confirmed.

## Inferred Acceptance Criteria
- AC-1: `app/backend/clients/base_llm_client.py` exists and defines `LLMClient` as a `typing.Protocol` with exactly six methods: `translate_once`, `translate_batch`, `refine_translation`, `health`, `list_models`, `unload`, with signatures compatible with the current `OllamaClient` public API.
- AC-2: `OllamaClient` is declared as `class OllamaClient(LLMClient)` (or is a structural subtype) and a conformance test asserts it satisfies the `LLMClient` Protocol.
- AC-3: `translation_service.py` contains zero direct calls to `_build_no_system_payload` or `_call_ollama` (verifiable by source grep / test).
- AC-4: `OllamaClient`'s public (non-underscore) API is unchanged — no method renamed, removed, or signature-broken.
- AC-5: All existing translation tests pass unchanged with no edits to assertion expectations (regression-free).
- AC-6: No new third-party dependency introduced; only `typing.Protocol` from Python stdlib added.
- AC-7: No governed contract artifact under `contracts/`, no API route/schema, no env var, and no frontend file is modified.

## Tasks Not Applicable
- not-applicable: 2.2, 2.3, 2.4, 2.5, 2.6, 3.3, 3.4, 3.5, 4.2, 4.3, 4.4, 5.1, 5.2

Rationale:
- 2.2 CSS/UI: no frontend; 2.3 Env: no env var; 2.4 Data-shape: no data change; 2.5 Business-rules: behavior unchanged; 2.6 CI/CD: no gate change
- 3.3 E2E/resilience, 3.4 monkey, 3.5 stress/soak: Tier 3, no UI, no load surface
- 4.2 Frontend, 4.3 Env/deploy, 4.4 CI/CD workflows: not in scope
- 5.1 UI/UX review, 5.2 Visual review: no UI

NOT skipped: 1.3 (Architecture Review Required = yes), 2.1 (contract-reviewer confirms no API change)

## Clarifications or Assumptions
- `LLMClient` Protocol is an internal code-level interface, not one of the 6 governed contracts. No contract edit required; contract-reviewer reviews it as a code interface.
- `OllamaClient` currently exposes the six target methods as public or extractable behavior; Protocol formalizes the existing surface.
- CER-001: `ollama_client.py` is inside already-allowed `app/backend/clients/` — approved inline.

## Context Manifest Draft

### Affected Surfaces
- Backend LLM client layer (`app/backend/clients/`)
- Translation service consumer (`app/backend/services/translation_service.py`)

### Allowed Paths
- specs/changes/p1-llm-client-abstraction/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/clients/
- app/backend/services/translation_service.py
- app/backend/utils/exceptions.py
- app/backend/utils/translation_helpers.py
- app/backend/config.py
- tests/test_ollama_client_dynamic_strategy.py
- tests/test_translation_strategy.py
- tests/test_hy_mt_quality_refinement.py
- tests/test_translation_profiles_scenarios.py
- tests/test_model_router.py
- tests/__init__.py
- contracts/

### Agent Work Packets

#### spec-architect
- specs/changes/p1-llm-client-abstraction/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/clients/
- app/backend/services/translation_service.py
- app/backend/utils/exceptions.py

#### test-strategist
- specs/changes/p1-llm-client-abstraction/
- app/backend/clients/
- app/backend/services/translation_service.py
- tests/test_ollama_client_dynamic_strategy.py
- tests/test_translation_strategy.py
- tests/test_hy_mt_quality_refinement.py
- tests/test_translation_profiles_scenarios.py
- tests/test_model_router.py

#### ci-cd-gatekeeper
- specs/changes/p1-llm-client-abstraction/
- contracts/ci/ci-gate-contract.md

#### implementation-planner
- specs/changes/p1-llm-client-abstraction/
- app/backend/clients/
- app/backend/services/translation_service.py

#### backend-engineer
- specs/changes/p1-llm-client-abstraction/
- app/backend/clients/
- app/backend/services/translation_service.py
- app/backend/utils/exceptions.py
- app/backend/utils/translation_helpers.py
- app/backend/config.py
- tests/test_ollama_client_dynamic_strategy.py
- tests/test_translation_strategy.py
- tests/test_hy_mt_quality_refinement.py
- tests/test_translation_profiles_scenarios.py
- tests/test_model_router.py
- tests/__init__.py

#### contract-reviewer
- specs/changes/p1-llm-client-abstraction/
- contracts/
- app/backend/clients/

#### qa-reviewer
- specs/changes/p1-llm-client-abstraction/
- app/backend/clients/
- app/backend/services/translation_service.py
- tests/

### Context Expansion Requests
-

### Approved Expansions
- CER-001: `app/backend/clients/ollama_client.py` — inside already-allowed `app/backend/clients/`; approved inline.
