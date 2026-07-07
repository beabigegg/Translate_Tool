# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- Backend job-status API surface (api/routes.py, api/schemas.py)
- Backend job lifecycle / state store (services/job_manager.py — JobRecord)
- Backend translation pipeline hot path (services/translation_service.py
  critique/QE loop; possibly services/translation_strategy.py)
- Frontend job polling + progress display (hooks/, pages/, components/, api/, i18n/)
- Contracts: API, CSS/UI, business (ETA), possibly data-shape

## Allowed Paths
<!-- UNION of all repo-relative paths (or globs) any agent may read for this change.
     cdd-kit gate validates every agent's files-read log against this list.
     If an agent legitimately read a path, add that path here; do not remove it
     from files-read just to pass gate.
     Be specific — wide globs (e.g. src/) defeat read-scope governance.
     Always include the three defaults below; add change-specific paths beneath them. -->
- specs/changes/translation-progress-detail-ui/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/api/routes.py
- app/backend/api/schemas.py
- app/backend/services/job_manager.py
- app/backend/services/translation_service.py
- app/backend/services/translation_strategy.py
- app/backend/config.py
- app/frontend/src/hooks/
- app/frontend/src/pages/
- app/frontend/src/components/
- app/frontend/src/api/
- app/frontend/src/i18n/
- contracts/api/api-contract.md
- contracts/api/openapi.yml
- contracts/api/openapi.json
- contracts/api/api-inventory.md
- contracts/css/css-contract.md
- contracts/css/design-tokens.md
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- tests/test_jobstatus_download_url.py
- tests/contract/
- specs/changes/batch-critique-qe-scoring/change-request.md
- specs/changes/batch-critique-qe-scoring/implementation-plan.md
- app/backend/services/quality_judge.py

## Required Contracts
- contracts/api/api-contract.md (+ regenerated openapi.yml/openapi.json)
- contracts/css/css-contract.md
- contracts/css/design-tokens.md
- contracts/business/business-rules.md (ETA heuristic — if contract-governed)
- contracts/data/data-shape-contract.md (only if job-status schema documented there)

## Required Tests
- tests/test_jobstatus_download_url.py (existing job-status shape test — extend/reference)
- tests/contract/ (additive-compat + OpenAPI conformance)
- New backend unit/integration tests for current-segment capture + ETA (path TBD)
- New frontend component tests (path TBD)

## Agent Work Packets
<!-- One sub-section per required agent. Each path list must be a subset of Allowed Paths above.
     Add or remove sub-sections to match Required Agents in change-classification.md.
     These sub-sections are documentation only — gate enforces Allowed Paths, not individual packets. -->

### change-classifier
- specs/changes/translation-progress-detail-ui/
- specs/context/project-map.md
- specs/context/contracts-index.md

### spec-architect
- specs/changes/translation-progress-detail-ui/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/api/schemas.py
- app/backend/services/job_manager.py
- app/backend/services/translation_service.py
- app/backend/services/quality_judge.py
- contracts/api/api-contract.md
- contracts/css/css-contract.md
- contracts/business/business-rules.md
- app/frontend/src/hooks/

### implementation-planner
- specs/changes/translation-progress-detail-ui/
- app/backend/api/routes.py
- app/backend/api/schemas.py
- app/backend/services/job_manager.py
- app/backend/services/translation_service.py
- app/backend/services/translation_strategy.py
- app/backend/services/quality_judge.py
- app/frontend/src/hooks/
- app/frontend/src/pages/
- app/frontend/src/components/
- app/frontend/src/api/
- app/frontend/src/i18n/
- contracts/api/api-contract.md
- contracts/css/css-contract.md
- specs/changes/batch-critique-qe-scoring/change-request.md
- specs/changes/batch-critique-qe-scoring/implementation-plan.md

### test-strategist
- specs/changes/translation-progress-detail-ui/
- tests/test_jobstatus_download_url.py
- tests/contract/
- app/backend/api/schemas.py
- app/backend/services/job_manager.py
- app/backend/services/quality_judge.py

### backend-engineer (deferred — not run this pass)
- specs/changes/translation-progress-detail-ui/
- app/backend/api/routes.py
- app/backend/api/schemas.py
- app/backend/services/job_manager.py
- app/backend/services/translation_service.py
- app/backend/services/translation_strategy.py
- app/backend/config.py
- contracts/api/api-contract.md
- contracts/api/openapi.yml
- contracts/api/openapi.json
- tests/

### frontend-engineer (deferred — not run this pass)
- specs/changes/translation-progress-detail-ui/
- app/frontend/src/hooks/
- app/frontend/src/pages/
- app/frontend/src/components/
- app/frontend/src/api/
- app/frontend/src/i18n/
- contracts/css/css-contract.md
- contracts/css/design-tokens.md

### contract-reviewer / ui-ux-reviewer / visual-reviewer / qa-reviewer (deferred — not run this pass)
- specs/changes/translation-progress-detail-ui/
- contracts/

## Context Expansion Requests
- request-id: CER-001
  requested_paths:
    - app/frontend/src/pages/*
    - app/frontend/src/components/**
    - app/frontend/src/hooks/*
    - app/frontend/src/api/*
    - app/frontend/src/i18n/*
  reason: project-map.md truncates all app/frontend/src/ subdirectories at max
  status: approved

- request-id: CER-002
  requested_paths:
    - specs/changes/batch-critique-qe-scoring/change-request.md
    - specs/changes/batch-critique-qe-scoring/implementation-plan.md
  reason: Both changes edit the translation_service.py critique-loop region.
  status: approved

- request-id: CER-003
  requested_paths:
    - .github/workflows/contract-driven-gates.yml
  reason: ci-cd-gatekeeper needs to read the existing CI gate contract and workflow file to confirm gate coverage for the new backend/frontend test files and the api-contract.md/openapi export-check + validate_contract_versions.py gates
  status: approved

- request-id: CER-004
  requested_paths:
    - app/backend/services/quality_judge.py
  reason: Scope amendment (post-planning) — a live incident showed the original design's exclusion of the judge phase from current_stage/ETA left users blind during a real judge-phase hang. spec-architect/test-strategist/implementation-planner must read quality_judge.py's run_judge_loop/_run_judge_loop_impl to fold the judge phase into the stage snapshot and BR-98 ETA formula.
  status: approved
## Approved Expansions
- app/backend/services/quality_judge.py
- .github/workflows/contract-driven-gates.yml
- app/frontend/src/api/*
- app/frontend/src/components/**
- app/frontend/src/hooks/*
- app/frontend/src/i18n/*
- app/frontend/src/pages/*
- contracts/ci/ci-gate-contract.md
- specs/changes/batch-critique-qe-scoring/change-request.md
- specs/changes/batch-critique-qe-scoring/implementation-plan.md
