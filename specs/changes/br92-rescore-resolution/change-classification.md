# Change Classification

## Change Types
- primary: business-logic-change (BR-92 resolution in `contracts/business/business-rules.md`)
- secondary: env-change (retire path scrubs `QE_RESCORE_THRESHOLD` from env-contract/schema/template), refactor/spec-drift-cleanup (removes phantom rule + tautological test)

## Lane
- feature

Not bug-fix: root cause and code location are already fully identified in the
change-request; this is a deliberate build-vs-retire product/contract
decision, not a symptom-driven investigation with unknown location.

## Risk Level
- medium

## Impact Radius
- cross-module (spans `config.py`, `services/job_manager.py`,
  `services/quality_evaluator.py`, business + env contracts, env
  schema/template, and two test files)

## Tier
- 2

## Architecture Review Required
- yes
- reason: The core "build the real rescore→re-translate hook vs formally
  retire BR-92" is a non-obvious design + operational-risk decision with a
  compatibility/data-flow trade-off (graceful-degradation gate vs contract
  deletion). `spec-architect` must lay out both options' cost/risk in
  `design.md` so the user can make the final build-vs-retire call. The agent
  frames the decision; it does not pick it.

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

Implementation STOPS after `implementation-plan.md` this pass (per
change-request Constraints) — no `backend-engineer`/`bug-fix-engineer` here.

## Optional Artifacts (default: no — set yes only with explicit reason)
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | Phantom/current behavior already fully documented in change-request Original Request |
| proposal.md | no | Build-vs-retire cost/risk lives in design.md; no separate product-investigation doc needed |
| spec.md | no | |
| design.md | yes | spec-architect must present both build and retire options with cost/risk before the user's direction call |
| qa-report.md | no | Plan-only pass; no durable QA evidence yet |
| regression-report.md | no | |
| visual-review-report.md | no | No UI surface |
| monkey-test-report.md | no | |
| stress-soak-report.md | no | |

## Required Contracts
- API: none
- CSS/UI: none
- Env: yes (retire path only) — `QE_RESCORE_THRESHOLD` in `contracts/env/env-contract.md:37-38`, `contracts/env/.env.example.template`, `contracts/env/env.schema.json`
- Data shape: none
- Business logic: yes — BR-92 in `contracts/business/business-rules.md:104` (delete on retire, or make real + fix "verified-by" on build)
- CI/CD: none

## Required Tests
- unit: yes — replace the tautological `test_below_threshold_triggers_retranslation` with real routing behavior (build) OR delete it and its verified-by reference (retire)
- contract: yes — `tests/test_env_contract.py` assertions for `QE_RESCORE_THRESHOLD` presence must match final state; business-rules verified-by consistency
- integration: conditional (build path only) — post-translate hook: below-threshold segment triggers an actual re-translation pass with graceful degradation
- E2E: no
- visual: no
- data-boundary: no
- resilience: conditional (build path only) — QE failure/unreachable must NOT flip job to `status: failed` (mirror BR-56/BR-61)
- fuzz/monkey: no
- stress: no
- soak: no

## Required Agents
- spec-architect — write `design.md` laying out build-vs-retire cost/risk (does not choose direction)
- contract-reviewer — review business-rules + env-contract/schema/template consistency for both directions
- test-strategist — `test-plan.md`: real coverage for build, or clean deletion of tautological test + verified-by for retire
- implementation-planner — turn the confirmed direction into `implementation-plan.md` (terminal agent this pass)
- qa-reviewer — release-readiness / sync-completeness check (no artifact left claiming behavior that doesn't exist)

Explicitly NOT this pass: `backend-engineer`, `bug-fix-engineer`.

## Inferred Acceptance Criteria
- AC-1: A build-vs-retire decision for BR-92 is explicitly framed for and confirmed by the user before `implementation-plan.md` is treated as final; `design.md` presents both options' cost/risk without the agent picking the direction.
- AC-2: After resolution, no artifact claims rescore behavior that isn't implemented — `contracts/business/business-rules.md`, `config.py`, `contracts/env/env-contract.md`, `env.schema.json`, `.env.example.template`, and both test files are mutually consistent.
- AC-3: The tautological `test_below_threshold_triggers_retranslation` is either replaced with a real behavior-routing test (build) or deleted with its BR-92 "verified-by" reference removed (retire) — no dangling verified-by remains.
- AC-4: Retire path — BR-92 removed from `business-rules.md`, `QE_RESCORE_THRESHOLD` removed from `config.py:133-136`, and rescore claims scrubbed from `env-contract.md:37-38` plus every artifact asserted in `test_env_contract.py:174-205`.
- AC-5: Build path — the rescore→re-translate hook reuses established graceful-degradation patterns (no `status: failed` solely for QE failure, mirroring BR-56/BR-61) and gains real, non-tautological test coverage.
- AC-6: The change is complete and coherent in whichever direction — no partial fix leaving contract/config/tests/env-contract out of sync.
- AC-7: Non-goals honored — in-line critique loop (BR-89/90), LLM-judge gate (BR-72-77), BR-55/56 dashboard COMET scoring, and sibling changes' scope are unmodified.

## Tasks Not Applicable
- not-applicable: 1.4, 2.2, 2.6, 3.5, 4.2, 4.4, 5.1, 5.2

(2.2 CSS/UI + 2.6 CI/CD contract: no UI/pipeline contract change. 3.5
stress/soak: not required. 4.2 Frontend + 4.4 CI/CD workflows: no FE or
workflow change. 5.1 UI/UX + 5.2 Visual review: no UI surface. Task 1.3
REMAINS applicable — design review required. All 4.x/5.4/6.x/7.x implementation-
stage tasks are deferred by the STOP-after-plan constraint, not skipped.)

## Clarifications or Assumptions
- Lane is `feature`, not `bug-fix`: root cause and every affected path are
  already pinpointed; the resolution is a deliberate product/contract
  decision, not a symptom-driven diagnosis.
- Env contract is listed as required because the retire path touches
  `env-contract.md`/`env.schema.json`/`.env.example.template`; if the user
  chooses build, the env contract may instead be updated (activating the
  flag's documented meaning) rather than deleted, but is in scope either way.
- **Decision point for the user (surfaced, not resolved here)**: build the
  real rescore→re-translate gate, or formally retire BR-92. `spec-architect`
  will quantify each in `design.md` before this is decided.
