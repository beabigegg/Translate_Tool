# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- Backend translation pipeline — critique-loop QE (COMET) scoring gate
  (`services/translation_service.py`), and the batched scoring service
  (`services/quality_evaluator.py`)

## Allowed Paths
<!-- UNION of all repo-relative paths (or globs) any agent may read for this change.
     cdd-kit gate validates every agent's files-read log against this list.
     If an agent legitimately read a path, add that path here; do not remove it
     from files-read just to pass gate.
     Be specific — wide globs (e.g. src/) defeat read-scope governance.
     Always include the three defaults below; add change-specific paths beneath them. -->
- specs/changes/batch-critique-qe-scoring/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/services/translation_service.py
- app/backend/services/quality_evaluator.py
- app/backend/config.py
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- contracts/CHANGELOG.md
- tests/test_critique_gate.py
- tests/test_quality_evaluation.py
- tests/test_critique_loop_batching.py
- tests/test_fewshot_glossary.py
- tests/test_glossary_enforcement.py

## Required Contracts
- contracts/business/business-rules.md (read-only; verify adoption-rule invariant, no change expected)

## Required Tests
- tests/test_critique_gate.py (candidate — critique gate / adoption)
- tests/test_quality_evaluation.py (candidate — score_blocks / QE + OOM ladder)

## Agent Work Packets
<!-- One sub-section per required agent. Each path list must be a subset of Allowed Paths above.
     Add or remove sub-sections to match Required Agents in change-classification.md.
     These sub-sections are documentation only — gate enforces Allowed Paths, not individual packets. -->

### change-classifier
- specs/changes/batch-critique-qe-scoring/
- specs/context/project-map.md
- specs/context/contracts-index.md

### implementation-planner
- specs/changes/batch-critique-qe-scoring/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/services/translation_service.py
- app/backend/services/quality_evaluator.py
- app/backend/config.py

### contract-reviewer
- specs/changes/batch-critique-qe-scoring/
- contracts/business/business-rules.md
- app/backend/services/translation_service.py
- app/backend/services/quality_evaluator.py

### test-strategist
- specs/changes/batch-critique-qe-scoring/
- app/backend/services/translation_service.py
- app/backend/services/quality_evaluator.py
- tests/test_critique_gate.py
- tests/test_quality_evaluation.py

### backend-engineer (deferred — not run this pass)
- specs/changes/batch-critique-qe-scoring/
- app/backend/services/translation_service.py
- app/backend/services/quality_evaluator.py
- app/backend/config.py
- tests/test_critique_gate.py
- tests/test_quality_evaluation.py

### e2e-resilience-engineer (deferred — not run this pass)
- specs/changes/batch-critique-qe-scoring/
- app/backend/services/translation_service.py
- app/backend/services/quality_evaluator.py
- tests/test_critique_gate.py
- tests/test_quality_evaluation.py

### qa-reviewer (deferred — not run this pass)
- specs/changes/batch-critique-qe-scoring/
- tests/test_critique_gate.py
- tests/test_quality_evaluation.py

## Context Expansion Requests
- request-id: CER-001
  requested_paths:
    - .github/workflows/contract-driven-gates.yml
  reason: ci-cd-gatekeeper needs to read the existing CI gate contract and workflow file to confirm no new gate is required and existing gates already cover tests/test_critique_gate.py and tests/test_quality_evaluation.py
  status: approved
- request-id: CER-002
  requested_paths:
    - tests/test_fewshot_glossary.py
    - tests/test_glossary_enforcement.py
  reason: The round-based refactor routes adoption through the new `_batched_critique_adopt` instead of `_critique_gate_adopt`, orphaning a mock in `tests/test_fewshot_glossary.py::test_revised_draft_recorded_in_tmap` that patched `_critique_gate_adopt` directly (it then ran the real COMET path and flipped its assertion). A one-line mechanical mock retarget to `_batched_critique_adopt` is required to keep the suite green — a refactor-caused, no-production-behavior test fix. `tests/test_glossary_enforcement.py` is the mocking-pattern reference cited by test-plan.md Notes. Approved (main-Claude orchestrator) as in-scope-by-necessity.
  status: approved
## Approved Expansions
- .github/workflows/contract-driven-gates.yml
- contracts/ci/ci-gate-contract.md
- tests/test_fewshot_glossary.py
- tests/test_glossary_enforcement.py
