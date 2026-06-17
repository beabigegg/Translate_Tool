# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- Backend LLM client layer (`app/backend/clients/`)
- Translation service consumer (`app/backend/services/translation_service.py`)

## Allowed Paths
- specs/changes/p1-llm-client-abstraction/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/clients/
- app/backend/services/translation_service.py
- app/backend/utils/exceptions.py
- app/backend/utils/translation_helpers.py
- app/backend/config.py
- tests/test_ollama_client_dynamic_strategy.py
- tests/test_translation_strategy.py
- tests/test_hy_mt_quality_refinement.py
- tests/test_translation_profiles_scenarios.py
- tests/test_model_router.py
- tests/__init__.py
- contracts/

## Required Contracts
- none (contracts/ is read-only for confirmation only)

## Required Tests
- tests/test_ollama_client_dynamic_strategy.py
- tests/test_translation_strategy.py
- tests/test_hy_mt_quality_refinement.py
- tests/test_translation_profiles_scenarios.py
- tests/test_model_router.py
- tests/test_llm_client_protocol.py (new — to be created by backend-engineer)

## Agent Work Packets

### spec-architect
- specs/changes/p1-llm-client-abstraction/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/clients/
- app/backend/services/translation_service.py
- app/backend/utils/exceptions.py

### test-strategist
- specs/changes/p1-llm-client-abstraction/
- app/backend/clients/
- app/backend/services/translation_service.py
- tests/test_ollama_client_dynamic_strategy.py
- tests/test_translation_strategy.py
- tests/test_hy_mt_quality_refinement.py
- tests/test_translation_profiles_scenarios.py
- tests/test_model_router.py

### ci-cd-gatekeeper
- specs/changes/p1-llm-client-abstraction/
- contracts/ci/ci-gate-contract.md

### implementation-planner
- specs/changes/p1-llm-client-abstraction/
- app/backend/clients/
- app/backend/services/translation_service.py

### backend-engineer
- specs/changes/p1-llm-client-abstraction/
- app/backend/clients/
- app/backend/services/translation_service.py
- app/backend/utils/exceptions.py
- app/backend/utils/translation_helpers.py
- app/backend/config.py
- tests/test_ollama_client_dynamic_strategy.py
- tests/test_translation_strategy.py
- tests/test_hy_mt_quality_refinement.py
- tests/test_translation_profiles_scenarios.py
- tests/test_model_router.py
- tests/__init__.py

### contract-reviewer
- specs/changes/p1-llm-client-abstraction/
- contracts/
- app/backend/clients/

### qa-reviewer
- specs/changes/p1-llm-client-abstraction/
- app/backend/clients/
- app/backend/services/translation_service.py
- tests/

## Context Expansion Requests
-

## Approved Expansions
- CER-001: `app/backend/clients/ollama_client.py` — inside already-allowed `app/backend/clients/`; approved inline at classification.
