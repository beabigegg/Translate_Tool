# Context Manifest — fallback-chain-cloud-providers

## Affected Surfaces
- provider routing / translation fallback chain (config/providers.yml, orchestrator.py)
- runtime configuration (DEEPSEEK_ENABLED env var, config.py)

## Allowed Paths
- specs/changes/fallback-chain-cloud-providers/
- specs/context/project-map.md
- specs/context/contracts-index.md
- config/providers.yml
- config/providers.yml.example
- app/backend/processors/orchestrator.py
- app/backend/config.py
- app/backend/services/model_router.py
- app/backend/parsers/layout_detector.py
- contracts/env/env-contract.md
- contracts/env/.env.example.template
- contracts/env/env.schema.json
- contracts/business/business-rules.md
- contracts/api/api-contract.md
- tests/test_provider_fallback.py
- tests/test_model_router.py
- tests/test_env_contract.py

## Required Contracts
- contracts/env/env-contract.md (add DEEPSEEK_ENABLED)
- contracts/business/business-rules.md (update fallback-chain rule)

## Context Expansion Requests
- CER-001: app/backend/services/model_router.py + app/backend/parsers/layout_detector.py — confirm wiring and layout-detection non-impact. Status: approved (added to Allowed Paths).
