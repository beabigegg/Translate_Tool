# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- Backend document-context detection path (`processors/orchestrator.py::_detect_document_context` and its `_cloud_client is None` guard)
- Cloud LLM client summary generation (`clients/openai_compatible_client.py`, base client)
- Translation system-prompt preamble injection (existing `translation_strategy` / `translation_service` wiring — read-only reuse)
- Feature-flag gating (`config.py`: `CONTEXT_DETECTION_ENABLED`, `QWEN_CONTEXT_FLOW_ENABLED`)

## Allowed Paths
- specs/changes/cloud-doc-context-summary/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/processors/orchestrator.py
- app/backend/services/context_prompts.py
- app/backend/clients/openai_compatible_client.py
- app/backend/clients/base_llm_client.py
- app/backend/clients/ollama_client.py
- app/backend/config.py
- app/backend/services/model_router.py
- app/backend/services/translation_strategy.py
- app/backend/services/translation_service.py
- contracts/business/business-rules.md
- contracts/env/env-contract.md
- contracts/env/.env.example.template
- contracts/env/env.schema.json
- contracts/CHANGELOG.md
- tests/

## Required Contracts
- contracts/business/business-rules.md
- contracts/env/env-contract.md

## Required Tests
- tests/test_context_prefix_bleed.py
- tests/test_context_prompt_i18n.py
- tests/test_orchestrator_phase0.py
- (new or extended cloud-path context-detection test — node-id TBD by test-strategist)

## Agent Work Packets

### change-classifier
- specs/changes/cloud-doc-context-summary/
- specs/context/project-map.md
- specs/context/contracts-index.md

### implementation-planner
- specs/changes/cloud-doc-context-summary/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/processors/orchestrator.py
- app/backend/services/context_prompts.py
- app/backend/clients/openai_compatible_client.py
- app/backend/clients/base_llm_client.py
- app/backend/clients/ollama_client.py
- app/backend/config.py
- app/backend/services/model_router.py
- app/backend/services/translation_strategy.py
- app/backend/services/translation_service.py
- contracts/business/business-rules.md
- contracts/env/env-contract.md
- tests/

### backend-engineer
- specs/changes/cloud-doc-context-summary/
- app/backend/processors/orchestrator.py
- app/backend/services/context_prompts.py
- app/backend/clients/openai_compatible_client.py
- app/backend/clients/base_llm_client.py
- app/backend/clients/ollama_client.py
- app/backend/config.py
- app/backend/services/model_router.py
- app/backend/services/translation_strategy.py
- app/backend/services/translation_service.py
- tests/

### test-strategist
- specs/changes/cloud-doc-context-summary/
- contracts/business/business-rules.md
- contracts/env/env-contract.md
- tests/

### contract-reviewer
- specs/changes/cloud-doc-context-summary/
- contracts/business/business-rules.md
- contracts/env/env-contract.md
- contracts/env/.env.example.template
- contracts/env/env.schema.json
- contracts/CHANGELOG.md

### qa-reviewer
- specs/changes/cloud-doc-context-summary/
- contracts/business/business-rules.md
- contracts/env/env-contract.md

## Context Expansion Requests

- request-id: CER-001
  requested_paths:
    - tests/
  reason: A promoted learning warns that threading a client parameter through a
    shared seam (`_detect_document_context`) predictably breaks test doubles that
    reproduce the signature (fake clients/closures in `test_orchestrator_judge.py`,
    `test_fewshot_glossary.py`, `test_translation_strategy.py`,
    `test_translation_service.py`, and unexpected files). implementation-planner /
    backend-engineer needs a whole-`tests/`-tree grep to find and update every such
    fake in the SAME change. Scope the grep to the changed seam; do not read
    unrelated test bodies.
  status: approved

## Approved Expansions
- CER-001 (tests/) — approved at scaffold time; `tests/` is included in Allowed Paths above. Grep scoped to the changed seam only.
