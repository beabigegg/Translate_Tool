# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- QA / LLM-judge quality loop (`quality_judge.py:run_judge_loop`/`_run_judge_loop_impl`)
- Job lifecycle / cancellation (`job_manager.py` `stop_flag`, `cancel_job`, judge call-site `_translate_fn`)
- Cloud LLM client transport / timeout semantics (`openai_compatible_client.py`, `base_llm_client.py`)
- Runtime config (timeout ceiling env/config)

## Allowed Paths
- specs/changes/qa-judge-hang-recovery/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/services/quality_judge.py
- app/backend/services/job_manager.py
- app/backend/clients/openai_compatible_client.py
- app/backend/clients/base_llm_client.py
- app/backend/clients/ollama_client.py
- app/backend/config.py
- app/backend/services/translation_service.py
- app/backend/services/model_router.py
- contracts/business/business-rules.md
- contracts/env/env-contract.md
- contracts/env/.env.example.template
- contracts/env/env.schema.json
- contracts/data/data-shape-contract.md
- contracts/api/api-contract.md
- tests/test_orchestrator_judge.py
- tests/test_judge_api.py
- tests/test_judge_apply.py
- tests/test_job_record_judge.py
- tests/test_openai_compatible_client.py
- tests/test_llm_client_protocol.py
- tests/test_model_router.py
- tests/test_provider_fallback.py
- tests/test_quality_judge.py
- tests/test_env_contract.py

## Required Contracts
- contracts/business/business-rules.md (BR-73 iteration cap, BR-74 graceful degradation — extend for cancel/timeout)
- contracts/env/env-contract.md, contracts/env/.env.example.template, contracts/env/env.schema.json (wall-clock ceiling config, if chosen)
- contracts/data/data-shape-contract.md (only if a new `cancelled` judge state is added)
- contracts/api/api-contract.md (only if a new judge_status value surfaces in `GET /jobs/{id}/judge`)

## Required Tests
- tests/test_orchestrator_judge.py, tests/test_judge_api.py, tests/test_judge_apply.py, tests/test_job_record_judge.py
- tests/test_openai_compatible_client.py, tests/test_llm_client_protocol.py
- tests/test_model_router.py, tests/test_provider_fallback.py
- tests/test_quality_judge.py, tests/test_env_contract.py
- tests/test_cloud_total_timeout.py (new — dribbling/keep-alive mock server fixture, no existing precedent in this repo)

## Agent Work Packets

### change-classifier
- specs/changes/qa-judge-hang-recovery/
- specs/context/project-map.md
- specs/context/contracts-index.md

### spec-architect
- specs/changes/qa-judge-hang-recovery/
- app/backend/services/quality_judge.py
- app/backend/services/job_manager.py
- app/backend/clients/openai_compatible_client.py
- app/backend/clients/base_llm_client.py
- app/backend/config.py
- contracts/business/business-rules.md
- contracts/env/env-contract.md
- contracts/data/data-shape-contract.md

### contract-reviewer
- specs/changes/qa-judge-hang-recovery/
- contracts/business/business-rules.md
- contracts/env/env-contract.md
- contracts/env/.env.example.template
- contracts/env/env.schema.json
- contracts/data/data-shape-contract.md
- contracts/api/api-contract.md

### implementation-planner
- specs/changes/qa-judge-hang-recovery/
- app/backend/services/quality_judge.py
- app/backend/services/job_manager.py
- app/backend/clients/openai_compatible_client.py
- app/backend/clients/base_llm_client.py
- app/backend/config.py
- app/backend/services/translation_service.py
- app/backend/services/model_router.py
- contracts/business/business-rules.md
- contracts/env/env-contract.md

### test-strategist
- specs/changes/qa-judge-hang-recovery/
- tests/test_orchestrator_judge.py
- tests/test_judge_api.py
- tests/test_judge_apply.py
- tests/test_job_record_judge.py
- tests/test_openai_compatible_client.py
- tests/test_llm_client_protocol.py
- tests/test_model_router.py
- tests/test_provider_fallback.py

### qa-reviewer
- specs/changes/qa-judge-hang-recovery/
- contracts/business/business-rules.md
- contracts/env/env-contract.md

## Context Expansion Requests
- request-id: CER-001
  requested_paths:
    - specs/changes/qa-judge-provider-consistency/implementation-plan.md
    - specs/changes/qa-judge-provider-consistency/tasks.yml
  reason: depends-on sibling edits the SAME regions (`job_manager.py` `_translate_fn` ~L493-510 and `quality_judge.py:run_judge_loop`). spec-architect and implementation-planner would ideally read its planned edit region to sequence edits and avoid a guaranteed merge conflict.
  status: rejected — `.cdd/context-policy.json`'s `forbiddenPaths` baseline lists `specs/changes/*` as a HARD, non-overridable block (distinct from the soft CER-approval mechanism used for paths like `config/providers.yml`). No CER can approve a cross-change `specs/changes/` read, regardless of dependency relationship. Main Claude briefs spec-architect/implementation-planner directly, in-prompt, with `qa-judge-provider-consistency`'s actual finalized design decisions instead.
- request-id: CER-002
  requested_paths:
    - specs/changes/translation-progress-detail-ui/implementation-plan.md
  reason: it added an additive optional `snapshot_cb` param to `run_judge_loop` this session; the cancellation guard must not conflict with that signature.
  status: rejected — same hard-forbidden-paths reason as CER-001. Main Claude briefs agents in-prompt with the relevant `snapshot_cb` signature detail instead.

## Approved Expansions
-
