# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- Backend PDF render/orchestration — post-render layout-QA pass (new service + orchestrator seam)
- Backend runtime configuration — `config.py` `LAYOUT_QA_ENABLED` feature flag
- Contracts: env (new flag), business (new BR above BR-105); conditionally data-shape + ci

## Allowed Paths
- specs/changes/layout-qa-safety-net/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/services/layout_qa.py
- app/backend/processors/orchestrator.py
- app/backend/processors/pdf_processor.py
- app/backend/services/job_manager.py
- app/backend/config.py
- tests/metrics/__init__.py
- tests/metrics/biou.py
- tests/metrics/residual_text.py
- tests/metrics/truncation_rate.py
- tests/test_layout_qa.py
- tests/test_env_contract.py
- tests/test_orchestrator_judge.py
- tests/test_pdf_render_warnings.py
- tests/test_layout_metrics.py
- contracts/env/env-contract.md
- contracts/env/.env.example.template
- contracts/env/env.schema.json
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- contracts/ci/ci-gate-contract.md
- docs/adr/0015-layout-qa-metric-core-in-runtime.md

Notes: `app/backend/services/layout_qa.py` and `tests/test_layout_qa.py` are NEW;
`contracts/data/data-shape-contract.md` and `contracts/ci/ci-gate-contract.md` are
conditional (touched only per the metric-hosting decision);
`tests/test_orchestrator_judge.py` is a reference pattern for the post-render
integration test.

(`tests/test_layout_qa.py` and `app/backend/services/layout_qa.py` are NEW.
The closed PR #13 branch `claude/session-uu3mpx` is a DESIGN REFERENCE ONLY and
is OUT OF SCOPE to read — no CER is issued for it.)

## Required Contracts
- contracts/env/env-contract.md (+ .env.example.template, env.schema.json)
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md (conditional)
- contracts/ci/ci-gate-contract.md (conditional)

## Required Tests
- tests/test_layout_qa.py (new — unit + data-boundary + fail-soft/resilience)
- tests/test_env_contract.py (contract: new flag)
- tests/metrics/{biou,residual_text,truncation_rate}.py (shared metric core under test)
- orchestrator integration test for the one-warning emission (new test class; pattern per tests/test_orchestrator_judge.py)

## Agent Work Packets

### spec-architect
- specs/changes/layout-qa-safety-net/
- specs/context/project-map.md
- specs/context/contracts-index.md
- contracts/business/business-rules.md
- contracts/env/env-contract.md
- contracts/data/data-shape-contract.md
- contracts/ci/ci-gate-contract.md
- tests/metrics/biou.py
- tests/metrics/residual_text.py
- tests/metrics/truncation_rate.py
- app/backend/processors/orchestrator.py
- app/backend/config.py

### implementation-planner
- specs/changes/layout-qa-safety-net/
- contracts/env/env-contract.md
- contracts/business/business-rules.md
- app/backend/processors/orchestrator.py
- app/backend/services/job_manager.py
- app/backend/config.py
- tests/metrics/biou.py
- tests/metrics/residual_text.py
- tests/metrics/truncation_rate.py

### backend-engineer
- specs/changes/layout-qa-safety-net/
- app/backend/services/layout_qa.py
- app/backend/processors/orchestrator.py
- app/backend/processors/pdf_processor.py
- app/backend/services/job_manager.py
- app/backend/config.py
- tests/metrics/__init__.py
- tests/metrics/biou.py
- tests/metrics/residual_text.py
- tests/metrics/truncation_rate.py
- tests/test_layout_qa.py
- contracts/env/.env.example.template
- contracts/env/env.schema.json

### test-strategist
- specs/changes/layout-qa-safety-net/
- tests/test_layout_qa.py
- tests/test_env_contract.py
- tests/test_orchestrator_judge.py
- tests/metrics/biou.py
- tests/metrics/residual_text.py
- tests/metrics/truncation_rate.py
- app/backend/services/layout_qa.py

### contract-reviewer
- specs/changes/layout-qa-safety-net/
- contracts/env/env-contract.md
- contracts/env/.env.example.template
- contracts/env/env.schema.json
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md

### ci-cd-gatekeeper
- specs/changes/layout-qa-safety-net/
- contracts/ci/ci-gate-contract.md
- tests/metrics/biou.py
- tests/metrics/residual_text.py
- tests/metrics/truncation_rate.py

### qa-reviewer
- specs/changes/layout-qa-safety-net/
- contracts/business/business-rules.md
- contracts/env/env-contract.md

## Context Expansion Requests
- request-id: CER-001
  requested_paths:
    - app/backend/renderers/fitz_renderer.py
    - app/backend/renderers/pdf_generator.py
  reason: If backend-engineer/spec-architect needs the exact PDF post-render seam (output-file handle, existing BR-104 sweep call site) and it is not fully resolvable from orchestrator.py + pdf_processor.py, these renderer entry points define where the output PDF is finalized. Not authorized until the seam is confirmed unresolvable from the allowed orchestrator/processor files.
  status: pending
- request-id: CER-002
  requested_paths:
    - app/backend/models/translatable_document.py
  reason: If the data-shape warning note (conditional) requires the JobRecord/warnings field definition to describe the aggregated layout-QA warning entry. Only if the data-shape contract edit is confirmed needed.
  status: pending
