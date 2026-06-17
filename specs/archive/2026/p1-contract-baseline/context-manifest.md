# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- api (contracts/api/*)
- data (contracts/data/data-shape-contract.md)
- domain-behavior (contracts/business/business-rules.md)

## Allowed Paths
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

## Required Contracts
- contracts/api/api-contract.md
- contracts/api/api-inventory.md
- contracts/api/error-format.md
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md

## Required Tests
- none (no test files added; conformance gate `cdd-kit validate --contracts` is the verification)

## Agent Work Packets

### change-classifier
- specs/changes/p1-contract-baseline/
- specs/context/project-map.md
- specs/context/contracts-index.md

### implementation-planner
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

### contract-reviewer
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

### qa-reviewer
- specs/changes/p1-contract-baseline/
- contracts/api/api-contract.md
- contracts/api/api-inventory.md
- contracts/api/error-format.md
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md

## Context Expansion Requests
-

## Approved Expansions
-
