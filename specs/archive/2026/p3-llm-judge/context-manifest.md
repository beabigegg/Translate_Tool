# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- Backend service layer (`app/backend/services/quality_judge.py` — new)
- Pipeline orchestration (`app/backend/processors/orchestrator.py` — judge hook + re-translation loop)
- Job lifecycle / data shape (`app/backend/services/job_manager.py`, `app/backend/api/schemas.py`)
- Translation invocation (`app/backend/services/translation_service.py`, `app/backend/services/model_router.py`)
- LLM client (`app/backend/clients/ollama_client.py`)
- API (`app/backend/api/routes.py`, `app/backend/api/schemas.py` — new endpoint)
- Config (`app/backend/config.py` — feature flag, Gemma model name)
- Frontend (`app/frontend/src/pages/TranslatePage.jsx`, `app/frontend/src/api/jobs.js` — job detail judge panel)
- Contracts: api, data-shape, business-rules, env, css

## Allowed Paths
- specs/changes/p3-llm-judge/
- specs/context/project-map.md
- specs/context/contracts-index.md
- contracts/api/api-contract.md
- contracts/api/api-inventory.md
- contracts/api/openapi.yml
- contracts/api/openapi.json
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md
- contracts/env/env-contract.md
- contracts/env/.env.example.template
- contracts/env/env.schema.json
- contracts/css/css-contract.md
- app/backend/services/
- app/backend/processors/orchestrator.py
- app/backend/processors/pdf_processor.py
- app/backend/processors/docx_processor.py
- app/backend/processors/pptx_processor.py
- app/backend/processors/xlsx_processor.py
- app/backend/clients/ollama_client.py
- app/backend/clients/base_llm_client.py
- app/backend/api/routes.py
- docs/adr/
- app/backend/api/schemas.py
- app/backend/config.py
- app/backend/models/translatable_document.py
- app/frontend/src/pages/TranslatePage.jsx
- app/frontend/src/pages/HistoryPage.jsx
- app/frontend/src/api/jobs.js
- app/frontend/src/api/client.js
- app/frontend/src/components/
- app/frontend/src/contexts/
- app/frontend/src/hooks/
- tests/
- .github/workflows/contract-driven-gates.yml

## Required Contracts
- contracts/api/api-contract.md (new GET /api/jobs/{id}/judge endpoint) + contracts/api/openapi.yml (export refresh)
- contracts/data/data-shape-contract.md (judge result fields on job record)
- contracts/business/business-rules.md (score tiers, re-translate trigger, max-iteration rule)
- contracts/env/env-contract.md (JUDGE_ENABLED flag, JUDGE_MODEL var) + .env.example.template
- contracts/css/css-contract.md (job-detail judge panel)

## Required Tests
- unit: judge service (score parsing, feedback formatting, iteration cap, graceful degradation)
- contract: new endpoint response shape vs api-contract
- integration: orchestrator judge hook fires post-translation across all 4 formats (DOCX/PPTX/XLSX/PDF)
- data-boundary: job record serialization with/without judge fields; missing-Gemma path

## Agent Work Packets

### spec-architect
- specs/changes/p3-llm-judge/
- specs/context/project-map.md
- specs/context/contracts-index.md
- contracts/api/api-contract.md
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md
- contracts/env/env-contract.md
- app/backend/processors/orchestrator.py
- app/backend/services/
- app/backend/clients/ollama_client.py
- app/backend/clients/base_llm_client.py
- app/backend/config.py
- app/backend/api/schemas.py

### contract-reviewer
- specs/changes/p3-llm-judge/
- contracts/api/
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md
- contracts/env/
- contracts/css/css-contract.md
- app/backend/api/routes.py
- app/backend/api/schemas.py

### test-strategist
- specs/changes/p3-llm-judge/
- contracts/
- tests/

### ci-cd-gatekeeper
- specs/changes/p3-llm-judge/
- contracts/
- .github/workflows/contract-driven-gates.yml

### implementation-planner
- specs/changes/p3-llm-judge/
- contracts/
- app/backend/
- app/frontend/src/

### backend-engineer
- specs/changes/p3-llm-judge/
- contracts/api/
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md
- contracts/env/
- app/backend/services/
- app/backend/processors/
- app/backend/clients/
- docs/adr/
- app/backend/api/routes.py
- app/backend/api/schemas.py
- app/backend/config.py
- app/backend/models/translatable_document.py
- tests/

### frontend-engineer
- specs/changes/p3-llm-judge/
- contracts/api/api-contract.md
- contracts/css/css-contract.md
- app/frontend/src/pages/TranslatePage.jsx
- app/frontend/src/pages/HistoryPage.jsx
- app/frontend/src/api/jobs.js
- app/frontend/src/api/client.js
- app/frontend/src/components/
- app/frontend/src/hooks/

### ui-ux-reviewer / visual-reviewer
- specs/changes/p3-llm-judge/
- contracts/css/css-contract.md
- app/frontend/src/pages/TranslatePage.jsx
- app/frontend/src/components/

### qa-reviewer
- specs/changes/p3-llm-judge/
- contracts/
- app/backend/
- tests/

## Context Expansion Requests
- (none — CER-001 resolved: exact frontend filenames confirmed via ls; CER-002 resolved: backend service files already in Allowed Paths)

## Approved Expansions
-
