# Change Classification

## Change Types
- primary: feature-enhancement, api-only-change
- secondary: data-shape-change (job-result `warnings` field)

## Risk Level
- medium

## Impact Radius
- module-level (backend `api/schemas.py` + `processors/pdf_processor.py` + API/data contracts; no frontend, no cross-module data flow change)

## Tier
- 3

Rationale: Additive, backward-compatible optional field (`warnings: None/[]` when no degradation) on one existing endpoint (`GET /api/jobs/{id}`). No auth, payments, production migration, or queue concurrency. Standard feature enhancement → Tier 3.

## Architecture Review Required
- no

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

## Optional Artifacts (default: no — set yes only with explicit reason)
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | additive field; existing behavior unchanged |
| proposal.md | no | scope is unambiguous in the change-request |
| spec.md | no | no separate product/behavior investigation needed |
| design.md | no | no architecture review required |
| qa-report.md | no | use `agent-log/qa-reviewer.yml` unless blocking finding |
| regression-report.md | no | additive optional field, low regression surface |
| visual-review-report.md | no | no UI change |
| monkey-test-report.md | no | not applicable |
| stress-soak-report.md | no | not a load/soak surface |

## Required Contracts
- API: `contracts/api/api-contract.md` (add `warnings: list[str]` to `GET /api/jobs/{id}` job-result schema) + regenerate `contracts/api/openapi.yml` / `contracts/api/openapi.json`
- CSS/UI: none
- Env: none
- Data shape: `contracts/data/data-shape-contract.md` (if job-result shape is defined there)
- Business logic: none
- CI/CD: none (existing openapi-check gate already covers it)

## Required Tests
- unit: fitz-fallback path (mock fitz raise at call site, assert exact warning string); PDF→DOCX routing trap path (assert layout-skip warning); no-degradation case (warnings is None/[])
- contract: `GET /api/jobs/{id}` response includes `warnings` and is optional/backward-compatible
- integration: warning propagates from processor → job result → API response
- E2E: none
- visual: none
- data-boundary: `warnings` is always `list[str]` or `None`, never bare string or other type
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
- AC-1: When fitz PDF renderer raises and code falls back to ReportLab, `GET /api/jobs/{id}` job result `warnings` contains "PDF rendering quality reduced: fell back to basic renderer — images and formatting may be lost"
- AC-2: When PDF is routed through bilingual DOCX conversion (`output_format != "pdf"`), `warnings` contains "Layout preservation skipped: PDF was converted to bilingual DOCX mode — use output_format=pdf for layout-faithful output"
- AC-3: When no degradation occurs, `warnings` is `None` or `[]`; existing API consumers unaffected (backward-compatible)
- AC-4: `warnings` is always `list[str]` or `None` — never a bare string or other type
- AC-5: `contracts/api/api-contract.md` documents the `warnings` field; regenerated `openapi.yml`/`openapi.json` match (CI openapi-check gate passes)
- AC-6: The fitz-fallback test mocks failure at the real call site and asserts on the actual job-result/API path (non-tautological)

## Tasks Not Applicable
- not-applicable: 1.3, 2.2, 2.3, 2.5, 2.6, 3.3, 3.4, 3.5, 4.2, 4.3, 5.1, 5.2

## Clarifications or Assumptions
- `warnings` is additive and optional; existing clients ignore the new key — backward-compatible
- The two warning strings must match byte-for-byte (including the em-dash "—") as written in the change-request
- Confirm where the job result is assembled (`job_manager.py` vs `api/routes.py`) so warnings propagate to the API response

## Context Manifest Draft

### Affected Surfaces
- Backend API response schema (`GET /api/jobs/{id}` job result)
- PDF processor fitz→ReportLab fallback path and PDF→DOCX routing path
- API contract + generated OpenAPI specs

### Allowed Paths
- specs/changes/pdf-renderer-fallback-warn/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/processors/pdf_processor.py
- app/backend/api/schemas.py
- app/backend/api/routes.py
- app/backend/services/job_manager.py
- contracts/api/api-contract.md
- contracts/api/openapi.yml
- contracts/api/openapi.json
- contracts/data/data-shape-contract.md
- tests/

### Agent Work Packets

#### change-classifier
- specs/changes/pdf-renderer-fallback-warn/
- specs/context/project-map.md
- specs/context/contracts-index.md

#### implementation-planner
- specs/changes/pdf-renderer-fallback-warn/
- specs/context/project-map.md
- contracts/api/api-contract.md
- app/backend/api/schemas.py
- app/backend/processors/pdf_processor.py

#### backend-engineer
- specs/changes/pdf-renderer-fallback-warn/
- app/backend/processors/pdf_processor.py
- app/backend/api/schemas.py
- app/backend/api/routes.py
- app/backend/services/job_manager.py
- contracts/api/api-contract.md
- contracts/api/openapi.yml
- contracts/api/openapi.json
- tests/

#### contract-reviewer
- specs/changes/pdf-renderer-fallback-warn/
- contracts/api/api-contract.md
- contracts/api/openapi.yml
- contracts/api/openapi.json
- contracts/data/data-shape-contract.md

#### test-strategist
- specs/changes/pdf-renderer-fallback-warn/
- app/backend/processors/pdf_processor.py
- app/backend/api/schemas.py
- tests/

#### qa-reviewer
- specs/changes/pdf-renderer-fallback-warn/
- contracts/api/api-contract.md
- tests/
