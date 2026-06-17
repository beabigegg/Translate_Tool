# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- backend API (new `GET /api/metrics` endpoint in app/backend/api/routes.py)
- backend services / instrumentation (new counter module; increment hooks in translation and font-load call sites)

## Allowed Paths
- specs/changes/p1-observability-metrics/
- specs/context/project-map.md
- specs/context/contracts-index.md
- contracts/api/api-contract.md
- contracts/api/api-inventory.md
- contracts/api/error-format.md
- contracts/api/openapi.yml
- contracts/business/business-rules.md
- app/backend/api/routes.py
- app/backend/api/schemas.py
- app/backend/services/model_router.py
- app/backend/services/translation_service.py
- app/backend/renderers/pdf_generator.py
- app/backend/services/
- tests/
- .github/workflows/contract-driven-gates.yml
- ci/

## Required Contracts
- contracts/api/api-contract.md
- contracts/api/api-inventory.md
- contracts/api/openapi.yml
- contracts/business/business-rules.md

## Required Tests
- tests/ (new: test_metrics_counters.py and/or test_metrics_endpoint.py)
- tests/test_model_router.py (reference — provider/model resolution call site)
- tests/test_pdf_generator.py (reference — font cache call site)

## Agent Work Packets

### change-classifier
- specs/changes/p1-observability-metrics/
- specs/context/project-map.md
- specs/context/contracts-index.md

### contract-reviewer
- specs/changes/p1-observability-metrics/
- contracts/api/api-contract.md
- contracts/api/api-inventory.md
- contracts/api/error-format.md
- contracts/api/openapi.yml
- contracts/business/business-rules.md

### test-strategist
- specs/changes/p1-observability-metrics/
- contracts/api/api-contract.md
- contracts/business/business-rules.md
- tests/

### implementation-planner
- specs/changes/p1-observability-metrics/
- contracts/api/api-contract.md
- contracts/business/business-rules.md

### backend-engineer
- specs/changes/p1-observability-metrics/
- contracts/api/api-contract.md
- contracts/business/business-rules.md
- app/backend/api/routes.py
- app/backend/api/schemas.py
- app/backend/services/model_router.py
- app/backend/services/translation_service.py
- app/backend/renderers/pdf_generator.py
- app/backend/services/
- tests/

### ci-cd-gatekeeper
- specs/changes/p1-observability-metrics/
- contracts/api/openapi.yml
- .github/workflows/contract-driven-gates.yml
- ci/

### qa-reviewer
- specs/changes/p1-observability-metrics/
- contracts/api/api-contract.md
- tests/

## Context Expansion Requests

- request-id: CER-001
  requested_paths:
    - app/backend/services/translation_service.py
    - app/backend/services/model_router.py
    - app/backend/renderers/pdf_generator.py
  reason: The indexes do not reveal exact translation/font-load call-site signatures where counter increments must be hooked. backend-engineer needs these files to add additive increment hooks without altering existing behavior.
  status: approved (pre-authorized in Allowed Paths above)

## Approved Expansions
- CER-001: app/backend/services/translation_service.py, app/backend/services/model_router.py, app/backend/renderers/pdf_generator.py — approved for backend-engineer read scope
