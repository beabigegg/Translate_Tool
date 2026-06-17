# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- LLM context-detection prompt generation (backend processors/services)
- Runtime config: Ollama context-window env vars
- Env contract + env schema + .env example

## Allowed Paths
- specs/changes/p1-prompt-i18n-numctx/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/config.py
- app/backend/processors/orchestrator.py
- app/backend/services/translation_service.py
- app/backend/__init__.py
- contracts/env/env-contract.md
- contracts/env/.env.example.template
- contracts/env/env.schema.json
- contracts/business/business-rules.md
- tests/test_translation_strategy.py
- tests/

## Required Contracts
- contracts/env/env-contract.md (update: add GENERAL_NUM_CTX, TRANSLATION_NUM_CTX; update .env.example.template and env.schema.json)
- contracts/business/business-rules.md (review only)

## Required Tests
- tests/ (new test file: tests/test_context_prompt_i18n.py for prompt-template selection and num_ctx resolution)
- tests/test_translation_strategy.py (review for num_ctx coverage)

## Agent Work Packets

### change-classifier
- specs/changes/p1-prompt-i18n-numctx/
- specs/context/project-map.md
- specs/context/contracts-index.md

### implementation-planner
- specs/changes/p1-prompt-i18n-numctx/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/config.py
- app/backend/processors/orchestrator.py
- app/backend/services/translation_service.py
- contracts/env/env-contract.md

### backend-engineer
- specs/changes/p1-prompt-i18n-numctx/
- app/backend/config.py
- app/backend/processors/orchestrator.py
- app/backend/services/translation_service.py
- app/backend/__init__.py
- contracts/env/env-contract.md
- contracts/env/.env.example.template
- contracts/env/env.schema.json

### test-strategist
- specs/changes/p1-prompt-i18n-numctx/
- app/backend/config.py
- app/backend/processors/orchestrator.py
- app/backend/services/translation_service.py
- tests/

### contract-reviewer
- specs/changes/p1-prompt-i18n-numctx/
- contracts/env/env-contract.md
- contracts/env/.env.example.template
- contracts/env/env.schema.json
- contracts/business/business-rules.md

### qa-reviewer
- specs/changes/p1-prompt-i18n-numctx/
- tests/

## Context Expansion Requests

- request-id: CER-001
  requested_paths:
    - app/backend/clients/ollama_client.py
    - app/backend/clients/base_llm_client.py
  reason: If num_ctx resolution is consumed by the Ollama client downstream of config.py, backend-engineer may need to read the client to confirm per-type value is wired correctly. Approve if implementation-planner determines it is needed.
  status: withdrawn
  resolution: Not needed — NUM_CTX flows via MODULE_TYPE_OPTIONS from module-level constants in config.py; ollama_client.py does not need reading to confirm the wiring.

## Approved Expansions
-
