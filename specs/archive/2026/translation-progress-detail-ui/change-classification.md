# Change Classification

## Change Types
- primary: feature-add (job-status pipeline-detail visibility), api-only-change (additive job-status response shape), ui-only-change (new/enhanced progress display surface)
- secondary: business-logic-change (ETA heuristic recalculation to cover critique+QE phases)

## Lane
- feature

(New capability — real-time pipeline visibility that does not exist today;
not symptom-driven, nothing is broken.)

## Risk Level
- medium

## Impact Radius
- cross-module (backend job-status API + translation-service hot path + frontend polling/progress UI)

## Tier
- 2

## Architecture Review Required
- yes
- reason: The change adds a new response-shape to a public API consumed by existing polling clients (must stay additively backward-compatible), introduces a new UI surface, and has an explicit unresolved design question spanning a module boundary and a hot code path: (a) current-segment-only snapshot vs. a short rolling-history buffer, and (b) the mechanism for the backend to capture and expose "current segment" state (extend JobRecord with an in-memory struct updated in-place vs. a separate lightweight endpoint) under a hard "no heavy overhead on the hot translation path" constraint. spec-architect must write design.md first.

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

## Optional Artifacts (default: no — set yes only with explicit reason)
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | Current behavior already thoroughly documented in change-request.md |
| proposal.md | no | Feature scope is clear; no separate product investigation needed |
| spec.md | no | Behavior fits in design.md + implementation-plan.md |
| design.md | yes | Architecture Review Required = yes; resolves current-only-vs-rolling-history and capture-mechanism open questions and the additive API contract shape |
| qa-report.md | no | Use agent-log/qa-reviewer.yml; promote to prose only if a blocking/approved-with-risk finding lands |
| regression-report.md | no | ETA-behavior regression scope tracked in test-plan + agent-log |
| visual-review-report.md | yes | New user-facing progress surface with live pipeline-stage detail warrants a durable visual evidence bundle |
| monkey-test-report.md | no | Not applicable to a display-only surface |
| stress-soak-report.md | no | The "no heavy hot-path overhead" constraint is verified by a lightweight unit/perf assertion, not a soak run |

Design consistency: design.md = yes AND Architecture Review Required = yes AND spec-architect listed — consistent. Task 1.3 is applicable (not skipped).

Artifact minimization:
- Prefer optional agent-log/*.yml pointers for routine review evidence.
- Create report markdown only for blocking findings, approved-with-risk, visual evidence bundles, or high-risk load/soak results.
- Later artifacts should reference earlier artifacts by path/section/id instead of duplicating full content.

## Required Contracts
- API: yes — additive extension of GET /api/jobs/{id} (and/or a related job-status endpoint) response shape in contracts/api/api-contract.md; regenerate contracts/api/openapi.yml (and openapi.json) in the same change. Must add fields only; no rename/removal of existing job-status fields. .cdd/conformance.json conformance check will fire if a route/call-site drifts from the contract.
- CSS/UI: yes — new progress-detail component styling must conform to contracts/css/css-contract.md and contracts/css/design-tokens.md.
- Env: none
- Data shape: consider — the current-segment snapshot is in-memory (JobRecord), surfaced via API; if contracts/data/data-shape-contract.md documents the job-status data schema, add the fields there too. Otherwise the API contract covers it (spec-architect to confirm).
- Business logic: yes (light) — the improved two-phase ETA heuristic; record the rule in contracts/business/business-rules.md if ETA semantics are contract-governed, else keep as implementation detail per design.md.
- CI/CD: none

## Required Tests
- unit: backend current-segment capture struct + stage transitions; new ETA heuristic math; frontend progress-detail component render + stage-label mapping
- contract: job-status response additive-compatibility (new fields present; existing fields unchanged); backward-compat when fields absent; OpenAPI export freshness
- integration: job-status endpoint returns populated current-segment detail as a job moves through translate → critique → QE → adopt
- E2E: consider — a monitoring flow (job progresses, UI reflects critique/QE phase and non-"done" state); optional, display-only
- visual: yes — new UI surface; UI/UX + visual review required
- data-boundary: yes — frontend and schema must tolerate null/absent current-segment fields (job just started, no critique phase, or older job state) without errors
- resilience: consider — frontend graceful handling when backend omits the new fields or returns partial detail mid-transition
- fuzz/monkey: none
- stress: none
- soak: none (but include one cheap assertion that snapshot capture adds negligible hot-path overhead per the constraint)

## Required Agents

Planning/design (this pass):
- spec-architect — writes design.md; resolves current-only-vs-rolling-history and the capture/expose mechanism; defines the additive API shape
- implementation-planner — turns design + contract + tests into the execution packet; must coordinate ordering/rebase with batch-critique-qe-scoring
- test-strategist — populates Acceptance Criteria → Test mapping and test-plan

Implementation/review (DEFERRED — per change-request "STOP after implementation-plan.md"; listed for the later approved session, NOT commissioned this pass):
- backend-engineer — job_manager/schemas/routes/translation_service changes
- frontend-engineer — progress-detail component + hook + ETA display
- contract-reviewer — API additive-compat + OpenAPI freshness
- ui-ux-reviewer — new UI surface
- visual-reviewer — visual evidence bundle
- qa-reviewer — release readiness / regression scope for the ETA change

## Inferred Acceptance Criteria
- AC-1: GET /api/jobs/{id} (or the related job-status endpoint) additively returns current-segment pipeline detail — current pipeline stage (translate / critique / QE-score / adopt), current source text, draft translation, QE/critique score(s), and adopted result — with no existing job-status field renamed or removed.
- AC-2: Existing job-status consumers (e.g. useJobPolling) continue to function unchanged whether the new fields are present or absent (backward compatible; openapi.yml/openapi.json regenerated and passing the conformance/export-check gate).
- AC-3: The frontend progress display renders the current pipeline stage and the current segment's content detail in real time via the existing polling mechanism, so the user can see at a glance which stage is running and on what content.
- AC-4: When the job has finished the initial translation pass and is in the critique/QE phase, the UI clearly signals ongoing work (not a "555/555 段 = done" appearance).
- AC-5: The remaining-time estimate reflects the full remaining pipeline (translation + critique + QE), not just remaining raw segment count.
- AC-6: Capturing the current-segment snapshot adds negligible overhead to the hot translation path (no expensive synchronous work added solely to populate UI state).
- AC-7: The frontend gracefully handles absence/partial-population of the new fields (job just started, no critique phase configured, mid-transition) without runtime errors.
- AC-8: Design decision on current-only vs. short rolling-history is recorded in design.md with rationale, and the implemented behavior matches that decision.
- AC-9 (added post-planning, scope amendment): `current_stage` and the ETA formula (BR-98 `eta-multi-phase-pipeline`) also cover the judge phase (`JUDGE_ENABLED=true`, `quality_judge.py`) — a stage value `"judge"`, the 3 new optional fields (`current_segment_judge_tier`, `current_segment_judge_attempt`, `current_segment_judge_substep`), and an additive optional snapshot callback on `run_judge_loop` (default `None`, fail-soft — a raising callback must not break the judge loop) make a stuck/slow judge call observable via the existing poll response, instead of the frozen opaque `status_detail` string the original design left in place. ETA phase-3 is omitted when `JUDGE_ENABLED=false` or the winning provider is `deepseek` (BR-97).

## Tasks Not Applicable
<!-- confirmed against the scaffolded tasks.yml by Main Claude -->
- not-applicable: (none — 1.3 is APPLICABLE since design review is required; migration/stress/soak/fuzz-monkey tasks will be marked skipped based on Required Tests above)

## Clarifications or Assumptions
- Assumption: this is display-only visibility; no pipeline-control/override actions (per Non-goals).
- Assumption: the new response fields extend the existing polled job-status payload rather than requiring a websocket/streaming channel; spec-architect confirms endpoint-vs-JobRecord-extension in design.md.
- Open design question (deferred to spec-architect, per change-request): current-segment-only snapshot vs. short rolling-history buffer, and the exact capture/expose mechanism — these are design decisions, not user decisions.
- Overlap/sequencing risk (explicit, do NOT merge scope): batch-critique-qe-scoring restructures the same translation_service.py critique-loop region for performance. That change owns loop behavior/performance; this change owns visibility (a cheap snapshot hook + additive API + UI). Recommended sequencing: land batch-critique-qe-scoring first (or explicitly coordinate), then have this change's implementation-planner design the snapshot hook against the batched round-based loop shape so the "current segment" concept still maps cleanly after batching. Flagged for the planner via CER-002; the two changes must not be collapsed into one.
- Per change-request Constraints: STOP after implementation-plan.md. No edits to app/backend/ or app/frontend/ this pass; implementation agents are listed as deferred.

## Context Manifest Draft
<!-- Classifier fills this section. In /cdd-new Step 2.3, Claude copies it verbatim into
     specs/changes/<change-id>/context-manifest.md, replacing the scaffold.
     All paths must be repo-relative. Gate enforces Allowed Paths against agent files-read logs. -->

### Affected Surfaces
- Backend job-status API surface (api/routes.py, api/schemas.py)
- Backend job lifecycle / state store (services/job_manager.py — JobRecord)
- Backend translation pipeline hot path (services/translation_service.py critique/QE loop; possibly services/translation_strategy.py)
- Frontend job polling + progress display (hooks/, pages/, components/, api/, i18n/)
- Contracts: API, CSS/UI, business (ETA), possibly data-shape

### Allowed Paths
- specs/changes/translation-progress-detail-ui/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/api/routes.py
- app/backend/api/schemas.py
- app/backend/services/job_manager.py
- app/backend/services/translation_service.py
- app/backend/services/translation_strategy.py
- app/backend/config.py
- app/frontend/src/hooks/
- app/frontend/src/pages/
- app/frontend/src/components/
- app/frontend/src/api/
- app/frontend/src/i18n/
- contracts/api/api-contract.md
- contracts/api/openapi.yml
- contracts/api/openapi.json
- contracts/api/api-inventory.md
- contracts/css/css-contract.md
- contracts/css/design-tokens.md
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- tests/test_jobstatus_download_url.py
- tests/contract/
- specs/changes/batch-critique-qe-scoring/change-request.md
- specs/changes/batch-critique-qe-scoring/implementation-plan.md

### Agent Work Packets

#### spec-architect
- specs/changes/translation-progress-detail-ui/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/api/schemas.py
- app/backend/services/job_manager.py
- app/backend/services/translation_service.py
- contracts/api/api-contract.md
- contracts/css/css-contract.md
- contracts/business/business-rules.md
- app/frontend/src/hooks/

#### implementation-planner
- specs/changes/translation-progress-detail-ui/
- app/backend/api/routes.py
- app/backend/api/schemas.py
- app/backend/services/job_manager.py
- app/backend/services/translation_service.py
- app/backend/services/translation_strategy.py
- app/frontend/src/hooks/
- app/frontend/src/pages/
- app/frontend/src/components/
- app/frontend/src/api/
- app/frontend/src/i18n/
- contracts/api/api-contract.md
- contracts/css/css-contract.md
- specs/changes/batch-critique-qe-scoring/change-request.md
- specs/changes/batch-critique-qe-scoring/implementation-plan.md

#### test-strategist
- specs/changes/translation-progress-detail-ui/
- tests/test_jobstatus_download_url.py
- tests/contract/
- app/backend/api/schemas.py
- app/backend/services/job_manager.py

#### backend-engineer (deferred)
- specs/changes/translation-progress-detail-ui/
- app/backend/api/routes.py
- app/backend/api/schemas.py
- app/backend/services/job_manager.py
- app/backend/services/translation_service.py
- app/backend/services/translation_strategy.py
- app/backend/config.py
- contracts/api/api-contract.md
- contracts/api/openapi.yml
- contracts/api/openapi.json
- tests/

#### frontend-engineer (deferred)
- specs/changes/translation-progress-detail-ui/
- app/frontend/src/hooks/
- app/frontend/src/pages/
- app/frontend/src/components/
- app/frontend/src/api/
- app/frontend/src/i18n/
- contracts/css/css-contract.md
- contracts/css/design-tokens.md

#### contract-reviewer / ui-ux-reviewer / visual-reviewer / qa-reviewer (deferred)
- specs/changes/translation-progress-detail-ui/
- contracts/

### Context Expansion Requests
- request-id: CER-001
  requested_paths:
    - app/frontend/src/pages/*
    - app/frontend/src/components/**
    - app/frontend/src/hooks/*
    - app/frontend/src/api/*
    - app/frontend/src/i18n/*
  reason: project-map.md truncates all app/frontend/src/ subdirectories at max depth, so the exact progress-display component, its parent page (TranslatePage), the polling hook file (useJobPolling.js), the jobs API client, and the i18n status-label file cannot be pinned to concrete filenames from the index alone. spec-architect/frontend-engineer need directory enumeration to identify the correct component to enhance.
  status: pending
- request-id: CER-002
  requested_paths:
    - specs/changes/batch-critique-qe-scoring/change-request.md
    - specs/changes/batch-critique-qe-scoring/implementation-plan.md
  reason: Both changes edit the translation_service.py critique-loop region. implementation-planner needs to read the sibling change's planned edits to sequence/rebase and avoid conflicting or duplicated modifications. specs/changes/ is excluded from the project-map index, so this must be an explicit expansion. Coordination read only — do not merge scope.
  status: pending
