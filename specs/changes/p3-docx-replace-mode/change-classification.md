# Change Classification: p3-docx-replace-mode

## Change Types
- primary: `feature-enhancement`, `api-only-change`
- secondary: `business-logic-change`

## Risk Level
- medium

## Impact Radius
- cross-module

## Tier
- 2

## Architecture Review Required
- no
- reason: Additive parameter on an existing, well-understood output path; no new module boundary, data-flow rework, or migration/rollback decision. The multi-target rule is a small policy decision recordable in the implementation plan + business-rules contract.

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

## Optional Artifacts (default: no — set yes only with explicit reason)
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | Existing "append" behavior documented inline in implementation-plan |
| proposal.md | no | Single clear request; no product decision to investigate |
| spec.md | no | No separate user-facing behavior spec required beyond classification + plan |
| design.md | no | Architecture review not required (additive parameter) |
| qa-report.md | no | Promote only if a blocking/approved-with-risk finding arises |
| regression-report.md | no | Backward-compat covered by unit/contract tests; agent-log pointer suffices |
| visual-review-report.md | no | No UI rendering surface |
| monkey-test-report.md | no | No interactive UI flow |
| stress-soak-report.md | no | No high-load change |

## Required Contracts
- API: `contracts/api/api-contract.md` — add `output_mode` field to `POST /api/jobs` request body (optional, default `"append"`). Run `cdd-kit openapi export --out contracts/api/openapi.yml` after editing.
- CSS/UI: none
- Env: none
- Data shape: none (output_mode is a runtime request parameter, not a persisted IR/document-schema field)
- Business logic: `contracts/business/business-rules.md` — replace-vs-append semantics and the multi-target rule.
- CI/CD: none

## Required Tests
- unit: `translate_docx` / `translate_pptx` accept `output_mode="replace"|"append"`; default is `"append"`; replace overwrites source paragraphs/text frames in-place. Selection assertion required (assert WHICH paragraphs are translated-only, not just count).
- contract: `POST /api/jobs` accepts `output_mode` in body; schema validation rejects invalid values; openapi conformance stays green.
- integration: orchestrator threads `output_mode` from job request → processor; verify parameter actually reaches processors (guard against orphaned-wiring miss).
- E2E: none (covered by integration + unit)
- visual: none
- data-boundary: none
- resilience: none
- fuzz/monkey: none
- stress: none
- soak: none

## Required Agents
- `contract-reviewer`
- `test-strategist`
- `implementation-planner`
- `backend-engineer`
- `qa-reviewer`

## Inferred Acceptance Criteria
- AC-1: `translate_docx` and `translate_pptx` accept an `output_mode` parameter typed `Literal["append", "replace"]` defaulting to `"append"`.
- AC-2: With `output_mode="append"` the existing bilingual output is byte/behavior-equivalent to current behavior (backward compatible — no regression).
- AC-3: With `output_mode="replace"` on a single-target DOCX job, the generated file contains no remaining source-language paragraphs (source text is overwritten in-place by its translation).
- AC-4: With `output_mode="replace"` on a single-target PPTX job, source text frames are overwritten in-place with their translation and no source text remains.
- AC-5: `POST /api/jobs` request body accepts an optional `output_mode` field defaulting to `"append"`; invalid values are rejected by request validation.
- AC-6: The orchestrator passes `output_mode` from the job request through to `translate_docx` / `translate_pptx` (verified the parameter reaches the processor, not merely accepted at the API layer).
- AC-7: Multi-target jobs either ignore `output_mode` or are forced to `"append"` (replace is not applied for multi-target), per the business rule, and this is enforced and tested.
- AC-8: The API contract (`api-contract.md` + exported `openapi.yml`) and `business-rules.md` document `output_mode` and the multi-target rule; contract/conformance gates pass.

## Tasks Not Applicable
- not-applicable: 1.3

## Clarifications or Assumptions
- Change is backend-only as scoped; no frontend UI control for `output_mode` is in scope (separate follow-up change).
- `output_mode` is a runtime request parameter, not a persisted IR/document-schema field — no data-shape contract change.
- PDF and XLSX processors are out of scope.
- For multi-target jobs: silent ignore (clamp to "append") is preferred over a validation error — contract-reviewer/planner to decide and record in business-rules.

## Context Manifest Draft

### Affected Surfaces
- Backend processors: DOCX/PPTX translation output path
- Backend orchestration: job-request parameter threading
- Backend API: `POST /api/jobs` request schema

### Allowed Paths
- specs/changes/p3-docx-replace-mode/
- specs/context/project-map.md
- specs/context/contracts-index.md
- contracts/api/api-contract.md
- contracts/api/openapi.yml
- contracts/api/openapi.json
- contracts/api/api-inventory.md
- contracts/business/business-rules.md
- app/backend/processors/docx_processor.py
- app/backend/processors/pptx_processor.py
- app/backend/processors/orchestrator.py
- app/backend/api/routes.py
- app/backend/api/schemas.py
- app/backend/services/job_manager.py
- tests/

### Agent Work Packets

#### implementation-planner
- specs/changes/p3-docx-replace-mode/
- specs/context/project-map.md
- specs/context/contracts-index.md
- contracts/api/api-contract.md
- contracts/business/business-rules.md
- app/backend/processors/docx_processor.py
- app/backend/processors/pptx_processor.py
- app/backend/processors/orchestrator.py
- app/backend/api/routes.py
- app/backend/api/schemas.py

#### backend-engineer
- specs/changes/p3-docx-replace-mode/
- contracts/api/api-contract.md
- contracts/api/openapi.yml
- contracts/api/openapi.json
- contracts/business/business-rules.md
- app/backend/processors/docx_processor.py
- app/backend/processors/pptx_processor.py
- app/backend/processors/orchestrator.py
- app/backend/api/routes.py
- app/backend/api/schemas.py
- app/backend/services/job_manager.py
- tests/

#### test-strategist
- specs/changes/p3-docx-replace-mode/
- tests/
- app/backend/processors/docx_processor.py
- app/backend/processors/pptx_processor.py
- app/backend/processors/orchestrator.py

#### contract-reviewer
- specs/changes/p3-docx-replace-mode/
- contracts/api/api-contract.md
- contracts/api/openapi.yml
- contracts/api/api-inventory.md
- contracts/business/business-rules.md

#### qa-reviewer
- specs/changes/p3-docx-replace-mode/
- contracts/api/api-contract.md
- contracts/business/business-rules.md
- app/backend/processors/docx_processor.py
- app/backend/processors/pptx_processor.py
- app/backend/processors/orchestrator.py
- app/backend/api/routes.py
- tests/
