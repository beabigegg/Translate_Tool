# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- Backend PDF translation pipeline — progress-detail snapshot wiring (`status_callback` threading)
- Data-shape contract — `current_segment` snapshot fields (additive parity note)

## Allowed Paths
- specs/changes/pdf-stage-detail-snapshot/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/processors/pdf_processor.py
- app/backend/processors/orchestrator.py
- app/backend/services/job_manager.py
- app/backend/services/translation_service.py
- app/backend/utils/translation_helpers.py
- contracts/data/data-shape-contract.md
- contracts/api/api-contract.md
- .github/workflows/contract-driven-gates.yml
- contracts/ci/ci-gate-contract.md
- tests/test_job_manager_current_segment.py
- tests/test_jobstatus_stage_detail.py
- tests/test_pdf_stage_snapshot.py

(`contracts/api/api-contract.md` is read-only — contract-reviewer confirms the `JobStatus`
snapshot fields are unchanged. `tests/test_pdf_stage_snapshot.py` is NEW.)

## Required Contracts
- contracts/data/data-shape-contract.md (additive note)
- contracts/api/api-contract.md (read-only confirmation, no edit)

## Required Tests
- tests/test_pdf_stage_snapshot.py (new)
- tests/test_job_manager_current_segment.py
- tests/test_jobstatus_stage_detail.py

## Agent Work Packets

### change-classifier
- specs/changes/pdf-stage-detail-snapshot/
- specs/context/project-map.md
- specs/context/contracts-index.md

### implementation-planner
- specs/changes/pdf-stage-detail-snapshot/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/processors/pdf_processor.py
- app/backend/processors/orchestrator.py
- app/backend/services/translation_service.py
- app/backend/services/job_manager.py
- app/backend/utils/translation_helpers.py

### bug-fix-engineer
- specs/changes/pdf-stage-detail-snapshot/
- app/backend/processors/pdf_processor.py
- app/backend/processors/orchestrator.py
- app/backend/services/job_manager.py
- app/backend/services/translation_service.py
- app/backend/utils/translation_helpers.py
- contracts/data/data-shape-contract.md
- tests/test_pdf_stage_snapshot.py
- tests/test_job_manager_current_segment.py
- tests/test_jobstatus_stage_detail.py

### test-strategist
- specs/changes/pdf-stage-detail-snapshot/
- app/backend/processors/pdf_processor.py
- app/backend/utils/translation_helpers.py
- app/backend/services/job_manager.py
- tests/test_pdf_stage_snapshot.py
- tests/test_job_manager_current_segment.py
- tests/test_jobstatus_stage_detail.py

### contract-reviewer
- specs/changes/pdf-stage-detail-snapshot/
- contracts/data/data-shape-contract.md
- contracts/api/api-contract.md

### qa-reviewer
- specs/changes/pdf-stage-detail-snapshot/
- app/backend/processors/pdf_processor.py
- app/backend/processors/orchestrator.py
- tests/test_pdf_stage_snapshot.py
- tests/test_job_manager_current_segment.py

## Context Expansion Requests
- request-id: CER-001
  requested_paths:
    - app/backend/api/schemas.py
    - app/backend/api/routes.py
  reason: If the PDF-path fix requires confirming how `job.current_segment` is serialized onto the `JobStatus` response, these are the serialization sites. Pending because the mapping already populates for Office (unchanged); open only if evidence shows the serialization layer also needs a change.
  status: pending

- request-id: CER-002
  requested_paths:
    - .github/workflows/contract-driven-gates.yml
  reason: ci-cd-gatekeeper needs current PR-required gate steps (blanket pytest job name/step) and the tier contract definitions to write ci-gates.md for this Tier-3 bug-fix
  status: approved
## Approved Expansions
- contracts/ci/ci-gate-contract.md
- .github/workflows/contract-driven-gates.yml contracts/ci/ci-gate-contract.md
