# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- Backend judge / QA re-translation loop (`app/backend/services/job_manager.py`, `app/backend/services/quality_judge.py`) and the `config.py`/`clients/` provider-construction plumbing it reuses.

## Allowed Paths
- specs/changes/qa-judge-provider-consistency/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/services/job_manager.py
- app/backend/services/quality_judge.py
- app/backend/config.py
- app/backend/services/model_router.py
- app/backend/clients/openai_compatible_client.py
- app/backend/clients/ollama_client.py
- app/backend/clients/base_llm_client.py
- config/providers.yml.example
- config/providers.yml
- contracts/business/business-rules.md
- contracts/env/env-contract.md
- tests/test_orchestrator_judge.py
- tests/test_judge_api.py
- tests/test_judge_apply.py
- tests/test_job_record_judge.py
- tests/test_provider_fallback.py
- tests/test_openai_compatible_client.py
- tests/test_model_router.py
- tests/test_quality_judge.py

## Required Contracts
- contracts/business/business-rules.md (new/extended provider-consistency rule)
- contracts/env/env-contract.md (review-only; `JUDGE_CLOUD_PROVIDER_ID` already inventoried)

## Required Tests
- tests/test_orchestrator_judge.py
- tests/test_judge_api.py
- tests/test_judge_apply.py
- tests/test_job_record_judge.py
- tests/test_provider_fallback.py
- tests/test_openai_compatible_client.py
- tests/test_quality_judge.py

## Agent Work Packets

### change-classifier
- specs/changes/qa-judge-provider-consistency/
- specs/context/project-map.md
- specs/context/contracts-index.md

### spec-architect
- specs/changes/qa-judge-provider-consistency/
- app/backend/services/job_manager.py
- app/backend/services/quality_judge.py
- app/backend/config.py
- app/backend/services/model_router.py
- app/backend/clients/openai_compatible_client.py
- app/backend/clients/ollama_client.py
- app/backend/clients/base_llm_client.py
- config/providers.yml.example
- config/providers.yml
- contracts/business/business-rules.md
- contracts/env/env-contract.md

### contract-reviewer
- specs/changes/qa-judge-provider-consistency/
- contracts/business/business-rules.md
- contracts/env/env-contract.md

### implementation-planner
- specs/changes/qa-judge-provider-consistency/
- app/backend/services/job_manager.py
- app/backend/services/quality_judge.py
- app/backend/config.py
- app/backend/clients/openai_compatible_client.py
- app/backend/clients/ollama_client.py
- contracts/business/business-rules.md
- tests/test_quality_judge.py

### test-strategist
- specs/changes/qa-judge-provider-consistency/
- app/backend/services/job_manager.py
- app/backend/services/quality_judge.py
- tests/test_quality_judge.py
- tests/test_orchestrator_judge.py
- tests/test_judge_api.py
- tests/test_judge_apply.py
- tests/test_job_record_judge.py
- tests/test_provider_fallback.py
- tests/test_openai_compatible_client.py

### qa-reviewer
- specs/changes/qa-judge-provider-consistency/
- contracts/business/business-rules.md
- contracts/env/env-contract.md

## Context Expansion Requests
- request-id: CER-001
  requested_paths:
    - config/providers.yml
  reason: The Open Questions in change-request.md turn on whether the `panjit` entry has separate "judge" vs "translate" model definitions or a single endpoint with a per-call model. Only `config/providers.yml.example` is index-tracked; the runtime `config/providers.yml` (gitignored) may hold the real shape spec-architect needs to decide reuse-vs-distinct-client.
  status: approved

## Approved Expansions
- config/providers.yml
