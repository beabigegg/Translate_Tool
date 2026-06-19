# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- Translation pipeline post-processing (new QE scoring step)
- API surface (new GET /jobs/{id}/quality endpoint)
- Job state / data shape (per-block quality scores)
- Runtime config / dependencies (new ML model + pip packages + env vars)

## Allowed Paths
<!-- UNION of all repo-relative paths (or globs) any agent may read for this change. -->
- specs/changes/p2-comet-qe/
- specs/context/project-map.md
- specs/context/contracts-index.md
- contracts/api/api-contract.md
- contracts/api/openapi.yml
- contracts/api/api-inventory.md
- contracts/api/error-format.md
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- contracts/env/env-contract.md
- contracts/env/.env.example.template
- contracts/env/env.schema.json
- contracts/ci/ci-gate-contract.md
- app/backend/api/routes.py
- app/backend/api/schemas.py
- app/backend/services/job_manager.py
- app/backend/services/translation_service.py
- app/backend/services/metrics.py
- app/backend/config.py
- app/backend/requirements.txt
- app/backend/environment.yml
- app/backend/main.py
- app/backend/services/quality_evaluator.py
- app/backend/processors/orchestrator.py
- app/backend/processors/docx_processor.py
- app/backend/processors/pdf_processor.py
- app/backend/processors/pptx_processor.py
- app/backend/processors/xlsx_processor.py
- tests/test_translation_strategy.py
- tests/test_env_contract.py
- tests/test_metrics_counters.py
- tests/test_metrics_endpoint.py
- tests/test_model_config_api.py
- tests/test_quality_evaluation.py
- tests/contract/
- .github/workflows/contract-driven-gates.yml

## Required Contracts
- contracts/api/api-contract.md
- contracts/api/openapi.yml
- contracts/data/data-shape-contract.md
- contracts/env/env-contract.md
- contracts/business/business-rules.md
- contracts/ci/ci-gate-contract.md (conditional on new gate)

## Required Tests
- tests/test_env_contract.py (new QE env vars)
- tests/test_translation_strategy.py (post-translation QE hook)
- tests/test_quality_evaluation.py (new — unit + endpoint + data-boundary)
- tests/contract/ (new endpoint contract samples)

## Agent Work Packets

### contract-reviewer
- specs/changes/p2-comet-qe/
- contracts/api/api-contract.md
- contracts/api/openapi.yml
- contracts/api/api-inventory.md
- contracts/api/error-format.md
- contracts/data/data-shape-contract.md
- contracts/env/env-contract.md
- contracts/business/business-rules.md
- contracts/ci/ci-gate-contract.md

### test-strategist
- specs/changes/p2-comet-qe/
- contracts/api/api-contract.md
- contracts/data/data-shape-contract.md
- contracts/env/env-contract.md
- contracts/business/business-rules.md
- tests/test_translation_strategy.py
- tests/test_env_contract.py
- tests/test_metrics_counters.py
- tests/contract/

### spec-architect
- specs/changes/p2-comet-qe/
- specs/context/project-map.md
- contracts/api/api-contract.md
- contracts/data/data-shape-contract.md
- contracts/env/env-contract.md
- contracts/business/business-rules.md
- app/backend/services/translation_service.py
- app/backend/services/job_manager.py
- app/backend/services/metrics.py
- app/backend/config.py
- app/backend/main.py

### ci-cd-gatekeeper
- specs/changes/p2-comet-qe/
- contracts/ci/ci-gate-contract.md
- contracts/api/openapi.yml
- app/backend/requirements.txt
- app/backend/environment.yml
- .github/workflows/contract-driven-gates.yml

### implementation-planner
- specs/changes/p2-comet-qe/
- contracts/api/api-contract.md
- contracts/data/data-shape-contract.md
- contracts/env/env-contract.md
- contracts/business/business-rules.md
- app/backend/api/routes.py
- app/backend/api/schemas.py
- app/backend/services/translation_service.py
- app/backend/services/job_manager.py
- app/backend/config.py

### backend-engineer
- specs/changes/p2-comet-qe/
- contracts/api/api-contract.md
- contracts/data/data-shape-contract.md
- contracts/env/env-contract.md
- contracts/business/business-rules.md
- app/backend/api/routes.py
- app/backend/api/schemas.py
- app/backend/services/translation_service.py
- app/backend/services/job_manager.py
- app/backend/services/metrics.py
- app/backend/services/quality_evaluator.py
- app/backend/config.py
- app/backend/main.py
- app/backend/requirements.txt
- app/backend/environment.yml
- contracts/env/.env.example.template
- contracts/env/env.schema.json
- tests/test_translation_strategy.py
- tests/test_env_contract.py
- tests/test_metrics_counters.py
- tests/test_quality_evaluation.py
- tests/contract/

### dependency-security-reviewer
- specs/changes/p2-comet-qe/
- app/backend/requirements.txt
- app/backend/environment.yml
- contracts/env/env-contract.md

### qa-reviewer
- specs/changes/p2-comet-qe/
- contracts/api/api-contract.md
- contracts/data/data-shape-contract.md
- contracts/env/env-contract.md
- contracts/business/business-rules.md
- tests/

## Context Expansion Requests

- request-id: CER-001
  requested_paths:
    - app/backend/services/quality_evaluator.py
  reason: New QE service module to be created during implementation; parent dir app/backend/services/ is in scope.
  status: approved

- request-id: CER-002
  requested_paths:
    - app/backend/processors/orchestrator.py
    - app/backend/processors/docx_processor.py
    - app/backend/processors/pdf_processor.py
    - app/backend/processors/pptx_processor.py
    - app/backend/processors/xlsx_processor.py
  reason: Option C chosen — wire translate_document() into all format processors as part of this change. Need to read all processors to design the minimal-invasive wiring approach (DR-1 resolution).
  status: approved

## Approved Expansions
- CER-001: app/backend/services/quality_evaluator.py — approved (new file, parent dir in scope)
- CER-002: app/backend/processors/ (orchestrator + all format processors) — approved for DR-1 architecture resolution and implementation
