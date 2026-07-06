# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- Backend document-conversion layer (`libreoffice_helpers.py`, `orchestrator.py`)
- Backend config / supported-extensions surface (`config.py`)
- Frontend upload surface (`fileTypes.js`, `FileDropZone.jsx`)
- API upload contract (`contracts/api/api-contract.md` + `openapi.yml`)
- Runtime/dependency surface (`environment.yml`, env-contract, install docs)
- Business-rule + CI-gate contracts (lossy-conversion policy, LibreOffice-in-CI policy)

## Allowed Paths
- specs/changes/support-legacy-office-formats/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/config.py
- app/backend/processors/libreoffice_helpers.py
- app/backend/processors/orchestrator.py
- app/backend/services/quality_evaluator.py
- app/frontend/src/constants/fileTypes.js
- app/frontend/src/components/domain/FileDropZone.jsx
- app/backend/environment.yml
- app/backend/requirements.txt
- contracts/api/api-contract.md
- contracts/api/api-inventory.md
- contracts/api/openapi.yml
- contracts/env/env-contract.md
- contracts/business/business-rules.md
- contracts/ci/ci-gate-contract.md
- .github/workflows/contract-driven-gates.yml
- README.md
- docs/
- tests/conftest.py
- tests/fixtures/
- tests/contract/
- tests/test_orchestrator_phase0.py
- tests/test_output_mode_orchestrator.py
- tests/test_libreoffice_helpers.py

## Required Contracts
- contracts/api/api-contract.md
- contracts/api/openapi.yml
- contracts/env/env-contract.md
- contracts/business/business-rules.md
- contracts/ci/ci-gate-contract.md

## Required Tests
- tests/test_libreoffice_helpers.py (new — ppt/doc/xls conversion + availability degradation)
- tests/test_orchestrator_phase0.py (orchestrator legacy-branch integration)
- tests/contract/ (upload-accepted-extensions conformance)
- tests/fixtures/ (legacy-format + malformed-file fixtures)

## Agent Work Packets

### spec-architect
- specs/changes/support-legacy-office-formats/
- specs/context/project-map.md
- specs/context/contracts-index.md
- contracts/api/api-contract.md
- contracts/business/business-rules.md
- contracts/env/env-contract.md
- app/backend/processors/orchestrator.py
- app/backend/services/quality_evaluator.py

### implementation-planner
- specs/changes/support-legacy-office-formats/
- contracts/api/api-contract.md
- contracts/env/env-contract.md
- contracts/business/business-rules.md
- app/backend/config.py
- app/backend/processors/libreoffice_helpers.py
- app/backend/processors/orchestrator.py
- app/frontend/src/constants/fileTypes.js

### backend-engineer
- specs/changes/support-legacy-office-formats/
- app/backend/config.py
- app/backend/processors/libreoffice_helpers.py
- app/backend/processors/orchestrator.py
- app/backend/environment.yml
- app/backend/requirements.txt
- tests/test_libreoffice_helpers.py
- tests/test_orchestrator_phase0.py
- tests/fixtures/
- tests/conftest.py

### frontend-engineer
- specs/changes/support-legacy-office-formats/
- app/frontend/src/constants/fileTypes.js
- app/frontend/src/components/domain/FileDropZone.jsx

### test-strategist
- specs/changes/support-legacy-office-formats/
- tests/
- contracts/api/api-contract.md
- contracts/business/business-rules.md

### contract-reviewer
- specs/changes/support-legacy-office-formats/
- contracts/api/api-contract.md
- contracts/api/api-inventory.md
- contracts/api/openapi.yml
- contracts/env/env-contract.md
- contracts/business/business-rules.md
- contracts/ci/ci-gate-contract.md

### dependency-security-reviewer
- specs/changes/support-legacy-office-formats/
- app/backend/processors/libreoffice_helpers.py
- app/backend/environment.yml
- app/backend/requirements.txt
- contracts/env/env-contract.md

### ci-cd-gatekeeper
- specs/changes/support-legacy-office-formats/
- contracts/ci/ci-gate-contract.md
- .github/workflows/contract-driven-gates.yml
- app/backend/environment.yml

### ui-ux-reviewer
- specs/changes/support-legacy-office-formats/
- app/frontend/src/constants/fileTypes.js
- app/frontend/src/components/domain/FileDropZone.jsx

### visual-reviewer
- specs/changes/support-legacy-office-formats/
- app/frontend/src/components/domain/FileDropZone.jsx

### qa-reviewer
- specs/changes/support-legacy-office-formats/
- contracts/api/api-contract.md
- tests/

## Context Expansion Requests
- request-id: CER-001
  requested_paths:
    - app/frontend/src/components/domain/FileDropZone.jsx
  reason: Classifier inferred this path without shell access; main Claude verified it exists and read its contents in-session prior to classification.
  status: approved

- request-id: CER-002
  requested_paths:
    - app/frontend/src/i18n/
  reason: Checked whether drop-zone copy is i18n-managed; confirmed FileDropZone.jsx uses hardcoded inline copy with no i18n import, so no i18n/ read is needed for this change.
  status: resolved-not-needed

## Approved Expansions
- CER-001: app/frontend/src/components/domain/FileDropZone.jsx — approved, path verified real by main Claude before classification.
- tests/test_quality_evaluation.py
