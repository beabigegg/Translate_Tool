# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- fitz PDF renderer (`app/backend/renderers/fitz_renderer.py`): `_generate_overlay` and `_generate_side_by_side` masking geometry
- PDF golden-regression test surface

## Allowed Paths
- specs/changes/p2-table-border-protection/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/renderers/fitz_renderer.py
- app/backend/renderers/bbox_reflow.py
- app/backend/renderers/base.py
- app/backend/utils/bbox_utils.py
- tests/test_golden_regression.py
- tests/test_pdf_generator.py
- tests/test_coordinate_renderer.py
- tests/fixtures/golden/pdf/
- tests/fixtures/test.pdf
- .github/workflows/contract-driven-gates.yml
- contracts/ci/ci-gate-contract.md

## Required Contracts
- none

## Required Tests
- tests/test_golden_regression.py
- tests/test_pdf_generator.py

## Agent Work Packets

### change-classifier
- specs/changes/p2-table-border-protection/
- specs/context/project-map.md
- specs/context/contracts-index.md

### bug-fix-engineer
- specs/changes/p2-table-border-protection/
- app/backend/renderers/fitz_renderer.py
- app/backend/renderers/bbox_reflow.py
- app/backend/renderers/base.py
- app/backend/utils/bbox_utils.py
- tests/test_golden_regression.py
- tests/test_pdf_generator.py
- tests/fixtures/golden/pdf/
- tests/fixtures/test.pdf

### test-strategist
- specs/changes/p2-table-border-protection/
- tests/test_golden_regression.py
- tests/test_pdf_generator.py
- tests/test_coordinate_renderer.py
- tests/fixtures/golden/pdf/
- tests/fixtures/test.pdf

### ci-cd-gatekeeper
- specs/changes/p2-table-border-protection/
- .github/workflows/contract-driven-gates.yml

### implementation-planner
- specs/changes/p2-table-border-protection/
- app/backend/renderers/fitz_renderer.py
- app/backend/renderers/bbox_reflow.py
- app/backend/utils/bbox_utils.py

### backend-engineer
- specs/changes/p2-table-border-protection/
- app/backend/renderers/fitz_renderer.py
- app/backend/renderers/bbox_reflow.py
- app/backend/renderers/base.py
- app/backend/utils/bbox_utils.py
- tests/test_pdf_generator.py
- tests/test_golden_regression.py
- tests/fixtures/golden/pdf/

### visual-reviewer
- specs/changes/p2-table-border-protection/
- tests/fixtures/golden/pdf/

### qa-reviewer
- specs/changes/p2-table-border-protection/

## Context Expansion Requests

- request-id: CER-001
  requested_paths:
    - app/backend/renderers/base.py
  reason: Renderer base class — needed if masking/geometry helpers are inherited rather than self-contained in fitz_renderer.py. Pre-authorized in Allowed Paths to avoid blocking bug-fix-engineer.
  status: approved

## Approved Expansions
- CER-001 approved: base.py included in Allowed Paths for bug-fix-engineer and backend-engineer work packets.
