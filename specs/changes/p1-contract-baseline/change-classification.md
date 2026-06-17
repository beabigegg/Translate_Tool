# Change Classification

## Change Types
- primary: contract-baseline / documentation-only (contracts/*.md backfill to reflect existing behavior)
- secondary: api-contract-change, data-shape-contract-change, business-logic-documentation (no behavior change — recording current behavior only)

## Lane
- feature

## Risk Level
- low

## Impact Radius
- module-level

The change only edits Markdown contract files under `contracts/api/`, `contracts/business/`, and `contracts/data/`. No runtime code, schema, or frontend is touched. The only operational effect is enabling `cdd-kit validate --contracts` to function as a baseline for downstream changes. Risk is bounded: an inaccurate contract is caught by the conformance gate, not by production behavior.

## Tier
- 4

## Architecture Review Required
- no

## Required Artifacts

The following 7 artifacts are always required:
`change-request.md`, `change-classification.md`, `implementation-plan.md`, `test-plan.md`, `ci-gates.md`, `tasks.yml`, `context-manifest.md`

## Optional Artifacts

| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | The "current behavior" IS the contract content itself; a separate doc would duplicate it. |
| proposal.md | no | No product decision — request is to document existing behavior. |
| spec.md | no | No new behavior to specify. |
| design.md | no | No architecture/module-boundary decision. (Task 1.3 N/A.) |
| qa-report.md | no | No code change to QA; gate pass evidence fits in agent-log YAML pointer. |
| regression-report.md | no | No behavior change, so no regression surface. |
| visual-review-report.md | no | No UI surface touched. |
| monkey-test-report.md | no | No interactive surface. |
| stress-soak-report.md | no | No load/long-running surface. |

## Required Contracts
- API: yes — `contracts/api/api-contract.md` (endpoint inventory, auth policy), `contracts/api/api-inventory.md` (real endpoint list), `contracts/api/error-format.md` (HTTP status codes + error payload shape)
- CSS/UI: none (non-goal)
- Env: none (explicit non-goal — handled by p1-cloud-providers)
- Data shape: yes — `contracts/data/data-shape-contract.md` (`JobStatus.status` enum, multipart request schema)
- Business logic: yes — `contracts/business/business-rules.md` (rule inventory + decision table)
- CI/CD: none

## Required Tests
- unit: none
- contract: `cdd-kit validate --contracts` must pass; conformance check (`.cdd/conformance.json`) verifies api-contract.md against real routes/call sites
- integration: none
- E2E: none
- visual: none
- data-boundary: none
- resilience: none
- fuzz/monkey: none
- stress: none
- soak: none

## Required Agents
- implementation-planner — turn the change-request + source files into an execution packet mapping each contract section to source-of-truth code
- contract-reviewer — verify each filled contract accurately reflects current code and that `cdd-kit validate --contracts` passes
- qa-reviewer — release-readiness confirmation: gate-ready, downstream-blocker precondition satisfied

Not required: `backend-engineer`, `frontend-engineer` (no code written), `spec-architect` (no design decision), `test-strategist` (no new test code; only existing conformance gate runs)

## Context Manifest Draft

### Affected Surfaces
- api (contracts/api/*)
- data (contracts/data/data-shape-contract.md)
- domain-behavior (contracts/business/business-rules.md)

### Allowed Paths
- specs/changes/p1-contract-baseline/
- specs/context/project-map.md
- specs/context/contracts-index.md
- contracts/api/api-contract.md
- contracts/api/api-inventory.md
- contracts/api/error-format.md
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- app/backend/api/routes.py
- app/backend/api/schemas.py
- app/backend/services/job_manager.py
- app/backend/utils/exceptions.py
- docs/improvement-plan.md
- .cdd/conformance.json

### Agent Work Packets

#### implementation-planner
- specs/changes/p1-contract-baseline/
- specs/context/project-map.md
- docs/improvement-plan.md
- app/backend/api/routes.py
- app/backend/api/schemas.py
- app/backend/services/job_manager.py
- app/backend/utils/exceptions.py
- contracts/api/api-contract.md
- contracts/api/api-inventory.md
- contracts/api/error-format.md
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md

#### contract-reviewer
- specs/changes/p1-contract-baseline/
- contracts/api/api-contract.md
- contracts/api/api-inventory.md
- contracts/api/error-format.md
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- app/backend/api/routes.py
- app/backend/api/schemas.py
- app/backend/services/job_manager.py
- app/backend/utils/exceptions.py
- .cdd/conformance.json

#### qa-reviewer
- specs/changes/p1-contract-baseline/
- contracts/api/api-contract.md
- contracts/api/api-inventory.md
- contracts/api/error-format.md
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md

### Context Expansion Requests
- none at classification time

## Inferred Acceptance Criteria
- AC-1: `contracts/api/api-inventory.md` lists every API endpoint actually defined in `app/backend/api/routes.py` (method + path), with no invented endpoints and no implemented endpoint omitted.
- AC-2: `contracts/api/api-contract.md` records the auth policy: "API has no authentication; this is an intentional local-tool design decision."
- AC-3: `contracts/data/data-shape-contract.md` documents the `JobStatus.status` enum with values that exactly match those in `app/backend/api/routes.py` and `app/backend/services/job_manager.py`.
- AC-4: `contracts/api/error-format.md` documents the error payload shape and HTTP status codes actually returned by `app/backend/utils/exceptions.py` and `app/backend/api/routes.py`.
- AC-5: `contracts/data/data-shape-contract.md` documents the multipart upload request schema (fields, types, required/optional) per `app/backend/api/schemas.py` / `routes.py`.
- AC-6: `contracts/business/business-rules.md` contains a non-empty rule inventory and at least one decision table reflecting implemented behavior.
- AC-7: `cdd-kit validate --contracts` passes with zero drift after contracts are filled.
- AC-8: No file outside `contracts/api/`, `contracts/business/`, `contracts/data/` is modified.

## Tasks Not Applicable
- 1.3: design review — no architecture decision
- 2.2: CSS/UI contract — no UI surface
- 4.1: Backend implementation — no code written
- 4.2: Frontend implementation — no code written
- 4.3: Env/deploy — env contract is non-goal (handled by p1-cloud-providers)
- 4.4: CI/CD workflows — no gate-definition change
- 5.1: UI/UX review — no UI surface
- 5.2: Visual review — no UI surface

## Clarifications / Assumptions
- Contract authoring is a documentation activity reflecting read-only source; no implementation-engineer agent required.
- The four named source files cover the complete current API/behavior surface for this change.
- `.cdd/conformance.json` is assumed `"enabled": true`; contract-reviewer must confirm.
