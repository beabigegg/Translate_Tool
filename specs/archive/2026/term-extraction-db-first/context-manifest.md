# Context Manifest — term-extraction-db-first

## Affected Surfaces
- backend term-extraction service (term_extractor.py)
- backend term database (term_db.py)
- backend Phase 0 orchestration hook (orchestrator.py)
- backend LLM clients (PANJIT OpenAI-compatible client reuse)
- runtime config / env (PANJIT endpoint, threshold, SSL)

## Allowed Paths
- specs/changes/term-extraction-db-first/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/services/term_extractor.py
- app/backend/services/term_db.py
- app/backend/services/term_audit.py
- app/backend/processors/orchestrator.py
- app/backend/clients/openai_compatible_client.py
- app/backend/clients/base_llm_client.py
- app/backend/clients/ollama_client.py
- app/backend/services/model_router.py
- app/backend/services/context_prompts.py
- app/backend/config.py
- app/backend/models/term.py
- config/providers.yml
- config/providers.yml.example
- contracts/api/api-contract.md
- contracts/api/api-inventory.md
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- contracts/env/env-contract.md
- contracts/env/.env.example.template
- contracts/env/env.schema.json
- tests/test_term_extractor.py
- tests/test_term_db.py
- tests/test_term_audit.py
- tests/test_provider_fallback.py
- tests/test_openai_compatible_client.py
- tests/test_env_contract.py
- tests/test_translation_strategy.py
- docs/improvement-plan.md

## Required Contracts
- contracts/env/env-contract.md
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- contracts/api/api-inventory.md

## Context Expansion Requests
- CER-001: term_extractor.py, term_db.py, orchestrator.py — function-level wiring for spec-architect and implementation-planner. Status: approved (added to Allowed Paths).
- CER-002: openai_compatible_client.py, config/providers.yml — confirm PANJIT /v1/embeddings support and config keys. Status: approved (added to Allowed Paths).
