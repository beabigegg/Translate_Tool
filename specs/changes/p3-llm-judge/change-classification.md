# Change Classification: p3-llm-judge

## Change Type
- primary: `feature-add` (new LLM-as-judge quality review service)
- secondary: `api-only-change` (new endpoint), `ui-only-change` (job detail display), `business-logic-change` (re-translation loop rule), `data-shape-change` (new fields on job record), `env-change` (feature flag + Gemma model config)

## Lane
- feature

## Tier
- 2

Rationale: medium risk, cross-module impact (new service layer + orchestrator hook + job record + API + UI). Not Tier 0/1 because it is feature-flagged, optional, falls back cleanly if Gemma is unavailable, and touches no auth/payments/migration. Classified upward to Tier 2 due to cross-module radius and the runaway-iteration / latency risk on the main translation pipeline.

## Risk Factors
- Re-translation loop (up to 3 iterations) adds latency and LLM cost on every job — runaway-cost guardrail required (max-iteration cap is the mitigation; must be tested).
- New service runs on the post-translation critical path; a judge failure must NOT fail the translation job (graceful degradation required).
- Second Ollama model (Gemma) concurrent with translation model — VRAM / model-load contention risk on local hardware.
- New data shape on job record (`JobRecord`) — must follow data-shape-contract compatibility rules and not break existing `GET /jobs/{id}` consumers.
- New API endpoint — `endpoint` tier-floor keyword trigger (see tier-floor-override).
- Interaction with existing `CRITIQUE_LOOP_ENABLED` flag and COMET QE post_translate_hook — must coexist, not collide.
- All-formats scope (DOCX/PPTX/XLSX/PDF) — judge wiring must reach all processors (orphaned-wiring risk per CLAUDE.md learnings).

## Architecture Review Required
- yes
- reason: Introduces new service layer (Gemma judge service), new data shape on job record, new API endpoint, and new behavioral control loop (re-translation iteration with feedback) on the core pipeline. Module-boundary, hook-point, iteration-state, and graceful-degradation decisions must be settled in design.md before planning.

## Tier-Floor-Override
- override: true
- rationale: `endpoint` / `integration` / `cache`-vocab triggers fire but represent: (1) a routine read-only feature endpoint mirroring the existing `/quality` pattern; (2) an existing local Ollama integration path, no new external dependency; (3) no cache introduced. There is no DDL migration, no auth surface, no secret beyond a local-model name. Genuine risks captured at Tier 2.

## Optional Artifacts

| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | No existing judge behavior is being changed |
| proposal.md | no | All product decisions confirmed by user |
| spec.md | no | Behavior fully specified in change-request + design.md |
| design.md | yes | Architecture Review Required: yes — new service layer, data shape, control loop |
| qa-report.md | no | Escalate only if blocking findings or approved-with-risk |
| regression-report.md | no | Judge is additive and feature-flagged |
| visual-review-report.md | no | Log in agent-log/visual-reviewer.yml |
| monkey-test-report.md | no | Tier 2 |
| stress-soak-report.md | no | Tier 2 |

## Required Agents
1. `spec-architect` — design.md (service boundary, judge hook point, iteration-state, data-shape, graceful-degradation decisions)
2. `contract-reviewer` — update API, data, business, env, CSS contracts
3. `test-strategist` — test-plan.md
4. `ci-cd-gatekeeper` — ci-gates.md
5. `implementation-planner` — implementation-plan.md
6. `backend-engineer` — judge service, orchestrator hook, iteration loop, job-record fields, new endpoint
7. `frontend-engineer` — job detail judge panel (score + source + translated + feedback)
8. `ui-ux-reviewer` — judge panel interaction/copy/accessibility
9. `visual-reviewer` — panel rendering confirmation (log-only)
10. `qa-reviewer` — release readiness, graceful-degradation, wiring across all 4 formats

## Tasks Not Applicable
- not-applicable: 3.3, 3.4, 3.5, 4.3, 6.3, 6.4

## Inferred Acceptance Criteria
- AC-1: When the judge feature flag is enabled and Gemma is available, a completed translation job has judge results (score ∈ {低,中,高}, source text, translated text, feedback, attempt count) recorded on its job record.
- AC-2: When the judge score is 中 or 低, the translation model is re-invoked with the judge feedback; when the score is 高, no re-translation occurs.
- AC-3: Re-translation stops after at most 3 attempts even if the score never reaches 高; the final result and attempt count are recorded.
- AC-4: When the judge feature flag is disabled, OR Gemma is unavailable, the translation job completes normally with no judge pass and no error surfaced to the user.
- AC-5: A new GET /api/jobs/{id}/judge endpoint returns judge results conforming to contracts/api/api-contract.md and the data-shape contract; a new POST /api/jobs/{id}/judge/apply endpoint triggers re-render; OpenAPI export is current.
- AC-6: The frontend job detail page displays the judge score, source text, translated text, and judge feedback when judge results exist, and renders cleanly when they do not.
- AC-7: The judge applies to all four document formats (DOCX/PPTX/XLSX/PDF) — the judge hook is wired into every processor path (verified by grep of call sites, not just unit mocks).
- AC-8: The judge coexists with existing COMET QE and the CRITIQUE_LOOP_ENABLED path without altering their behavior when the judge flag is off.
- AC-9: When re-translation produces a result, the frontend shows a confirmation dialog with the re-translated text; if the user confirms, a POST /api/jobs/{id}/judge/apply request is sent.
- AC-10: POST /api/jobs/{id}/judge/apply re-renders the document with the re-translated text and overwrites the job's output file; the endpoint returns an updated download URL.

## Clarifications or Assumptions
- Contract-heavy atomic-split trigger fired (5 of 6 contracts), but surfaces are dependent vertical slices of one shippable feature. Proceeded as single Tier 2 change.
- Judge re-translation loop reuses existing translation_service.py / model_router.py (not a parallel engine). design.md must confirm exact hook point vs post_translate_hook and CRITIQUE_LOOP_ENABLED.
- New endpoint is read-only (GET), mirroring existing GET /api/jobs/{id}/quality COMET pattern.
- Gemma model name is a config/env value, not hardcoded. No new API key/secret (local Ollama model).

## Context Manifest Draft

### Affected Surfaces
- Backend service layer: app/backend/services/ (new quality_judge.py)
- Pipeline orchestration: app/backend/processors/orchestrator.py (judge hook + re-translation loop)
- Job lifecycle / data shape: app/backend/services/job_manager.py, app/backend/api/schemas.py
- Translation invocation: app/backend/services/translation_service.py, app/backend/services/model_router.py
- LLM client: app/backend/clients/ollama_client.py
- API: app/backend/api/routes.py, app/backend/api/schemas.py (new endpoint)
- Config: app/backend/config.py (judge feature flag, Gemma model name)
- Frontend: app/frontend/src/pages/TranslatePage.jsx (job detail), app/frontend/src/api/jobs.js
- Contracts: api, data, business, env, css

### Allowed Paths
- specs/changes/p3-llm-judge/
- specs/context/project-map.md
- specs/context/contracts-index.md
- contracts/api/api-contract.md
- contracts/api/api-inventory.md
- contracts/api/openapi.yml
- contracts/api/openapi.json
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md
- contracts/env/env-contract.md
- contracts/env/.env.example.template
- contracts/env/env.schema.json
- contracts/css/css-contract.md
- app/backend/services/
- app/backend/processors/orchestrator.py
- app/backend/clients/ollama_client.py
- app/backend/clients/base_llm_client.py
- app/backend/api/routes.py
- app/backend/api/schemas.py
- app/backend/config.py
- app/backend/models/translatable_document.py
- app/frontend/src/pages/TranslatePage.jsx
- app/frontend/src/pages/HistoryPage.jsx
- app/frontend/src/api/jobs.js
- app/frontend/src/api/client.js
- app/frontend/src/components/
- app/frontend/src/contexts/
- app/frontend/src/hooks/
- tests/
- .github/workflows/contract-driven-gates.yml

### Agent Work Packets

#### spec-architect
- specs/changes/p3-llm-judge/
- specs/context/project-map.md
- specs/context/contracts-index.md
- contracts/api/api-contract.md
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md
- contracts/env/env-contract.md
- app/backend/processors/orchestrator.py
- app/backend/services/
- app/backend/clients/ollama_client.py
- app/backend/clients/base_llm_client.py
- app/backend/config.py
- app/backend/api/schemas.py

#### contract-reviewer
- specs/changes/p3-llm-judge/
- contracts/api/
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md
- contracts/env/
- contracts/css/css-contract.md
- app/backend/api/routes.py
- app/backend/api/schemas.py

#### test-strategist
- specs/changes/p3-llm-judge/
- contracts/
- tests/

#### ci-cd-gatekeeper
- specs/changes/p3-llm-judge/
- contracts/
- .github/workflows/contract-driven-gates.yml

#### implementation-planner
- specs/changes/p3-llm-judge/
- contracts/
- app/backend/
- app/frontend/src/

#### backend-engineer
- specs/changes/p3-llm-judge/
- contracts/api/
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md
- contracts/env/
- app/backend/services/
- app/backend/processors/orchestrator.py
- app/backend/clients/
- app/backend/api/routes.py
- app/backend/api/schemas.py
- app/backend/config.py
- app/backend/models/translatable_document.py
- tests/

#### frontend-engineer
- specs/changes/p3-llm-judge/
- contracts/api/api-contract.md
- contracts/css/css-contract.md
- app/frontend/src/pages/TranslatePage.jsx
- app/frontend/src/pages/HistoryPage.jsx
- app/frontend/src/api/jobs.js
- app/frontend/src/api/client.js
- app/frontend/src/components/
- app/frontend/src/hooks/

#### ui-ux-reviewer / visual-reviewer
- specs/changes/p3-llm-judge/
- contracts/css/css-contract.md
- app/frontend/src/pages/TranslatePage.jsx
- app/frontend/src/components/

#### qa-reviewer
- specs/changes/p3-llm-judge/
- contracts/
- app/backend/
- tests/

### Context Expansion Requests
- (none — CER-001 and CER-002 resolved: exact frontend filenames confirmed via ls; backend service files already in Allowed Paths)
