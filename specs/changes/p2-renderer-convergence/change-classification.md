# Change Classification

## Change Types
- primary: refactor (renderer-path convergence / architecture), business-logic-change (rendering/layout output behavior)
- secondary: data-shape-consumer-change (IR → rendered layout boundary)

## Lane
- feature

## Risk Level
- medium

## Impact Radius
- cross-module

## Tier
- 2

## Architecture Review Required
- yes
- reason: Introduces a primary/fallback renderer architecture (fitz primary, ReportLab fallback) with a fallback-trigger decision, extracts shared IR-bbox reflow logic into a common path, and changes the data-flow from `TranslatableDocument` IR to two distinct render backends. The fallback semantics (when does fitz hand off to ReportLab, and is layout output guaranteed equivalent) are non-obvious and load-bearing for correctness. Must be settled in `design.md` before implementation planning.

## Required Artifacts

Always required: `change-request.md`, `change-classification.md`, `implementation-plan.md`, `test-plan.md`, `ci-gates.md`, `tasks.yml`, `context-manifest.md`

## Optional Artifacts (default: no — set yes only with explicit reason)

| artifact | create? | reason |
|---|---|---|
| current-behavior.md | yes | Two existing renderers currently produce layout independently; the convergence changes existing behavior, so the pre-change render/fallback behavior must be captured to scope regression and prove output equivalence. |
| proposal.md | no | |
| spec.md | no | |
| design.md | yes | Architecture Review Required is yes — `spec-architect` must record the primary/fallback boundary, the shared-reflow extraction, and fallback-trigger semantics before `implementation-planner` runs. |
| qa-report.md | no | Routine pass/fail belongs in `agent-log/*.yml`; promote to yes only if blocking findings or approved-with-risk arise. |
| regression-report.md | no | Regression coverage is run via golden-regression tests; durable prose only needed if a behavior delta is accepted. |
| visual-review-report.md | yes | Output is rendered PDF layout; layout-correctness across two paths needs a durable visual evidence bundle proving fitz and ReportLab paths produce equivalent, correct layout. |
| monkey-test-report.md | no | |
| stress-soak-report.md | no | Rendering is per-document and not a long-running/auto-refresh/queue surface; no soak/stress trigger. |

Artifact minimization rule: later artifacts reference `current-behavior.md` and `design.md` by path/section rather than restating rationale.

## Required Contracts
- API: none (no endpoint shape change; rendering is internal to the PDF processor)
- CSS/UI: none (rendered PDF is not governed by `css-contract.md` web tokens)
- Env: none
- Data shape: `contracts/data/data-shape-contract.md` — confirm/extend the `TranslatableDocument` / `TranslatableElement` IR consumption contract (ElementType, reading_order, bbox) that both render paths must honor.
- Business logic: `contracts/business/business-rules.md` — record the fitz-primary / ReportLab-fallback selection rule and the layout-output-consistency guarantee as a business/behavior rule.
- CI/CD: `contracts/ci/ci-gate-contract.md` — update if a new golden-regression or visual-equivalence gate is added.

## Required Tests
- unit: shared IR-bbox reflow logic; per-renderer adapter for fitz path and ReportLab path
- contract: data-shape boundary — both renderers consume the same `TranslatableDocument` IR (ElementType + reading_order + bbox) and honor it
- integration: end-to-end `pdf_processor` → render via fitz primary path; forced-fallback path renders via ReportLab; both produce layout from identical IR
- E2E: covered by golden-regression (no additional E2E surface)
- visual: layout-equivalence — fitz vs ReportLab render of the same IR against golden PDF fixtures (`tests/fixtures/golden/pdf/`)
- data-boundary: malformed / incomplete IR (missing reading_order or bbox, unknown ElementType) handled consistently on both paths
- resilience: fitz-path failure correctly triggers ReportLab fallback without losing layout fidelity
- fuzz/monkey: none
- stress: none
- soak: none

## Required Agents
- spec-architect — author `design.md`: primary/fallback boundary, shared-reflow extraction, fallback-trigger and output-equivalence semantics (must precede implementation-planner)
- implementation-planner — convert design + contracts + tests into the execution packet
- backend-engineer — implement convergence in `app/backend/renderers/` and the `pdf_processor` call path
- test-strategist — derive the AC → test mapping and own data-boundary / regression / equivalence coverage
- contract-reviewer — confirm data-shape (IR boundary) and business-rule (fallback selection) contract changes
- visual-reviewer — verify layout-equivalence visual evidence across both render paths
- qa-reviewer — release readiness and regression sign-off

## Inferred Acceptance Criteria
- AC-1: A single shared IR-bbox reflow component computes element placement from `TranslatableDocument` (ElementType, reading_order, bbox) and is consumed by both the fitz primary path and the ReportLab fallback path.
- AC-2: The fitz path is selected as the primary renderer for PDF output by default.
- AC-3: When the fitz path fails (or its documented fallback trigger fires), the system falls back to ReportLab and still produces a rendered PDF without aborting the job.
- AC-4: For a given `TranslatableDocument` IR, the fitz path and the ReportLab path produce layout that is consistent/equivalent within the documented tolerance against golden PDF fixtures.
- AC-5: Reading order and element typing from the IR are preserved in the rendered output on both paths (no element reordering or type-driven layout loss).
- AC-6: Malformed or incomplete IR (missing bbox/reading_order, unknown ElementType) is handled deterministically and identically on both render paths.
- AC-7: Existing golden-regression tests for PDF rendering pass (no unexplained layout regression) and new equivalence/data-boundary tests are added.

## Tasks Not Applicable
- not-applicable: 2.1, 2.2, 2.3, 3.5, 4.2, 4.3, 5.1

## Clarifications and Assumptions
- Assumption: ReportLab is an existing dependency (`reportlab>=4.0.0` in requirements.txt); available as fallback backend without adding a new dependency.
- Assumption: "consistent layout" means equivalence within a documented numeric tolerance against golden PDF fixtures, not byte-identical PDFs; spec-architect defines the tolerance and fallback-trigger condition in `design.md`.
- Assumption: The IR data shape (ElementType wire values, reading_order) is stabilized by p2-ir-document-model and p2-layout-detection; this change consumes those contracts and does not redefine them.
- Note: Per CLAUDE.md promoted learnings, if `cdd-kit gate` forces a higher tier on vocabulary alone, apply `tier-floor-override` with rationale that no migration, auth, or cache work is performed.

## Context Manifest Draft

### Affected Surfaces
- PDF rendering layer (`app/backend/renderers/`)
- PDF processing entry path (`app/backend/processors/pdf_processor.py`)
- IR consumption (`app/backend/models/translatable_document.py`) — read-only contract for renderers
- shared bbox utilities (`app/backend/utils/bbox_utils.py`)

### Allowed Paths
- specs/changes/p2-renderer-convergence/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/renderers/
- app/backend/processors/pdf_processor.py
- app/backend/parsers/pdf_parser.py
- app/backend/parsers/layout_detector.py
- app/backend/models/translatable_document.py
- app/backend/utils/bbox_utils.py
- app/backend/utils/font_utils.py
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md
- contracts/ci/ci-gate-contract.md
- docs/p2-change-requests.md
- docs/adr/0002-ir-elementtype-serialized-values.md
- docs/adr/0003-layout-detector-runtime-and-failure-mode.md
- tests/test_coordinate_renderer.py
- tests/test_inline_renderer.py
- tests/test_text_region_renderer.py
- tests/test_pdf_generator.py
- tests/test_pdf_parser.py
- tests/test_ir_pipeline_decoupling.py
- tests/test_translatable_document.py
- tests/test_bbox_utils.py
- tests/test_golden_regression.py
- tests/test_layout_detector.py
- tests/fixtures/golden/pdf/
- tests/fixtures/test.pdf
- tests/templates/data-boundary/malformed-data.spec.md
- tests/templates/resilience/api-failure.spec.md

### Agent Work Packets

#### spec-architect
- specs/changes/p2-renderer-convergence/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/renderers/
- app/backend/processors/pdf_processor.py
- app/backend/parsers/pdf_parser.py
- app/backend/models/translatable_document.py
- app/backend/utils/bbox_utils.py
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md
- docs/p2-change-requests.md
- docs/adr/0002-ir-elementtype-serialized-values.md
- docs/adr/0003-layout-detector-runtime-and-failure-mode.md

#### implementation-planner
- specs/changes/p2-renderer-convergence/
- app/backend/renderers/
- app/backend/processors/pdf_processor.py
- app/backend/models/translatable_document.py
- app/backend/utils/bbox_utils.py
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md

#### backend-engineer
- specs/changes/p2-renderer-convergence/
- app/backend/renderers/
- app/backend/processors/pdf_processor.py
- app/backend/parsers/pdf_parser.py
- app/backend/parsers/layout_detector.py
- app/backend/models/translatable_document.py
- app/backend/utils/bbox_utils.py
- app/backend/utils/font_utils.py
- tests/test_coordinate_renderer.py
- tests/test_inline_renderer.py
- tests/test_text_region_renderer.py
- tests/test_pdf_generator.py
- tests/test_ir_pipeline_decoupling.py

#### test-strategist
- specs/changes/p2-renderer-convergence/
- app/backend/renderers/
- app/backend/models/translatable_document.py
- app/backend/utils/bbox_utils.py
- tests/
- tests/fixtures/golden/pdf/
- tests/templates/data-boundary/malformed-data.spec.md
- tests/templates/resilience/api-failure.spec.md

#### contract-reviewer
- specs/changes/p2-renderer-convergence/
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md
- contracts/ci/ci-gate-contract.md

#### visual-reviewer
- specs/changes/p2-renderer-convergence/
- tests/fixtures/golden/pdf/
- tests/test_golden_regression.py

#### qa-reviewer
- specs/changes/p2-renderer-convergence/
- tests/
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md

### Context Expansion Requests
- request-id: CER-001
  requested_paths:
    - app/backend/requirements.txt
  reason: Confirm ReportLab is an existing dependency before treating it as the fallback backend.
  status: resolved — `reportlab>=4.0.0` confirmed in requirements.txt; no new dependency needed.
