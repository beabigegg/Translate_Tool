# Change Classification

## Change Types
- primary: ui-only-change (feature-add)
- secondary: api-client-wiring (existing field, no contract change)

## Lane
- feature

## Risk Level
- low

## Impact Radius
- module-level (TranslatePage + jobs API client; no backend, no contract change)

## Tier
- 3

## Architecture Review Required
- no
- reason: no new endpoint, no module-boundary change, no data-flow or migration decision; the backend field, value set, and default already exist

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

## Optional Artifacts (default: no — set yes only with explicit reason)
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | |
| proposal.md | no | |
| spec.md | no | |
| design.md | no | no architecture review required; task 1.3 skipped |
| qa-report.md | no | routine pass/fail goes in agent-log/qa-reviewer.yml unless blocking finding |
| regression-report.md | no | additive UI control; no existing behavior changed |
| visual-review-report.md | no | one new control; reviewer notes go to agent-log/visual-reviewer.yml |
| monkey-test-report.md | no | |
| stress-soak-report.md | no | |

## Required Contracts
- API: verify only — `output_mode` (append/replace, default append) must already be documented in `contracts/api/api-contract.md`. No contract edit expected. If not documented, promote to api-contract change.
- CSS/UI: verify — new selector must comply with `contracts/css/css-contract.md` token policy and `contracts/css/design-tokens.md`; no hardcoded colors/spacing.
- Env: none
- Data shape: none
- Business logic: verify only — confirm append/replace behavior rules exist in `contracts/business/business-rules.md`. No edit expected.
- CI/CD: none

## Required Tests
- unit: frontend component test — selector renders both labeled options, default is `append`, chosen value is included in translation-start payload as `output_mode`
- contract: none (no API contract change; backend `output_mode` already covered by tests/test_output_mode_api.py)
- integration: optional payload-shape assertion that jobs API client forwards `output_mode` unchanged
- E2E: none required at this tier
- visual: selector visible on TranslatePage before job start (visual-reviewer; evidence via agent-log)
- data-boundary: none
- resilience: none
- fuzz/monkey: none
- stress: none
- soak: none

## Required Agents
1. implementation-planner — turn this classification + verify-only contracts into the execution packet
2. frontend-engineer — add selector to TranslatePage and wire `output_mode` into jobs API payload
3. test-strategist — author/define frontend component + payload-wiring tests and AC→test mapping
4. ui-ux-reviewer — label correctness, placement before job start, accessibility
5. visual-reviewer — confirm rendered control and token compliance
6. contract-reviewer — read-only confirmation that `output_mode` is in API contract and business rules; flag drift if not
7. qa-reviewer — release readiness / gate summary

## Inferred Acceptance Criteria
- AC-1: TranslatePage shows an output-mode selector with exactly two choices, labeled "原文在下方" (value `append`) and "原地取代/覆蓋原文" (value `replace`), visible before the user starts a translation job.
- AC-2: The default selection is `append`; with no user change the translation-start payload contains `output_mode: "append"`.
- AC-3: Selecting "原地取代/覆蓋原文" causes the translation-start API payload to contain `output_mode: "replace"`.
- AC-4: The selector uses CSS contract tokens (no hardcoded colors/spacing) and passes UI/UX + visual review.
- AC-5: No backend changes are introduced; `app/backend/api/schemas.py` `output_mode` field, value set, and default remain unchanged and API/business contracts require no edits.

## Tasks Not Applicable
- not-applicable: 1.3, 2.1, 4.1

## Clarifications or Assumptions
- Assumption: `output_mode` is already present in `contracts/api/api-contract.md` and `contracts/business/business-rules.md`. If contract-reviewer finds it is NOT documented, promote to an api-contract change.
- Assumption: localStorage persistence of the selection is out of scope (non-goal).
- Assumption: per-segment/per-paragraph mode selection is out of scope (non-goal).
- Note: `contracts/api/openapi.yml` does not need regeneration — no endpoint or schema field is being added or renamed.

## Context Manifest Draft

### Affected Surfaces
- Frontend UI: TranslatePage.jsx output-mode selector
- Frontend API client: jobs translation-start payload (app/frontend/src/api/)
- API/Business contracts: read-only verification (no new endpoint; `output_mode` already exists)

### Allowed Paths
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

### Required Contracts
- contracts/api/api-contract.md (verify `output_mode` documented; no change)
- contracts/business/business-rules.md (verify append/replace behavior rule; no change)
- contracts/css/css-contract.md (token policy for new control)

### Required Tests
- Frontend component/unit test for output-mode selector and payload wiring (app/frontend/src/ test directory — see CER-001)
- No backend test changes (tests/test_output_mode_api.py already covers backend `output_mode`)

### Agent Work Packets

#### implementation-planner
- specs/changes/expose-output-mode-ui/
- specs/context/project-map.md
- specs/context/contracts-index.md
- contracts/api/api-contract.md
- contracts/business/business-rules.md
- contracts/css/css-contract.md

#### frontend-engineer
- specs/changes/expose-output-mode-ui/
- app/frontend/src/pages/TranslatePage.jsx
- app/frontend/src/api/
- app/frontend/src/i18n/
- app/frontend/src/constants/
- app/frontend/src/styles/
- app/backend/api/schemas.py
- contracts/css/css-contract.md
- contracts/css/design-tokens.md

#### test-strategist
- specs/changes/expose-output-mode-ui/
- app/frontend/src/pages/TranslatePage.jsx
- app/frontend/src/api/

#### ui-ux-reviewer
- specs/changes/expose-output-mode-ui/
- app/frontend/src/pages/TranslatePage.jsx
- app/frontend/src/i18n/
- contracts/css/css-contract.md

#### visual-reviewer
- specs/changes/expose-output-mode-ui/
- app/frontend/src/pages/TranslatePage.jsx
- contracts/css/css-contract.md
- contracts/css/design-tokens.md

#### contract-reviewer
- specs/changes/expose-output-mode-ui/
- contracts/api/api-contract.md
- contracts/business/business-rules.md

#### qa-reviewer
- specs/changes/expose-output-mode-ui/

### Context Expansion Requests
- request-id: CER-001
  requested_paths:
    - app/frontend/src/**/__tests__/
    - app/frontend/package.json
  reason: project-map truncates app/frontend/src/** at max depth and shows no frontend test directory; test-strategist needs the actual frontend test root and runner config.
  status: pending
