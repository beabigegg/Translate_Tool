# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- Frontend: SettingsPage and its supporting hooks/api/components
- Backend: provider API routes, provider clients, quality/model services
- Contracts: api, data-shape, business, css, env

## Allowed Paths
- specs/changes/settings-page-cloud-redesign/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/frontend/src/pages/SettingsPage.jsx
- app/frontend/src/components/domain/VramCalculator.jsx
- app/frontend/src/hooks/useHealthCheck.js
- app/frontend/src/api/system.js
- app/frontend/src/pages/
- app/frontend/src/components/
- app/frontend/src/constants/
- app/frontend/src/i18n/
- app/frontend/src/styles/
- app/backend/api/routes.py
- app/backend/api/schemas.py
- app/backend/clients/openai_compatible_client.py
- app/backend/clients/base_llm_client.py
- app/backend/services/quality_evaluator.py
- app/backend/services/model_router.py
- app/backend/services/translation_service.py
- app/backend/config.py
- config/providers.yml
- config/providers.yml.example
- contracts/api/api-contract.md
- contracts/api/api-inventory.md
- contracts/api/error-format.md
- contracts/api/openapi.yml
- contracts/api/openapi.json
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md
- contracts/css/css-contract.md
- contracts/css/design-tokens.md
- contracts/env/env-contract.md
- contracts/env/.env.example.template
- tests/test_model_config_api.py
- tests/test_quality_evaluation.py
- tests/test_provider_fallback.py
- tests/test_openai_compatible_client.py
- tests/

## Required Contracts
- contracts/api/api-contract.md
- contracts/api/api-inventory.md
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md
- contracts/css/css-contract.md
- contracts/env/env-contract.md

## Required Tests
- tests/test_model_config_api.py (or new tests/test_providers_api.py)
- tests/test_quality_evaluation.py
- tests/test_provider_fallback.py
- tests/

## Agent Work Packets

### spec-architect
- specs/changes/settings-page-cloud-redesign/
- specs/context/project-map.md
- specs/context/contracts-index.md
- contracts/api/api-contract.md
- contracts/env/env-contract.md
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md
- app/backend/api/routes.py
- app/backend/services/quality_evaluator.py
- config/providers.yml.example

### implementation-planner
- specs/changes/settings-page-cloud-redesign/
- contracts/api/api-contract.md
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md

### backend-engineer
- specs/changes/settings-page-cloud-redesign/
- app/backend/api/routes.py
- app/backend/api/schemas.py
- app/backend/clients/openai_compatible_client.py
- app/backend/clients/base_llm_client.py
- app/backend/services/quality_evaluator.py
- app/backend/services/model_router.py
- app/backend/services/translation_service.py
- app/backend/config.py
- config/providers.yml
- config/providers.yml.example
- tests/

### frontend-engineer
- specs/changes/settings-page-cloud-redesign/
- app/frontend/src/pages/SettingsPage.jsx
- app/frontend/src/components/domain/VramCalculator.jsx
- app/frontend/src/hooks/useHealthCheck.js
- app/frontend/src/api/system.js
- app/frontend/src/components/
- app/frontend/src/constants/
- app/frontend/src/i18n/
- app/frontend/src/styles/
- app/frontend/src/pages/

### test-strategist
- specs/changes/settings-page-cloud-redesign/
- tests/
- app/frontend/src/pages/
- contracts/

### e2e-resilience-engineer
- specs/changes/settings-page-cloud-redesign/
- tests/
- app/backend/api/routes.py
- app/frontend/src/pages/SettingsPage.jsx

### contract-reviewer
- specs/changes/settings-page-cloud-redesign/
- contracts/

### ui-ux-reviewer
- specs/changes/settings-page-cloud-redesign/
- app/frontend/src/pages/SettingsPage.jsx
- app/frontend/src/i18n/
- contracts/css/

### visual-reviewer
- specs/changes/settings-page-cloud-redesign/
- app/frontend/src/pages/SettingsPage.jsx
- contracts/css/

### qa-reviewer
- specs/changes/settings-page-cloud-redesign/
- app/frontend/src/
- app/backend/
- tests/
- contracts/

### ci-cd-gatekeeper
- specs/changes/settings-page-cloud-redesign/
- contracts/api/openapi.yml
- .github/workflows/contract-driven-gates.yml

## Context Expansion Requests

- request-id: CER-001
  requested_paths:
    - app/frontend/src/pages/TranslatePage.jsx
    - app/frontend/src/pages/__tests__/
  reason: project-map truncates app/frontend/src/pages/ at max depth; TranslatePage Step-2 controls (parity reference) and frontend __tests__/ location needed by frontend-engineer and test-strategist.
  status: approved

- request-id: CER-002
  requested_paths:
    - app/frontend/src/api/system.js
    - app/frontend/src/hooks/useHealthCheck.js
  reason: project-map truncates app/frontend/src/api/ and hooks/ at max depth; both are edit targets.
  status: approved

## Approved Expansions
- CER-001: app/frontend/src/pages/TranslatePage.jsx, app/frontend/src/pages/__tests__/ — already included in Allowed Paths above.
- CER-002: app/frontend/src/api/system.js, app/frontend/src/hooks/useHealthCheck.js — already included in Allowed Paths above.
