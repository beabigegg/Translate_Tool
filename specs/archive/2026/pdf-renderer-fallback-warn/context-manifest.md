# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- Backend API response schema (`GET /api/jobs/{id}` job result — `warnings` field added)
- PDF processor fitz→ReportLab fallback path (`pdf_processor.py` ~lines 836-840)
- PDF→DOCX routing trap path (`pdf_processor.py` ~lines 376-414)
- API contract + generated OpenAPI specs

## Allowed Paths
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
- .github/workflows/contract-driven-gates.yml
- ci/
- app/backend/processors/orchestrator.py

## Required Contracts
- contracts/api/api-contract.md
- contracts/api/openapi.yml
- contracts/api/openapi.json
- contracts/data/data-shape-contract.md (if job-result shape is defined there)

## Required Tests
- tests/ (new file: `tests/test_pdf_render_warnings.py` or added to `tests/test_pdf_processor.py`)

## Agent Work Packets

### change-classifier
- specs/changes/pdf-renderer-fallback-warn/
- specs/context/project-map.md
- specs/context/contracts-index.md

### implementation-planner
- specs/changes/pdf-renderer-fallback-warn/
- specs/context/project-map.md
- contracts/api/api-contract.md
- app/backend/api/schemas.py
- app/backend/processors/pdf_processor.py

### backend-engineer
- specs/changes/pdf-renderer-fallback-warn/
- app/backend/processors/pdf_processor.py
- app/backend/api/schemas.py
- app/backend/api/routes.py
- app/backend/services/job_manager.py
- contracts/api/api-contract.md
- contracts/api/openapi.yml
- contracts/api/openapi.json
- tests/

### contract-reviewer
- specs/changes/pdf-renderer-fallback-warn/
- contracts/api/api-contract.md
- contracts/api/openapi.yml
- contracts/api/openapi.json
- contracts/data/data-shape-contract.md

### test-strategist
- specs/changes/pdf-renderer-fallback-warn/
- app/backend/processors/pdf_processor.py
- app/backend/api/schemas.py
- tests/

### qa-reviewer
- specs/changes/pdf-renderer-fallback-warn/
- contracts/api/api-contract.md
- tests/

## Context Expansion Requests

- request-id: CER-001
  requested_paths:
    - app/backend/processors/pdf_processor.py
    - app/backend/api/schemas.py
    - app/backend/services/job_manager.py
  reason: Implementation agents need the actual fallback call site (~lines 836-840), routing trap (~lines 376-414), the job-result schema definition, and where the job result is assembled to confirm warning propagation seam.
  status: approved

## Approved Expansions
- CER-001: app/backend/processors/pdf_processor.py, app/backend/api/schemas.py, app/backend/services/job_manager.py (approved for implementation agents)
