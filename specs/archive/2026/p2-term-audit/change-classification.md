---
change-id: p2-term-audit
schema-version: 1
---

# Change Classification

## Change Types
- primary: `feature-add` (backend audit module), `business-logic-change` (new BR for terminology hit-rate audit)
- secondary: `data-shape-change` (new `terminology_audit` field in job-level qa-report structure)

## Risk Level
- medium

## Impact Radius
- module-level

## Tier
- 2

Rationale: Backend-only new module, no frontend, no CSS/UI, no DB migration, no new HTTP endpoint. Introduces a new business rule (terminology hit-rate audit) and a new field on the existing qa-report/data shape, and wires into the post-translate path — cross-cutting within the backend domain but isolated from external surfaces. Tier 2 (not 3) because `rejected` 0-injection is a safety-relevant business invariant.

## Architecture Review Required
- yes
- reason: Two design decisions must be settled before implementation: (1) the hit-rate matching algorithm (exact vs lemmatized, multi-target-language morphology strictness — the only Open Question in the request), and (2) the data-flow seam — where in the post-translate path `term_audit` runs and how its result is written into the existing qa-report structure without creating a parallel report format.

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

## Optional Artifacts (default: no — set yes only with explicit reason)
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | No existing audit behavior; the capability is entirely absent today. |
| proposal.md | no | Scope settled in change-request. |
| spec.md | no | Behavior fits in design.md + implementation-plan.md. |
| design.md | yes | Architecture Review Required = yes: matching algorithm + post-translate seam + qa-report integration decisions. |
| qa-report.md | no | Audit evidence fits in agent-log/qa-reviewer.yml. |
| regression-report.md | no | Additive module; no existing behavior changed. |
| visual-review-report.md | no | No UI surface. |
| monkey-test-report.md | no | No interactive surface. |
| stress-soak-report.md | no | Single-pass per-job audit; not a high-load path. |

## Required Contracts
- API: none — no new endpoint; result written to job-level audit field, not an HTTP route. api-contract.md unchanged.
- CSS/UI: none
- Env: none — no new env var or secret
- Data shape: `contracts/data/data-shape-contract.md` — add `terminology_audit` field schema; bump 0.7.0 → 0.8.0
- Business logic: `contracts/business/business-rules.md` — add BR for terminology hit-rate audit; bump 0.11.0 → 0.12.0
- CI/CD: none — no new gate command needed

## Required Tests
- unit: yes — matcher correctness (case-insensitive exact, optional lemmatized), hit-rate computation, unapplied-term collection, rejected-injection detection; selection assertions (assert WHICH terms counted as hit/miss, not just count)
- contract: yes — audit output conforms to new `terminology_audit` data-shape; writes into existing qa-report structure (no parallel format)
- integration: yes — audit runs at the real post-translate seam (the hook, not a higher-level wrapper); end-to-end on a 20-approved-term fixture
- E2E: no
- visual: no
- data-boundary: yes — empty term set, zero approved terms, multi-target-language document
- resilience: no
- fuzz/monkey: no
- stress: no
- soak: no

## Required Agents
1. `spec-architect` — write design.md (must run first; Architecture Review Required = yes)
2. `contract-reviewer` — author/review business-rules and data-shape contract bumps; confirm no api-contract change
3. `test-strategist` — author test plan; guard tautological/wrong-entry-point patterns
4. `ci-cd-gatekeeper` — write ci-gates.md; apply tier-floor-override if "integration" vocab misfires
5. `implementation-planner` — execution packet after design + contracts + test plan + CI gate plan ready
6. `backend-engineer` — implement `app/backend/services/term_audit.py` and wire post-translate hook
7. `qa-reviewer` — release-readiness decision (always last)

## Inferred Acceptance Criteria
- AC-1: For a test document containing 20 `approved` terms, the audit produces a `terminology_hit_rate` report (report is producible end-to-end at the post-translate seam).
- AC-2: On that 20-approved-term fixture, the reported hit rate is ≥ 95%.
- AC-3: The audit reports `rejected` term injection count = 0 when no rejected term appears in output; a rejected injection is detected and reported as a violation when present in a negative fixture.
- AC-4: The matching algorithm correctly handles case differences and word-form/morphology variation — implemented as case-insensitive exact match plus an optional configurable lemmatized match (no heavy NLP runtime dependency required for the default path).
- AC-5: The audit result is written into the existing `qa-report` / job-audit structure; no new parallel report format is created (contract-verified against `data-shape-contract.md`).
- AC-6: No new HTTP API endpoint is added; `api-contract.md` is unchanged and the conformance/api gate reports no drift.
- AC-7: The audit scope is restricted to `approved` terms only (`unverified`, `needs_review`, `rejected` excluded from hit-rate denominator), consistent with the P1 term state machine.
- AC-8: An unapplied-terms list (each `approved` term not found in output) is produced and included in the audit report.

## Tasks Not Applicable
- not-applicable: 2.1 (API contract — no new endpoint), 2.2 (CSS/UI — no UI surface), 2.3 (Env — no new env var/secret), 2.6 (CI/CD contract — no new gate), 3.3 (E2E — no user-facing flow), 3.4 (monkey — no interactive surface), 3.5 (stress/soak — single-pass per-job), 4.2 (frontend — no frontend), 4.3 (Env/deploy — no env config change), 5.1 (UI/UX — no UI), 5.2 (visual — no UI), 6.3 (informational gates — none), 6.4 (nightly/weekly/manual — none)

## Clarifications or Assumptions
- **Open Question resolved**: Case-insensitive exact match as default; optional configurable lemmatized match. No heavy NLP runtime dependency on default path. spec-architect specifies lemmatization library/strategy in `design.md`.
- **Assumption**: "qa-report" target = existing job-level audit data structure in `data-shape-contract.md`, not a separate file artifact named `qa-report.md`.
- **Assumption**: Post-translate seam = `post_translate_hook` pattern from `quality_evaluator.py` (COMET QE). `term_audit` attaches at the same seam.
- **Tier Floor Override flag**: Change-request contains "integration" vocab — `cdd-kit gate` tier-floor may misfire. Apply `tier-floor-override: 2` in `ci-gates.md` if triggered. Rationale: "integration" refers only to in-process hook wiring and integration-level tests, not cross-system/external integration, migration, or auth.

## Context Manifest Draft

### Affected Surfaces
- Backend terminology audit (new `services/term_audit.py`)
- Post-translate orchestration seam (post_translate_hook pattern)
- Job-level qa-report / audit data shape
- Business rules: terminology hit-rate audit

### Allowed Paths
- specs/changes/p2-term-audit/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/services/term_audit.py
- app/backend/services/term_db.py
- app/backend/models/term.py
- app/backend/services/job_manager.py
- app/backend/services/translation_service.py
- app/backend/services/quality_evaluator.py
- app/backend/processors/orchestrator.py
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- tests/test_term_audit.py
- tests/test_term_db.py
- tests/test_term_state_machine.py
- tests/test_term_api.py
- tests/test_quality_evaluation.py
- tests/test_translation_strategy.py

### Agent Work Packets

#### spec-architect
- specs/changes/p2-term-audit/
- app/backend/services/quality_evaluator.py
- app/backend/services/translation_service.py
- app/backend/processors/orchestrator.py
- app/backend/services/term_db.py
- app/backend/models/term.py
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md

#### contract-reviewer
- specs/changes/p2-term-audit/
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- specs/context/contracts-index.md

#### test-strategist
- specs/changes/p2-term-audit/
- tests/test_term_audit.py
- tests/test_term_db.py
- tests/test_quality_evaluation.py
- app/backend/services/term_audit.py
- app/backend/services/term_db.py
- app/backend/models/term.py

#### ci-cd-gatekeeper
- specs/changes/p2-term-audit/
- .github/workflows/contract-driven-gates.yml
- contracts/ci/ci-gate-contract.md

#### implementation-planner
- specs/changes/p2-term-audit/
- app/backend/services/term_db.py
- app/backend/models/term.py
- app/backend/services/quality_evaluator.py
- app/backend/processors/orchestrator.py

#### backend-engineer
- specs/changes/p2-term-audit/
- app/backend/services/term_audit.py
- app/backend/services/term_db.py
- app/backend/models/term.py
- app/backend/services/translation_service.py
- app/backend/services/quality_evaluator.py
- app/backend/processors/orchestrator.py
- tests/test_term_audit.py
- tests/test_quality_evaluation.py
- tests/test_term_db.py

#### qa-reviewer
- specs/changes/p2-term-audit/
- tests/test_term_audit.py
- app/backend/services/term_audit.py
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
