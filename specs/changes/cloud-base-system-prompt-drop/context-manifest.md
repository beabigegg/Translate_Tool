# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- Cloud LLM client construction and outbound request assembly — `app/backend/clients/openai_compatible_client.py`
- Orchestrator cloud-client wiring and the `base_system_prompt` read — `app/backend/processors/orchestrator.py`
- Strategy composition and profile sourcing — `app/backend/services/translation_strategy.py`, `app/backend/translation_profiles.py`, `app/backend/services/job_manager.py`
- Other `OpenAICompatibleClient` construction sites — `app/backend/api/routes.py`, `app/backend/services/quality_judge.py`, `app/backend/services/term_extractor.py`
- Test doubles and call sites mirroring the client constructor signature
- Business rule BR-109 — `contracts/business/business-rules.md`

## Allowed Paths
- specs/changes/cloud-base-system-prompt-drop/
- specs/context/project-map.md
- specs/context/contracts-index.md
- .cdd/code-map.yml
- app/backend/clients/openai_compatible_client.py
- app/backend/clients/ollama_client.py
- app/backend/clients/base_llm_client.py
- app/backend/processors/orchestrator.py
- app/backend/services/translation_strategy.py
- app/backend/services/translation_service.py
- app/backend/services/quality_judge.py
- app/backend/services/term_extractor.py
- app/backend/services/job_manager.py
- app/backend/translation_profiles.py
- app/backend/api/routes.py
- contracts/business/business-rules.md
- contracts/CHANGELOG.md
- docs/adr/0016-context-out-of-band-system-channel.md
- tests/test_openai_compatible_client.py
- tests/test_provider_fallback.py
- tests/test_cloud_total_timeout.py
- tests/test_term_extractor.py
- tests/test_term_extractor_resilience.py
- tests/test_llm_client_protocol.py
- tests/test_ollama_client_dynamic_strategy.py
- tests/test_orchestrator_context_detection.py
- tests/test_context_prefix_bleed.py
- tests/test_fewshot_glossary.py
- tests/test_orchestrator_judge.py
- tests/conftest.py

## Required Contracts
- contracts/business/business-rules.md (BR-109 amendment: cloud client base `system_prompt` population)
- contracts/CHANGELOG.md (version bump entry)

## Required Tests
- tests/test_openai_compatible_client.py (constructor accepts and delivers `system_prompt`; outgoing-payload assertion)
- tests/test_orchestrator_context_detection.py (base prompt plus BR-109 preamble composition on the outgoing payload)
- tests/test_context_prefix_bleed.py (preamble stays last and does not replace the base)
- tests/test_ollama_client_dynamic_strategy.py (local Ollama behavior unchanged)
- tests/test_provider_fallback.py, tests/test_cloud_total_timeout.py, tests/test_term_extractor.py, tests/test_term_extractor_resilience.py, tests/test_llm_client_protocol.py (constructor call sites — 39 constructions across these six files)

## Agent Work Packets

### change-classifier
- specs/changes/cloud-base-system-prompt-drop/
- specs/context/project-map.md
- specs/context/contracts-index.md

### test-strategist
- specs/changes/cloud-base-system-prompt-drop/
- .cdd/code-map.yml
- app/backend/clients/openai_compatible_client.py
- app/backend/clients/ollama_client.py
- app/backend/processors/orchestrator.py
- app/backend/services/translation_strategy.py
- app/backend/translation_profiles.py
- tests/test_openai_compatible_client.py
- tests/test_provider_fallback.py
- tests/test_cloud_total_timeout.py
- tests/test_term_extractor.py
- tests/test_term_extractor_resilience.py
- tests/test_llm_client_protocol.py
- tests/test_ollama_client_dynamic_strategy.py
- tests/test_orchestrator_context_detection.py
- tests/test_context_prefix_bleed.py
- tests/test_fewshot_glossary.py
- tests/test_orchestrator_judge.py
- tests/conftest.py

### ci-cd-gatekeeper
- specs/changes/cloud-base-system-prompt-drop/
- tests/test_openai_compatible_client.py

### implementation-planner
- specs/changes/cloud-base-system-prompt-drop/
- .cdd/code-map.yml
- app/backend/clients/openai_compatible_client.py
- app/backend/clients/ollama_client.py
- app/backend/clients/base_llm_client.py
- app/backend/processors/orchestrator.py
- app/backend/services/translation_strategy.py
- app/backend/services/quality_judge.py
- app/backend/services/term_extractor.py
- app/backend/services/job_manager.py
- app/backend/translation_profiles.py
- app/backend/api/routes.py
- contracts/business/business-rules.md
- docs/adr/0016-context-out-of-band-system-channel.md

### bug-fix-engineer
- specs/changes/cloud-base-system-prompt-drop/
- .cdd/code-map.yml
- app/backend/clients/openai_compatible_client.py
- app/backend/clients/ollama_client.py
- app/backend/processors/orchestrator.py
- app/backend/services/translation_strategy.py
- app/backend/services/quality_judge.py
- app/backend/services/term_extractor.py
- app/backend/translation_profiles.py
- app/backend/api/routes.py
- tests/test_openai_compatible_client.py
- tests/test_provider_fallback.py
- tests/test_cloud_total_timeout.py
- tests/test_term_extractor.py
- tests/test_term_extractor_resilience.py
- tests/test_llm_client_protocol.py
- tests/test_orchestrator_context_detection.py
- tests/test_context_prefix_bleed.py
- tests/conftest.py

### contract-reviewer
- specs/changes/cloud-base-system-prompt-drop/
- contracts/business/business-rules.md
- contracts/CHANGELOG.md
- docs/adr/0016-context-out-of-band-system-channel.md

### qa-reviewer
- specs/changes/cloud-base-system-prompt-drop/
- contracts/business/business-rules.md
- tests/test_openai_compatible_client.py
- tests/test_orchestrator_context_detection.py

## Context Expansion Requests

- request-id: CER-001
  requested_paths:
    - tests/test_cloud_total_timeout.py
    - tests/test_term_extractor.py
    - tests/test_term_extractor_resilience.py
  reason: a constructor-signature change to a shared client seam predictably breaks doubles and call sites that mirror the signature, and those hide in unexpected test files (documented repo hazard). Main Claude grepped the whole tests/ tree before scaffolding and found 39 constructions across six files; these three were absent from the classifier's draft.
  status: approved
  approved-by: main-claude

- request-id: CER-002
  requested_paths:
    - .cdd/code-map.yml
  reason: to confirm the exact `OpenAICompatibleClient.__init__` signature and every downstream reader before wiring, per the "no-shell planning agents can assert nonexistent seams" rule.
  status: approved
  approved-by: main-claude

## Approved Expansions
- CER-001 — the three extra test files were added to Allowed Paths and to the test-strategist / bug-fix-engineer packets. Evidence: `grep -rl "OpenAICompatibleClient(" tests/` returns six files.
- CER-002 — `.cdd/code-map.yml` granted up front.
- Correction recorded: the classifier listed `app/backend/services/model_router.py` as a construction site, but it contains no reference to `OpenAICompatibleClient`; it is excluded. It omitted `app/backend/services/term_extractor.py` (constructs one at L570), which is included. Every path in this manifest was verified to exist on disk before it was written.
