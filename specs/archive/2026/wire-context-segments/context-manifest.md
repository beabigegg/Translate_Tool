# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- backend translation pipeline (prompt construction + batch orchestration)

## Allowed Paths
- specs/changes/wire-context-segments/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/config.py
- app/backend/utils/translation_helpers.py
- app/backend/clients/ollama_client.py
- app/backend/services/translation_service.py
- app/backend/services/context_prompts.py
- contracts/business/business-rules.md
- tests/test_ollama_client_dynamic_strategy.py
- tests/test_context_prompt_i18n.py
- tests/test_dead_references.py
- tests/test_context_window_segments.py

## Required Contracts
- contracts/business/business-rules.md

## Required Tests
- tests/test_ollama_client_dynamic_strategy.py
- tests/test_context_prompt_i18n.py
- tests/test_dead_references.py
- tests/test_context_window_segments.py (new — to be created by backend-engineer)

## Agent Work Packets

### contract-reviewer
- specs/changes/wire-context-segments/
- contracts/business/business-rules.md
- app/backend/config.py

### test-strategist
- specs/changes/wire-context-segments/
- tests/test_ollama_client_dynamic_strategy.py
- tests/test_context_prompt_i18n.py
- tests/test_dead_references.py
- app/backend/utils/translation_helpers.py
- app/backend/clients/ollama_client.py
- app/backend/services/translation_service.py
- app/backend/services/context_prompts.py
- app/backend/config.py

### implementation-planner
- specs/changes/wire-context-segments/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/config.py
- app/backend/utils/translation_helpers.py
- app/backend/clients/ollama_client.py
- app/backend/services/translation_service.py
- app/backend/services/context_prompts.py
- contracts/business/business-rules.md

### backend-engineer
- specs/changes/wire-context-segments/
- app/backend/config.py
- app/backend/utils/translation_helpers.py
- app/backend/clients/ollama_client.py
- app/backend/services/translation_service.py
- app/backend/services/context_prompts.py
- contracts/business/business-rules.md
- tests/test_ollama_client_dynamic_strategy.py
- tests/test_context_prompt_i18n.py
- tests/test_dead_references.py
- tests/test_context_window_segments.py

### qa-reviewer
- specs/changes/wire-context-segments/
- tests/test_dead_references.py
- tests/test_context_window_segments.py

## Context Expansion Requests
-

## Approved Expansions
-
