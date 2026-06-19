# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- Backend terminology audit (new `services/term_audit.py`)
- Post-translate orchestration seam (post_translate_hook pattern)
- Job-level qa-report / audit data shape
- Business rules: terminology hit-rate audit

## Allowed Paths
- specs/changes/p2-term-audit/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/services/term_audit.py
- app/backend/services/term_db.py
- app/backend/models/term.py
- app/backend/services/job_manager.py
- app/backend/services/translation_service.py
- app/backend/services/quality_evaluator.py
- app/backend/processors/orchestrator.py
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- tests/test_term_audit.py
- tests/test_term_db.py
- tests/test_term_state_machine.py
- tests/test_term_api.py
- tests/test_quality_evaluation.py
- tests/test_translation_strategy.py
- .github/workflows/contract-driven-gates.yml
- contracts/ci/ci-gate-contract.md

## Required Contracts
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md

## Required Tests
- tests/test_term_audit.py (NEW — primary)
- tests/test_term_db.py (reference for term-state fixtures)
- tests/test_quality_evaluation.py (reference: post_translate_hook test pattern)

## Agent Work Packets

### spec-architect
- specs/changes/p2-term-audit/
- app/backend/services/quality_evaluator.py
- app/backend/services/translation_service.py
- app/backend/processors/orchestrator.py
- app/backend/services/term_db.py
- app/backend/models/term.py
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md

### contract-reviewer
- specs/changes/p2-term-audit/
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- specs/context/contracts-index.md

### test-strategist
- specs/changes/p2-term-audit/
- tests/test_term_audit.py
- tests/test_term_db.py
- tests/test_quality_evaluation.py
- app/backend/services/term_audit.py
- app/backend/services/term_db.py
- app/backend/models/term.py

### ci-cd-gatekeeper
- specs/changes/p2-term-audit/
- .github/workflows/contract-driven-gates.yml
- contracts/ci/ci-gate-contract.md

### implementation-planner
- specs/changes/p2-term-audit/
- app/backend/services/term_db.py
- app/backend/models/term.py
- app/backend/services/quality_evaluator.py
- app/backend/processors/orchestrator.py

### backend-engineer
- specs/changes/p2-term-audit/
- app/backend/services/term_audit.py
- app/backend/services/term_db.py
- app/backend/models/term.py
- app/backend/services/translation_service.py
- app/backend/services/quality_evaluator.py
- app/backend/processors/orchestrator.py
- tests/test_term_audit.py
- tests/test_quality_evaluation.py
- tests/test_term_db.py

### qa-reviewer
- specs/changes/p2-term-audit/
- tests/test_term_audit.py
- app/backend/services/term_audit.py
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md

## Context Expansion Requests
-

## Approved Expansions
-
