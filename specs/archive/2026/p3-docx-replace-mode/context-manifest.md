# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- Backend processors: DOCX/PPTX translation output path
- Backend orchestration: job-request parameter threading
- Backend API: `POST /api/jobs` request schema

## Allowed Paths
- specs/changes/p3-docx-replace-mode/
- specs/context/project-map.md
- specs/context/contracts-index.md
- contracts/api/api-contract.md
- contracts/api/openapi.yml
- contracts/api/openapi.json
- contracts/api/api-inventory.md
- contracts/business/business-rules.md
- app/backend/processors/docx_processor.py
- app/backend/processors/pptx_processor.py
- app/backend/processors/orchestrator.py
- app/backend/api/routes.py
- app/backend/api/schemas.py
- app/backend/services/job_manager.py
- tests/

## Required Contracts
- contracts/api/api-contract.md
- contracts/business/business-rules.md

## Required Tests
- tests/ (new test for output_mode in processors + API; orchestrator threading)

## Agent Work Packets

### change-classifier
- specs/changes/p3-docx-replace-mode/
- specs/context/project-map.md
- specs/context/contracts-index.md

### implementation-planner
- specs/changes/p3-docx-replace-mode/
- specs/context/project-map.md
- specs/context/contracts-index.md
- contracts/api/api-contract.md
- contracts/business/business-rules.md
- app/backend/processors/docx_processor.py
- app/backend/processors/pptx_processor.py
- app/backend/processors/orchestrator.py
- app/backend/api/routes.py
- app/backend/api/schemas.py

### backend-engineer
- specs/changes/p3-docx-replace-mode/
- contracts/api/api-contract.md
- contracts/api/openapi.yml
- contracts/api/openapi.json
- contracts/business/business-rules.md
- app/backend/processors/docx_processor.py
- app/backend/processors/pptx_processor.py
- app/backend/processors/orchestrator.py
- app/backend/api/routes.py
- app/backend/api/schemas.py
- app/backend/services/job_manager.py
- tests/

### test-strategist
- specs/changes/p3-docx-replace-mode/
- tests/
- app/backend/processors/docx_processor.py
- app/backend/processors/pptx_processor.py
- app/backend/processors/orchestrator.py

### contract-reviewer
- specs/changes/p3-docx-replace-mode/
- contracts/api/api-contract.md
- contracts/api/openapi.yml
- contracts/api/api-inventory.md
- contracts/business/business-rules.md

### qa-reviewer
- specs/changes/p3-docx-replace-mode/
- contracts/api/api-contract.md
- contracts/business/business-rules.md
- app/backend/processors/docx_processor.py
- app/backend/processors/pptx_processor.py
- app/backend/processors/orchestrator.py
- app/backend/api/routes.py
- tests/

## Context Expansion Requests
-

## Approved Expansions
-
