# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- PDF render pipeline: `app/backend/renderers/` (fitz/bbox_reflow/coordinate/text-region)
- PDF parsing & layout detection: `app/backend/parsers/pdf_parser.py`, `app/backend/parsers/layout_detector.py`
- PDF orchestration: `app/backend/processors/pdf_processor.py`
- Unified IR: `app/backend/models/translatable_document.py` (paragraph/StyleInfo/FORMULA)
- Render/feature config: `app/backend/config.py`
- Layout-fidelity metrics & golden fixtures: `tests/metrics/`, `tests/fixtures/golden/pdf/`

## Allowed Paths
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

## Required Contracts
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md
- contracts/env/env-contract.md
- contracts/ci/ci-gate-contract.md

## Required Tests
- tests/test_pdf_parser.py (existing — verify non-regression + DPI assertions)
- tests/test_pdf_generator.py (existing — verify non-regression)
- tests/test_pdf_render_warnings.py (existing — verify non-regression)
- tests/test_coordinate_renderer.py (existing — verify non-regression)
- tests/test_renderer_convergence.py (existing — fitz/ReportLab fallback convergence)
- tests/test_layout_detector.py (existing — mAP/DPI regression)
- tests/test_layout_metrics.py (existing — BIoU/residual/truncation metrics)
- tests/test_golden_regression.py (existing/extended — before/after golden fixtures)
- tests/test_pdf_layout_refactor.py (NEW — AC-1 through AC-8 unit/integration/resilience)

## Agent Work Packets

### change-classifier
- specs/changes/pdf-layout-refactor/
- specs/context/project-map.md
- specs/context/contracts-index.md

### spec-architect
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

### contract-reviewer
- specs/changes/pdf-layout-refactor/
- contracts/

### test-strategist
- specs/changes/pdf-layout-refactor/
- app/backend/renderers/
- app/backend/parsers/pdf_parser.py
- app/backend/parsers/layout_detector.py
- app/backend/processors/pdf_processor.py
- app/backend/models/translatable_document.py
- tests/

### ci-cd-gatekeeper
- specs/changes/pdf-layout-refactor/
- .github/workflows/contract-driven-gates.yml
- contracts/ci/ci-gate-contract.md

### implementation-planner
- specs/changes/pdf-layout-refactor/
- app/backend/renderers/
- app/backend/parsers/pdf_parser.py
- app/backend/parsers/layout_detector.py
- app/backend/processors/pdf_processor.py
- app/backend/models/translatable_document.py
- app/backend/config.py
- contracts/

### backend-engineer
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

### visual-reviewer
- specs/changes/pdf-layout-refactor/
- tests/fixtures/golden/pdf/
- tests/metrics/

### qa-reviewer
- specs/changes/pdf-layout-refactor/
- contracts/
- tests/

## Context Expansion Requests
- (none at classification time)

## Approved Expansions
-
