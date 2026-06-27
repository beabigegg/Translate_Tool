# Change Classification

## Change Types
- primary: refactor (PDF renderer/parser/processor architecture), feature-enhancement (reading-order model, iterative scale-fit, DPI upgrade, OCR path)
- secondary: business-logic-change (formula pass-through rule, scanned→OCR routing, truncation→scale-fit behavior), data-shape-change (paragraph-aggregated IR, per-span StyleInfo re-application, FORMULA placeholder), ci-cd-change (new layout-fidelity / residual-text gates, OCR-optional gating)

## Lane
- feature

## Risk Level
- high

## Impact Radius
- cross-module (renderers + parsers + processors, plus shared IR in `models/translatable_document.py`)

## Tier
- 1

## Architecture Review Required
- yes
- reason: Introduces new architecture and data-flow changes — BabelDOC-style paragraph-aggregated IR (3.2), LayoutReader-style reading-order model replacing the x-gap heuristic (3.5), an OCR pipeline integration for scanned files (3.7), and a DPI/render-matrix change (3.6). Non-obvious design decisions with module-boundary and IR/data-flow impact, with rollback/compatibility trade-offs against the existing fitz-primary / ReportLab-fallback convergence. `spec-architect` must write `design.md` before `implementation-planner` runs.

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

## Optional Artifacts (default: no — set yes only with explicit reason)
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | Current behavior documented in change-request Known Context; design.md holds per-item deltas. |
| proposal.md | no | Scope fully defined by improvement-plan 3.1–3.7. |
| spec.md | no | No user-facing behavior decision beyond design.md + business-rules. |
| design.md | yes | Architecture Review Required = yes (new IR paradigm, reading-order model, OCR pipeline, DPI change). |
| qa-report.md | no | Promote to yes at QA stage if blocking findings or approved-with-risk arise. |
| regression-report.md | yes | High-risk change to existing PDF behavior with golden PDF regression suite; durable before/after evidence required. |
| visual-review-report.md | yes | PDF layout fidelity is visual output; before/after render evidence bundle is the core proof of this change. |
| monkey-test-report.md | no | No interactive UI surface. |
| stress-soak-report.md | no | Covered by bounded perf/data-boundary test. |

## Required Contracts
- API: none (no new/renamed endpoints; if 3.7 surfaces OCR status, update contracts/api/api-contract.md + re-export openapi.yml)
- CSS/UI: none
- Env: contracts/env/env-contract.md — DPI setting (3.6) and OCR feature flag (3.7) in config.py and .env.example
- Data shape: contracts/data/data-shape-contract.md — paragraph-aggregated IR (3.2), per-span StyleInfo (3.4), FORMULA placeholder (3.7)
- Business logic: contracts/business/business-rules.md — formula pass-through, scanned→OCR routing, iterative-scale-fit behavior, readable-minimum-font threshold
- CI/CD: contracts/ci/ci-gate-contract.md — layout-fidelity gates (residual-text=0, BIoU, truncation-rate, reading-order edit distance, mAP); OCR gate skip-safe when library absent

## Required Tests
- unit: yes — bbox-exact whitening, scale-fit loop, span-style re-application, reading-order ordering, DPI matrix, formula placeholder
- contract: yes — data-shape IR and business-rule conformance
- integration: yes — full PDF parse→detect→translate→render pipeline through pdf_processor.py
- E2E: yes — end-to-end PDF translation against golden fixtures
- visual: yes — render-output assertions / before-after layout comparison
- data-boundary: yes — scanned/blank PDFs, formula-only pages, malformed/high-DPI inputs, non-Latin/RTL multi-line runs
- resilience: yes — OCR lazy-load-absent, detector unavailable, fitz→ReportLab fallback convergence
- fuzz/monkey: no
- stress: no
- soak: no

## Required Agents
1. spec-architect — writes design.md (IR paradigm, reading-order model, OCR integration, DPI change, rollback/compat)
2. contract-reviewer — data / business / env / ci contract conformance
3. test-strategist — acceptance-criteria→test mapping, golden/metric fixtures, OCR-optional gate strategy
4. ci-cd-gatekeeper — writes ci-gates.md
5. implementation-planner — converts design + contracts + tests into sequential 3.1→3.7 execution packet
6. backend-engineer — implements all 7 items
7. visual-reviewer — PDF render fidelity evidence bundle
8. qa-reviewer — Tier 1 release readiness, pre-existing-failure baseline, OCR-gate exclusion sign-off

## Inferred Acceptance Criteria
- AC-1: After rendering, residual source-text count = 0; whitening uses bbox-exact extraction decoupled from PyMuPDF `search_for` (verified on non-Latin / multi-line runs). (3.1)
- AC-2: Lines are aggregated into paragraphs with in-block reflow (BabelDOC IR paradigm); BIoU improves and truncation rate falls vs the PR#3 metrics baseline. (3.2)
- AC-3: Iterative scale-fitting replaces the "shrink to 4pt then truncate" fallback; truncation rate → 0 and the minimum applied font stays ≥ the readable threshold. (3.3)
- AC-4: Per-span StyleInfo (color, bold, italic, underline) is re-applied per span run post-translation; a render assertion confirms output preserves source StyleInfo. (3.4)
- AC-5: A reading-order model (LayoutReader-style) replaces the single x-gap column threshold; normalized edit distance of reading order drops on the multi-column fixture. (3.5)
- AC-6: Parser DPI detection upgrades 72 → ~150–200; layout-detector classification mAP improves on high-DPI documents. (3.6)
- AC-7: FORMULA elements are placeholder-protected and pass through untranslated; scanned files route to the OCR path; formula pass-through tests pass and the scanned-blank test no longer fails. (3.7)
- AC-8: TATR path is unaffected (TABLE_RECOGNITION_ENABLED=false default), fitz→ReportLab fallback still converges, and CI does not require the OCR library unless it is present.

## Tasks Not Applicable
- not-applicable: 2.1, 2.2, 3.5, 4.2, 4.3, 5.1, 6.4

## Clarifications or Assumptions
- Lane: classified as `feature` (refactor/enhancement) — root causes and code locations are documented; planned architectural work, not symptom-driven diagnosis.
- No new REST endpoint; API contract stays untouched unless 3.7 surfaces OCR status via an existing endpoint.
- 3.6 DPI and 3.7 OCR introduce config flags in config.py + env-contract; OCR library stays optional/lazy.
- Tier-floor watch: if cdd-kit gate tier-floors, use tier-floor-override with rationale; genuine tier is 1.
- Atomic-split declined: improvement-plan §8.3/§8.5 mandates single sequential worktree (shared file set).

## Context Manifest Draft

### Affected Surfaces
- PDF render pipeline: `app/backend/renderers/` (fitz/bbox_reflow/coordinate/text-region)
- PDF parsing & layout detection: `app/backend/parsers/pdf_parser.py`, `app/backend/parsers/layout_detector.py`
- PDF orchestration: `app/backend/processors/pdf_processor.py`
- Unified IR: `app/backend/models/translatable_document.py` (paragraph/StyleInfo/FORMULA)
- Render/feature config: `app/backend/config.py`
- Layout-fidelity metrics & golden fixtures: `tests/metrics/`, `tests/fixtures/golden/pdf/`

### Allowed Paths
- specs/changes/pdf-layout-refactor/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/renderers/
- app/backend/parsers/pdf_parser.py
- app/backend/parsers/layout_detector.py
- app/backend/parsers/base.py
- app/backend/processors/pdf_processor.py
- app/backend/processors/orchestrator.py
- app/backend/models/translatable_document.py
- app/backend/config.py
- app/backend/utils/bbox_utils.py
- app/backend/utils/font_utils.py
- app/backend/utils/text_utils.py
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md
- contracts/env/env-contract.md
- contracts/ci/ci-gate-contract.md
- .github/workflows/contract-driven-gates.yml
- tests/test_pdf_parser.py
- tests/test_pdf_generator.py
- tests/test_pdf_render_warnings.py
- tests/test_coordinate_renderer.py
- tests/test_renderer_convergence.py
- tests/test_layout_detector.py
- tests/test_layout_metrics.py
- tests/test_golden_regression.py
- tests/test_text_region_renderer.py
- tests/metrics/
- tests/fixtures/golden/pdf/
- tests/fixtures/test.pdf

### Required Contracts
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md
- contracts/env/env-contract.md
- contracts/ci/ci-gate-contract.md

### Required Tests
- tests/test_pdf_parser.py (existing — verify non-regression + DPI assertions)
- tests/test_pdf_generator.py (existing — verify non-regression)
- tests/test_pdf_render_warnings.py (existing — verify non-regression)
- tests/test_coordinate_renderer.py (existing — verify non-regression)
- tests/test_renderer_convergence.py (existing — fitz/ReportLab fallback convergence)
- tests/test_layout_detector.py (existing — mAP/DPI regression)
- tests/test_layout_metrics.py (existing — BIoU/residual/truncation metrics)
- tests/test_golden_regression.py (existing/extended — before/after golden fixtures)
- tests/test_pdf_layout_refactor.py (NEW — AC-1 through AC-8 unit/integration/resilience)

### Agent Work Packets

#### spec-architect
- specs/changes/pdf-layout-refactor/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/renderers/
- app/backend/parsers/pdf_parser.py
- app/backend/parsers/layout_detector.py
- app/backend/processors/pdf_processor.py
- app/backend/models/translatable_document.py
- app/backend/config.py
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md

#### contract-reviewer
- specs/changes/pdf-layout-refactor/
- contracts/

#### test-strategist
- specs/changes/pdf-layout-refactor/
- app/backend/renderers/
- app/backend/parsers/pdf_parser.py
- app/backend/parsers/layout_detector.py
- app/backend/processors/pdf_processor.py
- app/backend/models/translatable_document.py
- tests/

#### ci-cd-gatekeeper
- specs/changes/pdf-layout-refactor/
- .github/workflows/contract-driven-gates.yml
- contracts/ci/ci-gate-contract.md

#### implementation-planner
- specs/changes/pdf-layout-refactor/
- app/backend/renderers/
- app/backend/parsers/pdf_parser.py
- app/backend/parsers/layout_detector.py
- app/backend/processors/pdf_processor.py
- app/backend/models/translatable_document.py
- app/backend/config.py
- contracts/

#### backend-engineer
- specs/changes/pdf-layout-refactor/
- app/backend/renderers/
- app/backend/parsers/pdf_parser.py
- app/backend/parsers/layout_detector.py
- app/backend/parsers/base.py
- app/backend/processors/pdf_processor.py
- app/backend/processors/orchestrator.py
- app/backend/models/translatable_document.py
- app/backend/config.py
- app/backend/utils/bbox_utils.py
- app/backend/utils/font_utils.py
- app/backend/utils/text_utils.py
- tests/
- contracts/

#### visual-reviewer
- specs/changes/pdf-layout-refactor/
- tests/fixtures/golden/pdf/
- tests/metrics/

#### qa-reviewer
- specs/changes/pdf-layout-refactor/
- contracts/
- tests/

### Context Expansion Requests
- (none at classification time — all candidate paths present in project-map.md / contracts-index.md)
