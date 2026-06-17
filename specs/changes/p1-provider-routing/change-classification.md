# Change Classification

## Change Types
- primary: `feature-enhancement` (config-driven routing), `business-logic-change` (per-target-language routing behavior)
- secondary: `refactor` (extract hardcoded `_OLLAMA_ROUTING_TABLE` to config)

## Lane
- feature

## Risk Level
- medium

## Impact Radius
- module-level (services/model_router.py routing logic; consumed by the translation dispatch path)

## Tier
- 2

## Architecture Review Required
- no
- reason: The config-driven provider/routing architecture is already decided in `docs/adr/0001-config-driven-provider-registry.md` and implemented by the completed `p1-cloud-providers` change (providers.yml, `load_providers_config()`). This change applies that settled pattern to the routing table and fixes per-language dispatch. No new module boundary, data-flow, migration, or compatibility decision.

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

## Optional Artifacts (default: no — set yes only with explicit reason)

| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | Current behavior (hardcoded dict + `targets[0]` routing) is small and fully captured in the implementation plan and AC list. |
| proposal.md | no | No product/user-facing behavior decision to resolve; scope is fixed and technical. |
| spec.md | no | Behavior defined by providers.yml `routing:` section and business-rules contract. |
| design.md | no | Architecture review not required (pattern already decided by p1-cloud-providers / ADR-0001). |
| qa-report.md | no | Routine pass/fail; record in `agent-log/qa-reviewer.yml`. |
| regression-report.md | no | Existing-behavior change; evidence fits in `agent-log/qa-reviewer.yml`. Promote to yes only if blocking. |
| visual-review-report.md | no | No UI surface. |
| monkey-test-report.md | no | Not applicable. |
| stress-soak-report.md | no | Not high-load/long-running. |

## Required Contracts
- API: none
- CSS/UI: none
- Env: none
- Data shape: none
- Business logic: `contracts/business/business-rules.md` — record that routing rules are now sourced from `config/providers.yml` `routing:` section, and that mixed-language batches route each `target_lang` independently (no longer keyed on `targets[0]`).
- CI/CD: none

## Required Tests
- unit: yes — `tests/test_model_router.py`: routing table loaded from providers.yml `routing:`; `resolve_route_groups()` resolves each target_lang independently; mixed-language batch `[vi, de, ko, ja]` produces correct per-language model groups; fallback/default behavior preserved.
- contract: yes — assert routing resolution matches rules declared in `config/providers.yml` (config is source of truth, not a hardcoded dict).
- integration: light — verify translation dispatch consumers of `resolve_route_groups()` still group correctly.
- E2E: none
- visual: none
- data-boundary: none
- resilience: none
- fuzz/monkey: none
- stress: none
- soak: none

## Required Agents
- `contract-reviewer` — verify business-rules contract reflects new routing source and per-language dispatch.
- `test-strategist` — map ACs to test file/families; ensure per-language and config-driven cases plus regression are covered.
- `implementation-planner` — turn scoped behaviors + contract delta into the execution packet.
- `backend-engineer` — implement config-driven routing read and per-target-language resolution in `model_router.py`.
- `qa-reviewer` — release readiness; confirm all existing tests pass and new routing tests pass.

## Inferred Acceptance Criteria
- AC-1: `model_router.py` no longer contains a hardcoded `_OLLAMA_ROUTING_TABLE` dict as the routing source; routing rules are read from the `routing:` section of `config/providers.yml`.
- AC-2: Adding or changing a routing rule (language → model) requires only editing `config/providers.yml` with no Python code change, and the new rule takes effect.
- AC-3: `resolve_route_groups()` resolves each `target_lang` in a batch independently rather than routing the whole batch by `targets[0]`.
- AC-4: A mixed-language batch `[vi, de, ko, ja]` dispatches each language to the model defined for it in `config/providers.yml` (each language can land in a different route group).
- AC-5: A language not present in the providers.yml `routing:` section falls back to the existing default routing behavior (no crash, deterministic default).
- AC-6: All pre-existing `tests/test_model_router.py` tests pass unchanged in intent (existing routing behavior preserved), and new per-language + config-driven routing tests pass.
- AC-7: The business-rules contract documents that routing is config-sourced from `config/providers.yml` and that batches route per target language.

## Tasks Not Applicable
- not-applicable: 1.3, 2.1, 2.2, 2.3, 2.4, 2.6, 3.3, 3.4, 3.5, 4.2, 4.3, 4.4, 5.1, 5.2

## Risk Factors
- Existing-behavior change in the translation dispatch hot path: per-language grouping alters which model handles each language in mixed batches — regression risk on previously-working single-language and default-fallback flows.
- Source-of-truth swap: if `config/providers.yml` `routing:` is incomplete relative to the old hardcoded dict, some languages could silently lose their mapping. Mitigation: AC-5 default-fallback test + verifying providers.yml covers all previously-hardcoded languages.
- Grouping-shape contract: `resolve_route_groups()` return shape is consumed downstream; per-language grouping must not break the consumer's expected grouping structure.

## Clarifications or Assumptions
- Assumption: The `routing:` section already exists in `config/providers.yml` (delivered by `p1-cloud-providers`). If it does not exist in a consumable shape, this becomes partly a config-schema addition — flag via CER-001 and report `blocked`.
- Assumption: No env, secret, or runtime-config change (providers.yml is application config, not an env var or secret).
- Dependency: p1-cloud-providers must be completed/archived before this change gates. Status: DONE (archived to specs/archive/2026/p1-cloud-providers/).

## Context Manifest Draft

### Affected Surfaces
- Backend routing: `app/backend/services/model_router.py` (routing table + `resolve_route_groups()`)
- Provider config: `config/providers.yml` (`routing:` section as source of truth)
- Business behavior contract: routing rule semantics

### Allowed Paths
- specs/changes/p1-provider-routing/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/services/model_router.py
- config/providers.yml
- config/providers.yml.example
- contracts/business/business-rules.md
- tests/test_model_router.py
- docs/adr/0001-config-driven-provider-registry.md

### Agent Work Packets

#### change-classifier
- specs/changes/p1-provider-routing/
- specs/context/project-map.md
- specs/context/contracts-index.md

#### contract-reviewer
- specs/changes/p1-provider-routing/
- contracts/business/business-rules.md
- config/providers.yml

#### test-strategist
- specs/changes/p1-provider-routing/
- tests/test_model_router.py
- app/backend/services/model_router.py
- config/providers.yml

#### implementation-planner
- specs/changes/p1-provider-routing/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/services/model_router.py
- config/providers.yml
- contracts/business/business-rules.md
- docs/adr/0001-config-driven-provider-registry.md

#### backend-engineer
- specs/changes/p1-provider-routing/
- app/backend/services/model_router.py
- config/providers.yml
- config/providers.yml.example
- tests/test_model_router.py
- contracts/business/business-rules.md

#### qa-reviewer
- specs/changes/p1-provider-routing/
- tests/test_model_router.py
- contracts/business/business-rules.md

### Context Expansion Requests
- request-id: CER-001
  requested_paths:
    - app/backend/processors/orchestrator.py
    - app/backend/services/translation_service.py
  reason: If implementation-planner or backend-engineer finds the consumer signature/grouping contract is ambiguous, read-only access to the immediate callers of `resolve_route_groups()` may be needed to confirm the per-language grouping shape is consumed correctly.
  status: pending
