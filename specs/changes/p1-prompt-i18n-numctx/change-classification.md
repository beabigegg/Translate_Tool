# Change Classification

## Change Types
- primary: feature-enhancement (context-detection prompt i18n), env-change (NUM_CTX split)
- secondary: business-logic-change (prompt-template selection by target_lang)

## Lane
- feature

## Bug Symptom Type
- n/a (feature lane)

## Diagnostic Only
- no

## Bug Evidence
- n/a (feature lane)

## Risk Level
- medium

## Impact Radius
- module-level

## Tier
- 3

## Architecture Review Required
- no
- reason: No new module boundary, no data-flow restructure; both changes are localized template selection and env-var fallback wiring within existing functions. Existing signatures and triggers are non-goals.

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

## Optional Artifacts (default: no — set yes only with explicit reason)

| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | Current behavior captured in change-request Known Context with exact file:line pointers |
| proposal.md | no | No product/UX decision open; behavior target is explicit |
| spec.md | no | No user-facing spec needed |
| design.md | no | No architecture review required |
| qa-report.md | no | Routine pass/fail fits agent-log/qa-reviewer.yml |
| regression-report.md | no | Backward-compat preserved; 396-test baseline recordable as agent-log pointer |
| visual-review-report.md | no | No UI surface |
| monkey-test-report.md | no | No interactive surface |
| stress-soak-report.md | no | No load/queue/long-job change |

## Required Contracts
- API: none
- CSS/UI: none
- Env: `contracts/env/env-contract.md` — **update**. Add `GENERAL_NUM_CTX` and `TRANSLATION_NUM_CTX` to env inventory with fallback chain; update `.env.example.template` and `env.schema.json`; document `OLLAMA_NUM_CTX` as backward-compat fallback.
- Data shape: none (`StrategyDecision` / `build_strategy` unchanged — non-goal)
- Business logic: `contracts/business/business-rules.md` — **review only**. Update only if a rule already documents the context-detection prompt language; otherwise capture in implementation-plan only.
- CI/CD: none

## Required Tests
- unit: yes — prompt-template selection returns correct template for en / zh-TW / ja and falls back to en for unlisted language (e.g. ko); covers both immediate path (orchestrator._detect_document_context) and deferred path (translation_service deferred context); NUM_CTX resolution: GENERAL/TRANSLATION env override wins; absent → OLLAMA_NUM_CTX; absent → defaults 4096/3072; backward-compat (only OLLAMA_NUM_CTX set) preserved.
- contract: env-contract conformance via `cdd-kit validate` against env.schema.json
- integration: deferred context path with `_ctx_target` set produces correct localized prompt; 396-test baseline passes
- E2E: none
- visual: none
- data-boundary: none
- resilience: none
- fuzz/monkey: none
- stress: none
- soak: none

## Required Agents
- implementation-planner
- backend-engineer
- test-strategist
- contract-reviewer
- qa-reviewer

## Inferred Acceptance Criteria
- AC-1: For `target_lang` in {en, zh-TW, ja}, the context-detection prompt sent to the LLM uses the matching localized template (not the hardcoded zh-TW string).
- AC-2: For a `target_lang` not in the supported set (e.g. ko, fr), the context-detection prompt falls back to the English (`en`) template.
- AC-3: Both the immediate path (`orchestrator._detect_document_context`) and the deferred path (`translation_service` deferred context) use the same localized template selection.
- AC-4: `GENERAL_NUM_CTX` env var, when set, overrides the general-model context window independently of `TRANSLATION_NUM_CTX`.
- AC-5: `TRANSLATION_NUM_CTX` env var, when set, overrides the translation-model context window independently of `GENERAL_NUM_CTX`.
- AC-6: When a specific NUM_CTX var is unset, the value falls back to `OLLAMA_NUM_CTX`; when both are unset, it falls back to defaults (4096 general / 3072 translation).
- AC-7: An existing deployment that sets only `OLLAMA_NUM_CTX` continues to produce the same effective context-window values (backward compatibility preserved).
- AC-8: `contracts/env/env-contract.md`, `.env.example.template`, and `env.schema.json` document the two new vars and the fallback chain; `cdd-kit validate` passes.

## Tasks Not Applicable
- not-applicable: 1.3, 2.1, 2.2, 2.4, 2.6, 3.3, 3.4, 3.5, 4.2, 4.3, 5.1, 5.2

## Clarifications or Assumptions
- Locale matching: exact match, then fallback to en (no fuzzy/region collapsing). `zh-CN` and other zh variants default to `en` unless explicitly listed.
- Prompt templates live in a new backend module or inline constant (implementation-plan decision); no public API change.
- Defaults: GENERAL=4096, TRANSLATION=3072 (unchanged from current Python constants).
- Non-secret integer tuning vars; no tier-floor override expected, but apply one with written rationale if `cdd-kit gate` false-positives on "config"/"endpoint" vocab.

## Context Manifest Draft

### Affected Surfaces
- LLM context-detection prompt generation (backend processors/services)
- Runtime config: Ollama context-window env vars
- Env contract + env schema + .env example

### Allowed Paths
- specs/changes/p1-prompt-i18n-numctx/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/config.py
- app/backend/processors/orchestrator.py
- app/backend/services/translation_service.py
- app/backend/__init__.py
- contracts/env/env-contract.md
- contracts/env/.env.example.template
- contracts/env/env.schema.json
- contracts/business/business-rules.md
- tests/test_translation_strategy.py
- tests/

### Agent Work Packets

#### implementation-planner
- specs/changes/p1-prompt-i18n-numctx/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/config.py
- app/backend/processors/orchestrator.py
- app/backend/services/translation_service.py
- contracts/env/env-contract.md

#### backend-engineer
- specs/changes/p1-prompt-i18n-numctx/
- app/backend/config.py
- app/backend/processors/orchestrator.py
- app/backend/services/translation_service.py
- app/backend/__init__.py
- contracts/env/env-contract.md
- contracts/env/.env.example.template
- contracts/env/env.schema.json

#### test-strategist
- specs/changes/p1-prompt-i18n-numctx/
- app/backend/config.py
- app/backend/processors/orchestrator.py
- app/backend/services/translation_service.py
- tests/

#### contract-reviewer
- specs/changes/p1-prompt-i18n-numctx/
- contracts/env/env-contract.md
- contracts/env/.env.example.template
- contracts/env/env.schema.json
- contracts/business/business-rules.md

#### qa-reviewer
- specs/changes/p1-prompt-i18n-numctx/
- tests/

### Context Expansion Requests
- request-id: CER-001
  requested_paths:
    - app/backend/clients/ollama_client.py
    - app/backend/clients/base_llm_client.py
  reason: If num_ctx resolution is consumed by the Ollama client downstream of config.py, backend-engineer may need to read the client to confirm per-type value is wired correctly.
  status: pending
