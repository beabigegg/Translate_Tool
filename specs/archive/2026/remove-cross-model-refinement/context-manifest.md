# Context Manifest — remove-cross-model-refinement

## Affected Surfaces
- backend translation orchestration / model routing (cross-model refinement path)
- backend LLM client (Ollama refinement methods)
- backend config constants (refinement flags)

## Allowed Paths
- specs/changes/remove-cross-model-refinement/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/config.py
- app/backend/processors/orchestrator.py
- app/backend/clients/ollama_client.py
- app/backend/clients/base_llm_client.py
- app/backend/services/model_router.py
- app/backend/services/translation_strategy.py
- app/backend/services/translation_service.py
- contracts/env/env-contract.md
- contracts/business/business-rules.md
- contracts/api/api-contract.md
- contracts/data/data-shape-contract.md
- tests/test_hy_mt_quality_refinement.py
- tests/test_model_router.py
- tests/test_ollama_client_dynamic_strategy.py
- tests/test_translation_strategy.py
- tests/test_llm_client_protocol.py
- tests/test_env_contract.py
- tests/test_provider_fallback.py
- tests/test_sentence_mode_consistency.py
- tests/test_metrics_counters.py

## Required Contracts
- contracts/env/env-contract.md (verify/remove refinement constants if env-sourced)
- contracts/business/business-rules.md (verify no refinement rule)
- contracts/api/api-contract.md (read-only conformance confirmation)
- contracts/data/data-shape-contract.md (read-only, no expected change)

## Context Expansion Requests
- None at classification time. File CER-001 if backend-engineer finds additional consumer files via grep.
