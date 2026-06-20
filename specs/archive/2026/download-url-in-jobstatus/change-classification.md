# Change Classification

## Change Types
- primary: bug-fix, api-only-change
- secondary: business-logic-change (download_url derivation rule on completion)

## Lane
- bug-fix

## Bug Symptom Type
- api

## Diagnostic Only
- no

## Risk Level
- low

## Impact Radius
- module-level

## Tier
- 3

## Architecture Review Required
- no

## Required Artifacts

Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

| artifact | create? |
|---|---|
| design.md | no |
| qa-report.md | no |
| visual-review-report.md | no |

## Required Contracts
- API: yes — `contracts/api/api-contract.md` add `download_url: Optional[str]` to JobStatus response schema; regenerate openapi.yml
- CSS/UI: no
- Env: no
- Data shape: no
- Business logic: optional — derivation rule captured in AC
- CI/CD: no

## Required Tests
- unit: job_manager sets `download_url = f"/api/jobs/{job_id}/download"` exactly when completed + output_zip present; None otherwise
- contract: JobStatus response includes download_url per api-contract / openapi
- integration: run job to completion; GET /jobs/{job_id} payload carries correct download_url

## Required Agents
1. `contract-reviewer` — update api-contract.md + openapi.yml before implementation
2. `test-strategist` — define unit/contract/integration coverage
3. `ci-cd-gatekeeper` — ci-gates.md
4. `implementation-planner` — execution packet
5. `bug-fix-engineer` — reproduce, fix schemas.py + job_manager.py, add regression test
6. `qa-reviewer` — release readiness

## Inferred Acceptance Criteria
- AC-1: JobStatus in schemas.py declares `download_url: Optional[str] = None`
- AC-2: When status == "completed" and output_zip is set, job_manager populates `download_url = f"/api/jobs/{job_id}/download"`
- AC-3: When not completed or output_zip absent, download_url is None
- AC-4: GET /jobs/{job_id} for a completed job returns correct download_url; frontend download button renders
- AC-5: No existing JobStatus field is changed or dropped
- AC-6: contracts/api/api-contract.md documents new field; openapi.yml regenerated and in sync
- AC-7: Download endpoint at routes.py:339-350 is unchanged

## Tasks Not Applicable
- 1.3 (no design.md / architecture review)
- 2.2 (CSS/UI contract — no UI change)
- 2.3 (Env contract — no env change)
- 2.4 (Data shape contract — API response field only)
- 2.6 (CI/CD contract — no gate change)
- 3.3 (E2E/resilience — not required)
- 3.4 (data-boundary/monkey — not required)
- 3.5 (stress/soak — not required)
- 4.2 (Frontend — TranslatePage.jsx already correct, no change needed)
- 4.3 (Env/deploy — no env change)
- 5.1 (UI/UX review — no UI change)
- 5.2 (Visual review — no UI change)
