# Change Classification

## Change Types
- primary: feature-enhancement, api-contract-change
- secondary: ui-only-change (frontend upload whitelist + drop-zone copy), env-change / dependency-surface (LibreOffice as documented optional binary), test-coverage-add (existing `.doc`/`.xls` conversion paths currently untested)

## Lane
- feature

## Risk Level
- medium

## Impact Radius
- cross-module (backend processors + config, frontend upload surface, API/env/business contracts, CI, install docs)

## Tier
- 2

Rationale: medium risk × cross-module maps to Tier 2–3; classifying upward to Tier 2 because this adds/formalizes an external binary dependency (LibreOffice) with graceful-degradation semantics, changes the documented upload contract (`SUPPORTED_EXTENSIONS`), and carries a genuine quality/faithfulness design decision (lossy-conversion risk disclosure). No auth, payments, DB migration, or production-data-at-scale surface is touched, so it does not rise to Tier 0–1.

## Architecture Review Required
- yes
- reason: Two non-obvious, contract-affecting design decisions exist. (1) Whether converted legacy documents that flow through existing layout-detection/QE need a distinct QE threshold or a user-facing "lossy conversion — layout fidelity may be lower than native" disclosure, and whether that disclosure requires a new API-contract field / job-metadata field / UI hint. (2) Data-flow and operational-risk semantics of introducing/formalizing an external binary dependency with graceful degradation across backend, contracts, and CI. Adding `ppt_to_pptx` alone follows the existing pattern, but the disclosure/QE-boundary decision is a module-boundary + operational-risk decision that should be settled in `design.md` before implementation planning.

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md
Plus: design.md (Architecture Review Required = yes)

## Optional Artifacts (default: no — set yes only with explicit reason)
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | current state already captured as verified facts in change-request "Known Context"; no separate investigation needed |
| proposal.md | no | scope already agreed with user before scaffolding |
| spec.md | no | no separate user-facing behavior spec beyond design.md + implementation-plan |
| design.md | yes | lossy-conversion disclosure / QE-boundary decision + external-dependency data-flow must be decided before planning |
| qa-report.md | no | use agent-log/qa-reviewer.yml; upgrade to yes only if blocking findings or approved-with-risk |
| regression-report.md | no | no existing behavior is being changed (new formats + net-new test coverage); use agent-log pointer if regression run is clean |
| visual-review-report.md | no | UI change is a text/whitelist copy change; capture pass/fail in agent-log/visual-reviewer.yml unless a visible defect needs durable evidence |
| monkey-test-report.md | no | not applicable |
| stress-soak-report.md | no | no high-load/long-running surface introduced |

Artifact minimization:
- Prefer optional `agent-log/*.yml` pointers for routine review evidence.
- Create report markdown only for blocking findings, approved-with-risk, visual evidence bundles, or high-risk load/soak results.
- Later artifacts should reference earlier artifacts by path/section/id instead of duplicating full content.

## Required Contracts
- API: yes — `contracts/api/api-contract.md`: add `.ppt` to accepted upload extensions, document behavior/error when LibreOffice is unavailable (graceful degradation), keep `SUPPORTED_EXTENSIONS` in sync. Re-run `cdd-kit openapi export --out contracts/api/openapi.yml` after edit.
- CSS/UI: no — drop-zone copy/whitelist only; no design-token or styling-rule change expected.
- Env: yes — `contracts/env/env-contract.md` + `app/backend/environment.yml` + install docs: document LibreOffice as an optional external binary dependency with detection/degradation semantics.
- Data shape: no — converted documents reuse the existing IR / pipeline; no new data schema.
- Business logic: yes — `contracts/business/business-rules.md`: rule for legacy-format lossy-conversion handling and QE/disclosure policy (final shape decided in design.md).
- CI/CD: yes — `contracts/ci/ci-gate-contract.md`: define how legacy-format conversion tests behave when LibreOffice is absent on a CI runner (skip-with-marker vs required), so the gate is deterministic.

## Required Tests
- unit: `ppt_to_pptx`, plus previously-untested `doc_to_docx` / `xls_to_xlsx` and `is_libreoffice_available()` graceful-degradation branch (helpers in `libreoffice_helpers.py`)
- contract: upload-accepted-extensions / `SUPPORTED_EXTENSIONS` conformance and the LibreOffice-unavailable error contract
- integration: orchestrator `.ppt`/`.doc`/`.xls` branches end-to-end through the existing layout-detection/QE pipeline (converted doc still produces layout-faithful, QE-scored output)
- E2E: optional smoke — upload a legacy file and retrieve translated output (only if it fits an existing smoke harness)
- visual: minimal — drop-zone renders the newly-accepted extensions/copy (agent-log evidence acceptable)
- data-boundary: corrupt/empty/misnamed legacy file and missing-binary path produce a clear, contract-conformant error (not a crash)
- resilience: LibreOffice-unavailable and conversion-failure paths degrade gracefully with actionable error messaging
- fuzz/monkey: none
- stress: none
- soak: none

## Required Agents
- spec-architect — writes design.md: lossy-conversion disclosure + QE-boundary decision, external-dependency data-flow (runs before implementation-planner)
- implementation-planner — turns design + contracts + tests into the execution packet
- backend-engineer — ppt_to_pptx in libreoffice_helpers.py, orchestrator .ppt wiring mirroring .doc/.xls, SUPPORTED_EXTENSIONS update in config.py, backfill tests for existing doc/xls paths
- frontend-engineer — ACCEPTED_EXTENSIONS in fileTypes.js + drop-zone copy in FileDropZone.jsx
- test-strategist — unit/contract/integration/data-boundary/resilience coverage and acceptance-criteria → test mapping
- contract-reviewer — API + env + business + CI contract deltas and openapi export freshness
- dependency-security-reviewer — formalizing LibreOffice as a documented external binary dependency (subprocess/headless invocation and supply-chain/install surface); confirm graceful-degradation and no new secret/exec risk
- ci-cd-gatekeeper — deterministic CI behavior for LibreOffice-dependent tests (skip-with-marker vs required) and gate/tier-floor handling
- ui-ux-reviewer — visible drop-zone copy/accepted-types change (interaction/copy)
- visual-reviewer — confirm drop-zone renders new extensions correctly (lightweight; agent-log evidence unless a defect needs durable report)
- qa-reviewer — release readiness (always last)

## Inferred Acceptance Criteria
- AC-1: `ppt_to_pptx()` exists in `app/backend/processors/libreoffice_helpers.py`, follows the same signature/error semantics as `doc_to_docx()`/`xls_to_xlsx()`, and returns a converted `.pptx` when LibreOffice is available.
- AC-2: `orchestrator.py` routes `.ppt` uploads through `ppt_to_pptx()` into the existing PPTX pipeline, mirroring the existing `.doc`/`.xls` branches, and `.ppt` is added to `SUPPORTED_EXTENSIONS` in `config.py`.
- AC-3: The previously-untested `.doc` and `.xls` conversion paths (`doc_to_docx`, `xls_to_xlsx`, orchestrator branches) gain automated test coverage that fails if the wiring regresses.
- AC-4: When LibreOffice is not installed, all three legacy formats degrade gracefully via `is_libreoffice_available()` — the user/API receives a clear, contract-conformant error rather than a crash, and this behavior is covered by a resilience/data-boundary test.
- AC-5: LibreOffice is documented as an optional external dependency in `environment.yml` and install docs (README/docs), including how to install it and the consequence of its absence.
- AC-6: Frontend `ACCEPTED_EXTENSIONS` and the drop-zone copy accept and display `.doc`/`.xls`/`.ppt`, consistent with backend `SUPPORTED_EXTENSIONS`.
- AC-7: A converted legacy document still flows through the existing layout-detection and QE pipeline and produces a QE-scored, layout-faithful output; the lossy-conversion risk is surfaced per the design.md decision (disclosure field/UI hint and/or QE handling).
- AC-8: `contracts/api/api-contract.md` reflects the updated accepted-upload types and unavailable-dependency behavior, and `contracts/api/openapi.yml` is re-exported and in sync.

## Tasks Not Applicable
- not-applicable: 2.2 (CSS/UI contract — not touched), 2.4 (Data shape contract — not touched), 3.3 (E2E/resilience — no dedicated e2e-resilience-engineer commissioned at Tier 2; resilience/data-boundary coverage folded into 3.1/3.2 per test-strategist plan), 3.4 (Data-boundary/monkey — no dedicated monkey-test-engineer commissioned at Tier 2; data-boundary coverage folded into 3.1/3.2), 3.5 (Stress/soak — not applicable, no high-load/long-running surface)

## Clarifications or Assumptions
- Assumption: the lossy-conversion "risk disclosure" mechanism (new API/job field, UI warning banner, and/or separate QE threshold) is deferred to spec-architect in design.md; this classification requires the decision to be made there before implementation-planning, but does not prescribe its shape.
- Assumption: `.ppt` conversion reuses the LibreOffice-headless strategy (per Non-goals) — no native binary `.ppt` parser is in scope.
- Verified (main Claude, prior to scaffolding): `app/frontend/src/components/domain/FileDropZone.jsx` exists at the path used throughout this classification, and contains no i18n usage (hardcoded Traditional Chinese copy, no import from `app/frontend/src/i18n/`) — so drop-zone copy changes are a direct inline edit, not an i18n-key change. CER-001 and CER-002 (below) are resolved on this basis; see Approved Expansions in context-manifest.md.
- Open: whether legacy-format conversion tests should be `required` or `skip-with-marker` in CI when LibreOffice is absent on the runner — to be settled by ci-cd-gatekeeper in ci-gates.md / contracts/ci/ci-gate-contract.md.

## Context Manifest Draft
<!-- Copied verbatim into context-manifest.md by main Claude in Step 2.3. -->

### Affected Surfaces
- Backend document-conversion layer (`libreoffice_helpers.py`, `orchestrator.py`)
- Backend config / supported-extensions surface (`config.py`)
- Frontend upload surface (`fileTypes.js`, `FileDropZone.jsx`)
- API upload contract (`contracts/api/api-contract.md` + `openapi.yml`)
- Runtime/dependency surface (`environment.yml`, env-contract, install docs)
- Business-rule + CI-gate contracts (lossy-conversion policy, LibreOffice-in-CI policy)

### Allowed Paths
- specs/changes/support-legacy-office-formats/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/config.py
- app/backend/processors/libreoffice_helpers.py
- app/backend/processors/orchestrator.py
- app/backend/services/quality_evaluator.py
- app/frontend/src/constants/fileTypes.js
- app/frontend/src/components/domain/FileDropZone.jsx
- app/backend/environment.yml
- app/backend/requirements.txt
- contracts/api/api-contract.md
- contracts/api/api-inventory.md
- contracts/api/openapi.yml
- contracts/env/env-contract.md
- contracts/business/business-rules.md
- contracts/ci/ci-gate-contract.md
- .github/workflows/contract-driven-gates.yml
- README.md
- docs/
- tests/conftest.py
- tests/fixtures/
- tests/contract/
- tests/test_orchestrator_phase0.py
- tests/test_output_mode_orchestrator.py
- tests/test_libreoffice_helpers.py (new)

### Agent Work Packets

#### spec-architect
- specs/changes/support-legacy-office-formats/
- specs/context/project-map.md
- specs/context/contracts-index.md
- contracts/api/api-contract.md
- contracts/business/business-rules.md
- contracts/env/env-contract.md
- app/backend/processors/orchestrator.py
- app/backend/services/quality_evaluator.py

#### implementation-planner
- specs/changes/support-legacy-office-formats/
- contracts/api/api-contract.md
- contracts/env/env-contract.md
- contracts/business/business-rules.md
- app/backend/config.py
- app/backend/processors/libreoffice_helpers.py
- app/backend/processors/orchestrator.py
- app/frontend/src/constants/fileTypes.js

#### backend-engineer
- specs/changes/support-legacy-office-formats/
- app/backend/config.py
- app/backend/processors/libreoffice_helpers.py
- app/backend/processors/orchestrator.py
- app/backend/environment.yml
- app/backend/requirements.txt
- tests/test_libreoffice_helpers.py
- tests/test_orchestrator_phase0.py
- tests/fixtures/
- tests/conftest.py

#### frontend-engineer
- specs/changes/support-legacy-office-formats/
- app/frontend/src/constants/fileTypes.js
- app/frontend/src/components/domain/FileDropZone.jsx

#### test-strategist
- specs/changes/support-legacy-office-formats/
- tests/
- contracts/api/api-contract.md
- contracts/business/business-rules.md

#### contract-reviewer
- specs/changes/support-legacy-office-formats/
- contracts/api/api-contract.md
- contracts/api/api-inventory.md
- contracts/api/openapi.yml
- contracts/env/env-contract.md
- contracts/business/business-rules.md
- contracts/ci/ci-gate-contract.md

#### dependency-security-reviewer
- specs/changes/support-legacy-office-formats/
- app/backend/processors/libreoffice_helpers.py
- app/backend/environment.yml
- app/backend/requirements.txt
- contracts/env/env-contract.md

#### ci-cd-gatekeeper
- specs/changes/support-legacy-office-formats/
- contracts/ci/ci-gate-contract.md
- .github/workflows/contract-driven-gates.yml
- app/backend/environment.yml

#### ui-ux-reviewer
- specs/changes/support-legacy-office-formats/
- app/frontend/src/constants/fileTypes.js
- app/frontend/src/components/domain/FileDropZone.jsx

#### visual-reviewer
- specs/changes/support-legacy-office-formats/
- app/frontend/src/components/domain/FileDropZone.jsx

#### qa-reviewer
- specs/changes/support-legacy-office-formats/
- contracts/api/api-contract.md
- tests/

### Context Expansion Requests
- request-id: CER-001
  requested_paths:
    - app/frontend/src/components/domain/FileDropZone.jsx
  reason: Classifier inferred this path without a shell; main Claude has since verified it exists and read its contents in-session prior to classification.
  status: approved
- request-id: CER-002
  requested_paths:
    - app/frontend/src/i18n/
  reason: Checked whether drop-zone copy is i18n-managed; confirmed FileDropZone.jsx uses hardcoded inline copy with no i18n import, so no i18n/ read is needed for this change.
  status: resolved-not-needed
