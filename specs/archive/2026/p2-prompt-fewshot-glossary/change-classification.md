# Change Classification

## Change Types
- primary: business-logic-change, feature-add
- secondary: prompt-change (LLM prompt construction)

## Lane
- feature

## Risk Level
- medium

## Impact Radius
- cross-module

## Tier
- 2

Rationale: Business-logic change to the core translation pipeline with a hard correctness guarantee (glossary terms at 100% match / zero terminology mismatches) and a new control-flow loop (translate-then-critique self-refinement) that adds extra LLM round-trips per request. Impact is cross-module — couples prompt construction (`context_prompts.py`), term/glossary subsystem (`term_db.py`, `term_extractor.py`), translation orchestration (`translation_service.py`, `translation_strategy.py`, `model_router.py`), and the cache/metrics path. Risk is medium: no migration, no schema-breaking change, no auth/payments; failures are contained to translation output quality and per-request latency/cost, not data loss.

## Architecture Review Required
- yes
- reason: The translate-then-critique loop is a non-obvious control-flow / data-flow change to the core translation pipeline (new iteration step, loop-termination policy, cache-key and metrics implications, interaction between glossary-enforcement and the refinement pass). It also forces an operational risk trade-off (extra LLM round-trips vs. quality). These module-boundary / data-flow / operational-risk decisions require `spec-architect` to write `design.md` before `implementation-planner` runs.

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

## Optional Artifacts
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | |
| proposal.md | no | |
| spec.md | no | |
| design.md | yes | Architecture Review Required = yes — loop/data-flow/operational decision |
| qa-report.md | no | use agent-log/qa-reviewer.yml; promote if blocking findings arise |
| regression-report.md | no | use agent-log pointer; promote if critique loop regresses golden translations |
| visual-review-report.md | no | no UI surface |
| monkey-test-report.md | no | |
| stress-soak-report.md | no | |

## Required Contracts
- API: conditional — only if translate response shape/behavior changes (e.g. exposing revision metadata); else read-only reference
- CSS/UI: none
- Env: conditional — only if a critique-loop toggle or max-iterations config var is introduced
- Data shape: conditional — only if glossary/term IR shape or response record gains fields
- Business logic: **required** — add rules: glossary-term 100% match guarantee; critique-loop runs ≥1 per request; loop iteration cap
- CI/CD: none (existing gates apply)

## Required Tests
- unit: tests/test_context_prompt_i18n.py (extend), tests/test_translation_strategy.py, tests/test_term_db.py, tests/test_term_extractor.py
- contract: glossary-match enforcement (new, 100% match); critique-loop invocation (new, ≥1 revision per request)
- integration: tests/test_hy_mt_quality_refinement.py (extend), tests/test_translation_profiles_scenarios.py
- E2E: none
- visual: none
- data-boundary: conditional (only if term/IR shape changes)
- resilience: critique-loop failure/timeout fallback (loop degrades to draft on critique-call failure)
- fuzz/monkey: none
- stress: consideration only — bounded-loop cost; document cap in design.md (not mandated at Tier 2)
- soak: none

## Required Agents
- spec-architect
- implementation-planner
- backend-engineer
- contract-reviewer
- test-strategist
- qa-reviewer

## Inferred Acceptance Criteria
- AC-1: For any translation request whose source contains a glossary-registered term, the corresponding canonical target term appears in the final output for 100% of registered terms present in the source (zero terminology mismatches), measured by an automated glossary-match check.
- AC-2: Few-shot translation examples are injected into the constructed LLM prompt for every translation request, and the injected examples are verifiably present in the prompt sent to the client.
- AC-3: The glossary/domain terms are injected into the LLM prompt (or enforced post-hoc) such that the source-of-truth is `term_db` and not hardcoded examples.
- AC-4: The translate-then-critique loop runs at least once per translation request, producing a revised draft that is distinct from (or explicitly validated equal to) the initial draft, with the revision recorded/metricized.
- AC-5: The critique loop has a bounded maximum iteration count and a per-request cost/timeout cap so it cannot run unboundedly.
- AC-6: The translation cache key incorporates glossary state and refinement so cached results never serve a pre-glossary or pre-critique output, preserving the 100% guarantee on cache hits.
- AC-7: Existing golden-regression translations (`test_golden_regression.py`, `test_hy_mt_quality_refinement.py`) still pass — the new loop does not regress current translation behavior or IR output shape.
- AC-8: Metrics expose at least: critique-loop invocation count, iterations per request, and glossary-match rate, so the 100% guarantee is observable.

## Tasks Not Applicable
- not-applicable: 2.2 (CSS/UI contract — no UI surface), 4.2 (Frontend — no UI change), 4.3 (Env/deploy — no new env vars unless design mandates it), 5.1 (UI/UX review — no UI), 5.2 (Visual review — no visual surface), 3.4 (Data-boundary/monkey — no adversarial input surface), 3.5 (Stress/soak — cost cap documented in design.md, not mandated at Tier 2), 2.6 (CI/CD contract — no new gate type), 6.3 (Informational gates — none), 6.4 (Nightly/weekly/manual gates — none)

## Clarifications or Assumptions
- ASSUMPTION: "100% match rate" is enforced by a deterministic post-translation glossary check (not prompt-only persuasion). Prompt-only best-effort will not reliably achieve 100% — design.md must decide the enforcement mechanism.
- ASSUMPTION: The domain glossary source-of-truth is the existing `term_db.py` subsystem; no new glossary storage/schema is introduced.
- ASSUMPTION: No new endpoint is added; the change alters behavior of the existing translation flow.
- ASSUMPTION: The critique loop's "at least once" lower bound implies a configurable upper bound is acceptable; design.md must define the iteration cap and degrade-to-draft fallback on critique failure.
- OPEN: Whether the loop runs per translatable unit or per request — this materially changes the LLM-call cost multiplier and must be settled by spec-architect.

## Context Manifest Draft

### Affected Surfaces
- LLM prompt construction (few-shot + glossary injection)
- Translation orchestration / self-refinement control flow
- Glossary / term subsystem (read path)
- Translation cache keying
- Metrics / observability for quality
- Business-rules contract (terminology-match guarantee, loop policy)

### Allowed Paths
- specs/changes/p2-prompt-fewshot-glossary/
- specs/context/project-map.md
- specs/context/contracts-index.md
- contracts/business/business-rules.md
- contracts/api/api-contract.md
- contracts/api/api-inventory.md
- contracts/data/data-shape-contract.md
- app/backend/services/context_prompts.py
- app/backend/services/translation_service.py
- app/backend/services/translation_strategy.py
- app/backend/services/term_db.py
- app/backend/services/term_extractor.py
- app/backend/services/model_router.py
- app/backend/services/translation_cache.py
- app/backend/services/job_manager.py
- app/backend/services/metrics.py
- app/backend/clients/base_llm_client.py
- app/backend/clients/ollama_client.py
- app/backend/clients/openai_compatible_client.py
- app/backend/models/term.py
- app/backend/translation_profiles.py
- app/backend/config.py
- tests/test_context_prompt_i18n.py
- tests/test_hy_mt_quality_refinement.py
- tests/test_translation_strategy.py
- tests/test_term_db.py
- tests/test_term_extractor.py
- tests/test_term_api.py
- tests/test_translation_profiles_scenarios.py
- tests/test_golden_regression.py
- tests/test_metrics_counters.py
- tests/test_metrics_endpoint.py
- .github/workflows/contract-driven-gates.yml

### Required Contracts
- contracts/business/business-rules.md (required — add 100% glossary-match guarantee + critique-loop policy)
- contracts/api/api-contract.md (conditional — read-only unless response shape changes)
- contracts/data/data-shape-contract.md (conditional — read-only unless term IR gains fields)

### Required Tests
- tests/test_hy_mt_quality_refinement.py
- tests/test_golden_regression.py
- tests/test_context_prompt_i18n.py
- tests/test_translation_strategy.py

### Agent Work Packets

#### spec-architect
- specs/changes/p2-prompt-fewshot-glossary/
- specs/context/project-map.md
- specs/context/contracts-index.md
- contracts/business/business-rules.md
- contracts/api/api-contract.md
- contracts/data/data-shape-contract.md
- app/backend/services/context_prompts.py
- app/backend/services/translation_service.py
- app/backend/services/translation_strategy.py
- app/backend/services/translation_cache.py
- app/backend/services/model_router.py
- app/backend/services/job_manager.py

#### implementation-planner
- specs/changes/p2-prompt-fewshot-glossary/
- specs/context/project-map.md
- contracts/business/business-rules.md
- app/backend/services/context_prompts.py
- app/backend/services/translation_service.py
- app/backend/services/translation_strategy.py
- app/backend/services/term_db.py
- app/backend/services/metrics.py

#### backend-engineer
- specs/changes/p2-prompt-fewshot-glossary/
- app/backend/services/context_prompts.py
- app/backend/services/translation_service.py
- app/backend/services/translation_strategy.py
- app/backend/services/term_db.py
- app/backend/services/term_extractor.py
- app/backend/services/model_router.py
- app/backend/services/translation_cache.py
- app/backend/services/job_manager.py
- app/backend/services/metrics.py
- app/backend/clients/base_llm_client.py
- app/backend/clients/ollama_client.py
- app/backend/clients/openai_compatible_client.py
- app/backend/models/term.py
- app/backend/translation_profiles.py
- app/backend/config.py

#### test-strategist
- specs/changes/p2-prompt-fewshot-glossary/
- tests/test_context_prompt_i18n.py
- tests/test_hy_mt_quality_refinement.py
- tests/test_translation_strategy.py
- tests/test_term_db.py
- tests/test_term_extractor.py
- tests/test_translation_profiles_scenarios.py
- tests/test_golden_regression.py
- tests/test_metrics_counters.py
- tests/test_metrics_endpoint.py

#### contract-reviewer
- specs/changes/p2-prompt-fewshot-glossary/
- contracts/business/business-rules.md
- contracts/api/api-contract.md
- contracts/api/api-inventory.md
- contracts/data/data-shape-contract.md

#### ci-cd-gatekeeper
- specs/changes/p2-prompt-fewshot-glossary/
- .github/workflows/contract-driven-gates.yml

#### qa-reviewer
- specs/changes/p2-prompt-fewshot-glossary/
- contracts/business/business-rules.md
- tests/test_hy_mt_quality_refinement.py
- tests/test_golden_regression.py

### Context Expansion Requests
- request-id: CER-001
  requested_paths:
    - contracts/business/business-rules.md
  reason: spec-architect and contract-reviewer must read the full file to add/update the 100%-match guarantee and loop policy without duplicating or contradicting existing rules.
  status: approved

- request-id: CER-002
  requested_paths:
    - app/backend/services/translation_cache.py
    - app/backend/services/job_manager.py
  reason: Confirming cache-key and per-request loop-cost handling is required to satisfy AC-5/AC-6; must be inspected by spec-architect/backend-engineer to design the cache-key change and loop bound.
  status: approved
