# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

Explicitly forbidden: `docs/TEST_DOC/` — no agent may read it and no test may
depend on it.

## Affected Surfaces
- Cloud LLM client (OpenAI-compatible / PANJIT `gpt-oss:120b`) — request
  composition, wall-clock timeout, embedding path
- Translation service critique loop (`CRITIQUE_LOOP_ENABLED`)
- Backend config constants

## Allowed Paths
- specs/changes/cloud-reasoning-stall-hardening/
- specs/context/project-map.md
- specs/context/contracts-index.md
- .github/workflows/contract-driven-gates.yml
- app/backend/clients/openai_compatible_client.py
- app/backend/clients/base_llm_client.py
- app/backend/config.py
- app/backend/services/translation_service.py
- app/backend/services/translation_strategy.py
- app/backend/services/context_prompts.py
- app/backend/processors/orchestrator.py
- contracts/business/business-rules.md
- contracts/env/env-contract.md
- contracts/env/.env.example.template
- docs/adr/
- docs/adr/0011-cloud-llm-total-timeout-and-cancellable-post.md
- docs/adr/0016-context-out-of-band-system-channel.md
- docs/adr/0017-json-structured-translation-seam.md
- tests/test_openai_compatible_client.py
- tests/test_cloud_total_timeout.py
- tests/test_orchestrator_context_detection.py
- tests/test_context_prefix_bleed.py
- tests/test_critique_loop_batching.py
- tests/test_critique_gate.py
- tests/test_json_translation_prompt.py
- tests/test_json_translation_body.py
- tests/test_fewshot_glossary.py
- tests/conftest.py

## Required Contracts
- contracts/business/business-rules.md (BR-100, BR-109, critique policy)
- docs/adr/0011-cloud-llm-total-timeout-and-cancellable-post.md
- docs/adr/0016-context-out-of-band-system-channel.md
- contracts/env/env-contract.md + contracts/env/.env.example.template (conditional
  — verify OPENAI_TOTAL_TIMEOUT_SECONDS is env-documented)

## Required Tests
- tests/test_openai_compatible_client.py
- tests/test_cloud_total_timeout.py
- tests/test_orchestrator_context_detection.py
- tests/test_context_prefix_bleed.py
- tests/test_critique_loop_batching.py
- tests/test_critique_gate.py

## Agent Work Packets

### spec-architect
- specs/changes/cloud-reasoning-stall-hardening/
- contracts/business/business-rules.md
- docs/adr/
- docs/adr/0011-cloud-llm-total-timeout-and-cancellable-post.md
- docs/adr/0016-context-out-of-band-system-channel.md
- docs/adr/0017-json-structured-translation-seam.md
- contracts/env/env-contract.md

### contract-reviewer
- specs/changes/cloud-reasoning-stall-hardening/
- contracts/business/business-rules.md
- contracts/env/env-contract.md
- contracts/env/.env.example.template
- docs/adr/
- docs/adr/0011-cloud-llm-total-timeout-and-cancellable-post.md
- docs/adr/0016-context-out-of-band-system-channel.md

### test-strategist
- specs/changes/cloud-reasoning-stall-hardening/
- tests/test_openai_compatible_client.py
- tests/test_cloud_total_timeout.py
- tests/test_orchestrator_context_detection.py
- tests/test_context_prefix_bleed.py
- tests/test_critique_loop_batching.py
- tests/test_critique_gate.py
- app/backend/clients/openai_compatible_client.py
- app/backend/config.py

### ci-cd-gatekeeper
- specs/changes/cloud-reasoning-stall-hardening/

### implementation-planner
- specs/changes/cloud-reasoning-stall-hardening/
- app/backend/clients/openai_compatible_client.py
- app/backend/clients/base_llm_client.py
- app/backend/config.py
- app/backend/services/translation_service.py
- app/backend/services/translation_strategy.py
- app/backend/services/context_prompts.py
- app/backend/processors/orchestrator.py
- contracts/business/business-rules.md
- docs/adr/0011-cloud-llm-total-timeout-and-cancellable-post.md
- docs/adr/0016-context-out-of-band-system-channel.md

### backend-engineer
- specs/changes/cloud-reasoning-stall-hardening/
- app/backend/clients/openai_compatible_client.py
- app/backend/clients/base_llm_client.py
- app/backend/config.py
- app/backend/services/translation_service.py
- app/backend/services/translation_strategy.py
- app/backend/services/context_prompts.py
- app/backend/processors/orchestrator.py
- tests/test_openai_compatible_client.py
- tests/test_cloud_total_timeout.py
- tests/test_orchestrator_context_detection.py
- tests/test_context_prefix_bleed.py
- tests/test_critique_loop_batching.py
- tests/test_critique_gate.py
- tests/test_json_translation_prompt.py
- tests/test_json_translation_body.py
- tests/test_fewshot_glossary.py
- tests/conftest.py

### e2e-resilience-engineer
- specs/changes/cloud-reasoning-stall-hardening/
- app/backend/clients/openai_compatible_client.py
- app/backend/clients/base_llm_client.py
- app/backend/config.py
- tests/test_cloud_total_timeout.py
- tests/test_openai_compatible_client.py

### qa-reviewer
- specs/changes/cloud-reasoning-stall-hardening/
- contracts/business/business-rules.md

## Context Expansion Requests
- request-id: CER-1
  requested_paths:
    - .github/workflows/contract-driven-gates.yml
  reason: ci-cd-gatekeeper needs to align new gate table job names with existing PR-required jobs (contract-and-fast-tests, full-regression, golden-sample-regression, renderer-equivalence) for this Tier-1 backend-only change riding existing gates
  status: approved
## Approved Expansions
- .github/workflows/contract-driven-gates.yml
