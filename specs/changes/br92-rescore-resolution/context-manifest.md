# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- QE post-job scoring / rescore gate (mechanism (b) in the QA-pipeline audit)
- Business-rules contract (BR-92)
- Env contract + schema + template (`QE_RESCORE_THRESHOLD`)
- Config feature flags (`config.py`)

## Allowed Paths
- specs/changes/br92-rescore-resolution/
- specs/context/project-map.md
- specs/context/contracts-index.md
- contracts/business/business-rules.md
- contracts/env/env-contract.md
- contracts/env/.env.example.template
- contracts/env/env.schema.json
- app/backend/config.py
- app/backend/services/job_manager.py
- app/backend/services/quality_evaluator.py
- app/backend/services/translation_service.py
- app/backend/services/quality_judge.py
- tests/test_quality_evaluation.py
- tests/test_env_contract.py
- contracts/data/data-shape-contract.md

(`translation_service.py`, `quality_judge.py`, and BR-55/56/72-77/89/90 are
read-only contrast/non-goal references to confirm scope boundaries, not
modification targets.)

## Required Contracts
- contracts/business/business-rules.md
- contracts/env/env-contract.md
- contracts/env/.env.example.template
- contracts/env/env.schema.json

## Required Tests
- tests/test_quality_evaluation.py
- tests/test_env_contract.py

## Agent Work Packets

### change-classifier
- specs/changes/br92-rescore-resolution/
- specs/context/project-map.md
- specs/context/contracts-index.md

### spec-architect
- specs/changes/br92-rescore-resolution/
- contracts/business/business-rules.md
- contracts/env/env-contract.md
- app/backend/config.py
- app/backend/services/job_manager.py
- app/backend/services/quality_evaluator.py
- app/backend/services/translation_service.py
- app/backend/services/quality_judge.py
- tests/test_quality_evaluation.py
- tests/test_env_contract.py

### implementation-planner
- specs/changes/br92-rescore-resolution/
- contracts/business/business-rules.md
- contracts/env/env-contract.md
- contracts/env/.env.example.template
- contracts/env/env.schema.json
- contracts/data/data-shape-contract.md
- app/backend/config.py
- app/backend/services/job_manager.py
- app/backend/services/quality_evaluator.py
- tests/test_quality_evaluation.py
- tests/test_env_contract.py

### contract-reviewer
- specs/changes/br92-rescore-resolution/
- contracts/business/business-rules.md
- contracts/env/env-contract.md
- contracts/env/.env.example.template
- contracts/env/env.schema.json

### test-strategist
- specs/changes/br92-rescore-resolution/
- tests/test_quality_evaluation.py
- tests/test_env_contract.py
- contracts/business/business-rules.md
- contracts/env/env-contract.md

### qa-reviewer
- specs/changes/br92-rescore-resolution/
- contracts/business/business-rules.md
- contracts/env/env-contract.md

## Context Expansion Requests
- request-id: CER-001
  requested_paths:
    - contracts/data/data-shape-contract.md
  reason: spec-architect found `data-shape-contract.md:787` falsely claims BR-92 is "wired in job_manager.py post-translate hook, CER-002" — a second stale artifact not caught by the original classifier scan. Whichever direction (build/retire) is chosen, this line must be corrected too.
  status: approved

## Approved Expansions
- contracts/data/data-shape-contract.md
