# Context Manifest — p1-cloud-providers

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- backend LLM clients (`app/backend/clients/`)
- backend services routing/translation (`app/backend/services/model_router.py`, `translation_service.py`, `job_manager.py`)
- backend config (`app/backend/config.py`, new `config/providers.yml`)
- backend API (`app/backend/api/routes.py`, `app/backend/api/schemas.py` — `/route-info`, JobStatus)
- contracts: api, env, data, business

## Allowed Paths
- specs/changes/p1-cloud-providers/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/clients/
- app/backend/clients/base_llm_client.py
- app/backend/clients/ollama_client.py
- app/backend/clients/openai_compatible_client.py
- app/backend/clients/__init__.py
- app/backend/services/model_router.py
- app/backend/services/translation_service.py
- app/backend/services/job_manager.py
- app/backend/processors/orchestrator.py
- app/backend/config.py
- app/backend/api/routes.py
- app/backend/api/schemas.py
- config/providers.yml
- contracts/api/api-contract.md
- contracts/api/api-inventory.md
- contracts/env/env-contract.md
- contracts/env/.env.example.template
- contracts/env/env.schema.json
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md
- docs/improvement-plan.md
- tests/test_model_router.py
- tests/test_model_config_api.py
- tests/test_openai_compatible_client.py
- tests/test_provider_fallback.py
- tests/contract/

## Required Contracts
- contracts/api/api-contract.md
- contracts/api/api-inventory.md
- contracts/env/env-contract.md
- contracts/env/.env.example.template
- contracts/env/env.schema.json
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md

## Required Tests
- tests/test_model_router.py (update for config-driven routing)
- tests/test_model_config_api.py (update for provider field in /route-info)
- tests/test_openai_compatible_client.py (new — Protocol conformance + request/response)
- tests/test_provider_fallback.py (new — resilience/fallback tests)
- tests/contract/ (Protocol conformance + JobStatus shape)

## Agent Work Packets

### spec-architect
- specs/changes/p1-cloud-providers/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/clients/base_llm_client.py
- app/backend/services/model_router.py
- app/backend/services/translation_service.py
- app/backend/config.py
- docs/improvement-plan.md
- contracts/api/api-contract.md
- contracts/env/env-contract.md
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md

### contract-reviewer
- specs/changes/p1-cloud-providers/
- contracts/api/api-contract.md
- contracts/api/api-inventory.md
- contracts/env/env-contract.md
- contracts/env/.env.example.template
- contracts/env/env.schema.json
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md

### test-strategist
- specs/changes/p1-cloud-providers/
- app/backend/clients/
- app/backend/services/
- app/backend/config.py
- app/backend/api/
- tests/

### ci-cd-gatekeeper
- specs/changes/p1-cloud-providers/
- specs/context/project-map.md
- contracts/

### implementation-planner
- specs/changes/p1-cloud-providers/
- app/backend/clients/
- app/backend/services/model_router.py
- app/backend/services/translation_service.py
- app/backend/services/job_manager.py
- app/backend/processors/orchestrator.py
- app/backend/config.py
- app/backend/api/routes.py
- app/backend/api/schemas.py
- contracts/
- docs/improvement-plan.md

### backend-engineer
- specs/changes/p1-cloud-providers/
- app/backend/clients/
- app/backend/services/model_router.py
- app/backend/services/translation_service.py
- app/backend/services/job_manager.py
- app/backend/processors/orchestrator.py
- app/backend/config.py
- app/backend/api/routes.py
- app/backend/api/schemas.py
- config/providers.yml
- contracts/
- tests/

### qa-reviewer
- specs/changes/p1-cloud-providers/
- contracts/
- tests/

## Context Expansion Requests
- (none at time of classification; if backend-engineer needs additional files during implementation, file CER-001 before reading)

## Approved Expansions
-
