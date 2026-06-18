# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- PDF rendering layer (`app/backend/renderers/`)
- PDF processing entry path (`app/backend/processors/pdf_processor.py`)
- IR consumption (`app/backend/models/translatable_document.py`) — read-only contract for renderers
- shared bbox utilities (`app/backend/utils/bbox_utils.py`)

## Allowed Paths
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
- .github/workflows/contract-driven-gates.yml

## Required Contracts
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md
- contracts/ci/ci-gate-contract.md (only if a new equivalence/regression gate is added)

## Required Tests
- tests/test_coordinate_renderer.py
- tests/test_inline_renderer.py
- tests/test_text_region_renderer.py
- tests/test_pdf_generator.py
- tests/test_ir_pipeline_decoupling.py
- tests/test_golden_regression.py
- tests/fixtures/golden/pdf/

## Agent Work Packets

### spec-architect
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

### implementation-planner
- specs/changes/p2-renderer-convergence/
- app/backend/renderers/
- app/backend/processors/pdf_processor.py
- app/backend/models/translatable_document.py
- app/backend/utils/bbox_utils.py
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md

### backend-engineer
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

### test-strategist
- specs/changes/p2-renderer-convergence/
- app/backend/renderers/
- app/backend/models/translatable_document.py
- app/backend/utils/bbox_utils.py
- tests/
- tests/fixtures/golden/pdf/
- tests/templates/data-boundary/malformed-data.spec.md
- tests/templates/resilience/api-failure.spec.md

### ci-cd-gatekeeper
- specs/changes/p2-renderer-convergence/
- contracts/ci/ci-gate-contract.md
- .github/workflows/contract-driven-gates.yml

### contract-reviewer
- specs/changes/p2-renderer-convergence/
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md
- contracts/ci/ci-gate-contract.md

### visual-reviewer
- specs/changes/p2-renderer-convergence/
- tests/fixtures/golden/pdf/
- tests/test_golden_regression.py

### qa-reviewer
- specs/changes/p2-renderer-convergence/
- tests/
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md

## Context Expansion Requests
- request-id: CER-001
  requested_paths:
    - app/backend/requirements.txt
  reason: Confirm ReportLab is an existing dependency before treating it as the fallback backend.
  status: resolved — `reportlab>=4.0.0` confirmed in requirements.txt; no new dependency needed.

## Approved Expansions
-
