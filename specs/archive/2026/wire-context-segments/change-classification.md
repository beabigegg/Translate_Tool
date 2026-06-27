# Change Classification: wire-context-segments

## Change Types
- primary: business-logic-change (translation prompt behavior), feature-enhancement (wire orphaned config)
- secondary: config-wiring (dead-constant activation in `config.py`)

## Risk Level
- medium

## Impact Radius
- module-level (backend translation service layer; multiple files but no cross-surface/API/DB/frontend reach)

## Tier
- 2

Rationale: default `CONTEXT_WINDOW_SEGMENTS=2` means this changes the prompt content of every translation by default (not opt-in), spanning three coordinated call sites (batching → prompt builder → orchestration). No endpoint, schema, env var, or migration involved.

## Architecture Review Required
- no
- reason: The seam already exists — constants are defined with clear intent at `config.py:104-105` and the prompt builder/batcher are existing call sites. No new module boundary, data-flow redesign, migration, or compatibility trade-off. `CONTEXT_WINDOW_SEGMENTS=0` preserves the existing path.

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

## Optional Artifacts (default: no — set yes only with explicit reason)
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | Current behavior (no context prefix) is one sentence; captured in test-plan |
| proposal.md | no | No product/user-facing decision to investigate; behavior is already specified |
| spec.md | no | Not needed |
| design.md | no | No architecture review required |
| qa-report.md | no | Use agent-log pointer unless QA finds blocking/approved-with-risk issues |
| regression-report.md | no | Use agent-log pointer unless regression found |
| visual-review-report.md | no | No UI surface |
| monkey-test-report.md | no | Not applicable |
| stress-soak-report.md | no | Bounded by CONTEXT_MAX_CHARS=300; no new load behavior |

## Required Contracts
- API: none (no endpoints added/changed)
- CSS/UI: none
- Env: none (constants remain Python-level in config.py, not env-driven)
- Data shape: none
- Business logic: contracts/business/business-rules.md — context-window prompt behavior (neighbor count, char cap, "do not translate" prefix, =0 disable) must be recorded with a BR id
- CI/CD: none

## Required Tests
- unit: prompt builder injects up to CONTEXT_WINDOW_SEGMENTS neighbors as "Context (do not translate):" prefix; total truncated at CONTEXT_MAX_CHARS; =0 yields byte-identical prompt to current behavior; first/last segment boundary cases
- contract: business-rule assertion for context-window behavior; verify constants are no longer dead references
- integration: translation_service batch path passes neighbor context through to ollama_client prompt builder (assert prefix reaches real prompt string, not a wrapper — avoid call-wiring tautology)
- E2E: none
- visual: none
- data-boundary: none
- resilience: none
- fuzz/monkey: none
- stress: none
- soak: none

## Required Agents
- contract-reviewer
- test-strategist
- implementation-planner
- backend-engineer
- qa-reviewer

## Inferred Acceptance Criteria
- AC-1: With CONTEXT_WINDOW_SEGMENTS=2, each segment's translation prompt includes up to 2 adjacent neighbor segments rendered under a "Context (do not translate):" prefix.
- AC-2: The combined context prefix never exceeds CONTEXT_MAX_CHARS=300 total characters; when neighbors would exceed it, the context is truncated to the cap.
- AC-3: With CONTEXT_WINDOW_SEGMENTS=0, prompts contain no context prefix and are byte-identical to current behavior (backward compatibility proven by test).
- AC-4: Only the target segment is translated/returned; context-prefixed neighbor text is never itself translated or emitted into output.
- AC-5: Segments at document boundaries (first/last, or batches shorter than the window) include only available neighbors and raise no error.
- AC-6: The wiring removes the dead-reference status of CONTEXT_WINDOW_SEGMENTS and CONTEXT_MAX_CHARS (verified via tests/test_dead_references.py).

## Tasks Not Applicable
- not-applicable: 1.3, 2.1, 2.2, 2.3, 2.4, 2.6, 3.3, 3.4, 3.5, 4.2, 4.3, 5.1, 5.2

## Clarifications or Assumptions
- CONTEXT_WINDOW_SEGMENTS / CONTEXT_MAX_CHARS remain Python constants (not env vars). If promoted to env-driven, env-contract + .env.example update required.
- Default ships as CONTEXT_WINDOW_SEGMENTS=2 (behavior changes by default for all translations).
- Path correction: translation_helpers.py lives at app/backend/utils/translation_helpers.py (not services/), per project-map.
- There is a dedicated app/backend/services/context_prompts.py that may be the real home of the "Context (do not translate):" prefix logic; backend-engineer must inspect it.

## Context Manifest Draft

### Affected Surfaces
- backend translation pipeline (prompt construction + batch orchestration)

### Allowed Paths
- specs/changes/wire-context-segments/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/config.py
- app/backend/utils/translation_helpers.py
- app/backend/clients/ollama_client.py
- app/backend/services/translation_service.py
- app/backend/services/context_prompts.py
- contracts/business/business-rules.md
- tests/test_ollama_client_dynamic_strategy.py
- tests/test_context_prompt_i18n.py
- tests/test_dead_references.py

### Agent Work Packets

#### contract-reviewer
- specs/changes/wire-context-segments/
- contracts/business/business-rules.md
- app/backend/config.py

#### test-strategist
- specs/changes/wire-context-segments/
- tests/test_ollama_client_dynamic_strategy.py
- tests/test_context_prompt_i18n.py
- tests/test_dead_references.py
- app/backend/utils/translation_helpers.py
- app/backend/clients/ollama_client.py
- app/backend/services/translation_service.py
- app/backend/services/context_prompts.py
- app/backend/config.py

#### implementation-planner
- specs/changes/wire-context-segments/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/config.py
- app/backend/utils/translation_helpers.py
- app/backend/clients/ollama_client.py
- app/backend/services/translation_service.py
- app/backend/services/context_prompts.py
- contracts/business/business-rules.md

#### backend-engineer
- specs/changes/wire-context-segments/
- app/backend/config.py
- app/backend/utils/translation_helpers.py
- app/backend/clients/ollama_client.py
- app/backend/services/translation_service.py
- app/backend/services/context_prompts.py
- contracts/business/business-rules.md
- tests/test_ollama_client_dynamic_strategy.py
- tests/test_context_prompt_i18n.py
- tests/test_dead_references.py

#### qa-reviewer
- specs/changes/wire-context-segments/
- tests/test_dead_references.py
