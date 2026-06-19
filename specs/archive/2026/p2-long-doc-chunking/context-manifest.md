# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- backend/services — `translation_service.py` (new Doc2Doc entry point)
- backend/services — new `doc_chunker.py` module (semantic chunking, owned area)
- backend/config — `config.py` + env (`CHUNK_OVERLAP_TOKENS`)
- contracts — env, data-shape, business

## Allowed Paths
- specs/changes/p2-long-doc-chunking/
- specs/context/project-map.md
- specs/context/contracts-index.md
- contracts/env/env-contract.md
- contracts/env/.env.example.template
- contracts/env/env.schema.json
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md
- app/backend/services/translation_service.py
- app/backend/services/translation_strategy.py
- app/backend/services/doc_chunker.py
- app/backend/utils/text_utils.py
- app/backend/config.py
- app/backend/models/translatable_document.py
- tests/test_translation_strategy.py
- tests/test_sentence_mode_consistency.py
- tests/test_env_contract.py
- tests/test_doc_chunker.py
- .github/workflows/contract-driven-gates.yml

## Required Contracts
- contracts/env/env-contract.md
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md

## Required Tests
- tests/test_doc_chunker.py (new — unit + reassembly + data-boundary)
- tests/test_translation_strategy.py (Doc2Doc integration; mocked LLM client)
- tests/test_env_contract.py (CHUNK_OVERLAP_TOKENS)
- tests/test_sentence_mode_consistency.py (sentence-boundary fallback consistency)

## Agent Work Packets

### spec-architect
- specs/changes/p2-long-doc-chunking/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/services/translation_service.py
- app/backend/services/translation_strategy.py
- app/backend/models/translatable_document.py
- app/backend/utils/text_utils.py
- app/backend/config.py
- app/backend/processors/orchestrator.py
- app/backend/api/routes.py
- app/backend/api/schemas.py
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- contracts/env/env-contract.md

### implementation-planner
- specs/changes/p2-long-doc-chunking/
- app/backend/services/translation_service.py
- app/backend/services/translation_strategy.py
- app/backend/config.py
- app/backend/processors/orchestrator.py
- app/backend/api/routes.py
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- contracts/env/env-contract.md

### backend-engineer
- specs/changes/p2-long-doc-chunking/
- app/backend/services/doc_chunker.py
- app/backend/services/translation_service.py
- app/backend/services/translation_strategy.py
- app/backend/config.py
- app/backend/models/translatable_document.py
- app/backend/utils/text_utils.py
- contracts/env/.env.example.template
- contracts/env/env.schema.json

### test-strategist
- specs/changes/p2-long-doc-chunking/
- app/backend/services/doc_chunker.py
- app/backend/services/translation_service.py
- tests/test_doc_chunker.py
- tests/test_translation_strategy.py
- tests/test_env_contract.py
- tests/test_sentence_mode_consistency.py
- app/backend/processors/orchestrator.py
- app/backend/api/routes.py
- app/backend/api/schemas.py

### contract-reviewer
- specs/changes/p2-long-doc-chunking/
- contracts/env/env-contract.md
- contracts/env/.env.example.template
- contracts/env/env.schema.json
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md

### qa-reviewer
- specs/changes/p2-long-doc-chunking/
- app/backend/services/doc_chunker.py
- app/backend/services/translation_service.py
- tests/test_doc_chunker.py
- tests/test_translation_strategy.py

## Context Expansion Requests

- request-id: CER-001
  requested_paths:
    - app/backend/processors/orchestrator.py
    - app/backend/api/routes.py
    - app/backend/api/schemas.py
  reason: Confirm whether Doc2Doc path is invoked by orchestrator or exposed over HTTP; routes.py and orchestrator.py both grep-confirmed to reference translation logic.
  status: approved

## Approved Expansions
- CER-001: app/backend/processors/orchestrator.py, app/backend/api/routes.py, app/backend/api/schemas.py (all agent work packets)
