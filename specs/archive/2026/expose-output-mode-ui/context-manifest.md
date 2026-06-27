# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- Frontend UI: TranslatePage.jsx output-mode selector
- Frontend API client: jobs translation-start payload (app/frontend/src/api/)
- API/Business contracts: read-only verification (no new endpoint; `output_mode` already exists)

## Allowed Paths
- specs/changes/expose-output-mode-ui/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/frontend/src/pages/TranslatePage.jsx
- app/frontend/src/api/
- app/frontend/src/i18n/
- app/frontend/src/constants/
- app/frontend/src/styles/
- app/backend/api/schemas.py
- contracts/api/api-contract.md
- contracts/business/business-rules.md
- contracts/css/css-contract.md
- contracts/css/design-tokens.md
- app/frontend/package.json
- app/frontend/vite.config.js
- app/frontend/src/

## Required Contracts
- contracts/api/api-contract.md (verify `output_mode` documented; no change)
- contracts/business/business-rules.md (verify append/replace behavior rule; no change)
- contracts/css/css-contract.md (token policy for new control)

## Required Tests
- Frontend component/unit test for output-mode selector and payload wiring
- No backend test changes (tests/test_output_mode_api.py already covers backend `output_mode`)

## Agent Work Packets

### change-classifier
- specs/changes/expose-output-mode-ui/
- specs/context/project-map.md
- specs/context/contracts-index.md

### implementation-planner
- specs/changes/expose-output-mode-ui/
- specs/context/project-map.md
- specs/context/contracts-index.md
- contracts/api/api-contract.md
- contracts/business/business-rules.md
- contracts/css/css-contract.md

### frontend-engineer
- specs/changes/expose-output-mode-ui/
- app/frontend/src/pages/TranslatePage.jsx
- app/frontend/src/api/
- app/frontend/src/i18n/
- app/frontend/src/constants/
- app/frontend/src/styles/
- app/frontend/src/
- app/frontend/package.json
- app/backend/api/schemas.py
- contracts/css/css-contract.md
- contracts/css/design-tokens.md

### test-strategist
- specs/changes/expose-output-mode-ui/
- app/frontend/src/pages/TranslatePage.jsx
- app/frontend/src/api/
- app/frontend/src/
- app/frontend/package.json

### ui-ux-reviewer
- specs/changes/expose-output-mode-ui/
- app/frontend/src/pages/TranslatePage.jsx
- app/frontend/src/i18n/
- contracts/css/css-contract.md

### visual-reviewer
- specs/changes/expose-output-mode-ui/
- app/frontend/src/pages/TranslatePage.jsx
- contracts/css/css-contract.md
- contracts/css/design-tokens.md

### contract-reviewer
- specs/changes/expose-output-mode-ui/
- contracts/api/api-contract.md
- contracts/business/business-rules.md

### qa-reviewer
- specs/changes/expose-output-mode-ui/

## Context Expansion Requests
- request-id: CER-001
  requested_paths:
    - app/frontend/src/
    - app/frontend/package.json
    - app/frontend/vite.config.js
  reason: project-map truncates app/frontend/src/** at max depth; test-strategist and frontend-engineer need the actual test root, runner config, and vite config to set up vitest.
  status: approved
