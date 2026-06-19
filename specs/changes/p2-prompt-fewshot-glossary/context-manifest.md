# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- LLM prompt construction (few-shot + glossary injection)
- Translation orchestration / self-refinement control flow
- Glossary / term subsystem (read path)
- Translation cache keying
- Metrics / observability for quality
- Business-rules contract (terminology-match guarantee, loop policy)

## Allowed Paths
- specs/changes/p2-prompt-fewshot-glossary/
- specs/context/project-map.md
- specs/context/contracts-index.md
- contracts/business/business-rules.md
- contracts/api/api-contract.md
- contracts/api/api-inventory.md
- contracts/data/data-shape-contract.md
- app/backend/services/context_prompts.py
- app/backend/services/translation_service.py
- app/backend/services/translation_strategy.py
- app/backend/services/term_db.py
- app/backend/services/term_extractor.py
- app/backend/services/model_router.py
- app/backend/services/translation_cache.py
- app/backend/services/job_manager.py
- app/backend/services/metrics.py
- app/backend/clients/base_llm_client.py
- app/backend/clients/ollama_client.py
- app/backend/clients/openai_compatible_client.py
- app/backend/models/term.py
- app/backend/translation_profiles.py
- app/backend/config.py
- tests/test_context_prompt_i18n.py
- tests/test_hy_mt_quality_refinement.py
- tests/test_translation_strategy.py
- tests/test_term_db.py
- tests/test_term_extractor.py
- tests/test_term_api.py
- tests/test_translation_profiles_scenarios.py
- tests/test_golden_regression.py
- tests/test_metrics_counters.py
- tests/test_metrics_endpoint.py
- .github/workflows/contract-driven-gates.yml

## Required Contracts
- contracts/business/business-rules.md (required — 100% glossary-match guarantee + critique-loop policy)
- contracts/api/api-contract.md (conditional — read-only unless response shape changes)
- contracts/data/data-shape-contract.md (conditional — read-only unless term IR gains fields)

## Required Tests
- tests/test_hy_mt_quality_refinement.py
- tests/test_golden_regression.py
- tests/test_context_prompt_i18n.py
- tests/test_translation_strategy.py

## Agent Work Packets

### spec-architect
- specs/changes/p2-prompt-fewshot-glossary/
- specs/context/project-map.md
- specs/context/contracts-index.md
- contracts/business/business-rules.md
- contracts/api/api-contract.md
- contracts/data/data-shape-contract.md
- app/backend/services/context_prompts.py
- app/backend/services/translation_service.py
- app/backend/services/translation_strategy.py
- app/backend/services/translation_cache.py
- app/backend/services/model_router.py
- app/backend/services/job_manager.py

### implementation-planner
- specs/changes/p2-prompt-fewshot-glossary/
- specs/context/project-map.md
- contracts/business/business-rules.md
- app/backend/services/context_prompts.py
- app/backend/services/translation_service.py
- app/backend/services/translation_strategy.py
- app/backend/services/term_db.py
- app/backend/services/metrics.py

### backend-engineer
- specs/changes/p2-prompt-fewshot-glossary/
- app/backend/services/context_prompts.py
- app/backend/services/translation_service.py
- app/backend/services/translation_strategy.py
- app/backend/services/term_db.py
- app/backend/services/term_extractor.py
- app/backend/services/model_router.py
- app/backend/services/translation_cache.py
- app/backend/services/job_manager.py
- app/backend/services/metrics.py
- app/backend/clients/base_llm_client.py
- app/backend/clients/ollama_client.py
- app/backend/clients/openai_compatible_client.py
- app/backend/models/term.py
- app/backend/translation_profiles.py
- app/backend/config.py

### test-strategist
- specs/changes/p2-prompt-fewshot-glossary/
- tests/test_context_prompt_i18n.py
- tests/test_hy_mt_quality_refinement.py
- tests/test_translation_strategy.py
- tests/test_term_db.py
- tests/test_term_extractor.py
- tests/test_translation_profiles_scenarios.py
- tests/test_golden_regression.py
- tests/test_metrics_counters.py
- tests/test_metrics_endpoint.py

### contract-reviewer
- specs/changes/p2-prompt-fewshot-glossary/
- contracts/business/business-rules.md
- contracts/api/api-contract.md
- contracts/api/api-inventory.md
- contracts/data/data-shape-contract.md

### ci-cd-gatekeeper
- specs/changes/p2-prompt-fewshot-glossary/
- .github/workflows/contract-driven-gates.yml

### qa-reviewer
- specs/changes/p2-prompt-fewshot-glossary/
- contracts/business/business-rules.md
- tests/test_hy_mt_quality_refinement.py
- tests/test_golden_regression.py

## Context Expansion Requests

- request-id: CER-001
  requested_paths:
    - contracts/business/business-rules.md
  reason: spec-architect and contract-reviewer must read the full file to add/update the 100%-match guarantee and loop policy without duplicating or contradicting existing rules.
  status: approved

- request-id: CER-002
  requested_paths:
    - app/backend/services/translation_cache.py
    - app/backend/services/job_manager.py
  reason: Confirming cache-key and per-request loop-cost handling is required to satisfy AC-5/AC-6; must be inspected by spec-architect/backend-engineer to design the cache-key change and loop bound.
  status: approved

## Approved Expansions
- CER-001 approved: contracts/business/business-rules.md included for spec-architect and contract-reviewer.
- CER-002 approved: translation_cache.py and job_manager.py included for spec-architect and backend-engineer.
