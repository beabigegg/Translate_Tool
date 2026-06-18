# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- Backend text-region rendering (expansion / fit cascade)
- Backend font selection (metric-compatible fallback chain)
- Shared reflow path (bbox_reflow.py) and converged fitz renderer
- IR / data-shape boundary (truncation marker)

## Allowed Paths
- specs/changes/p2-text-expansion/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/renderers/text_region_renderer.py
- app/backend/utils/font_utils.py
- app/backend/renderers/bbox_reflow.py
- app/backend/renderers/fitz_renderer.py
- app/backend/renderers/base.py
- app/backend/renderers/__init__.py
- app/backend/models/translatable_document.py
- app/backend/utils/bbox_utils.py
- app/backend/utils/text_utils.py
- app/backend/fonts/
- app/backend/renderers/coordinate_renderer.py
- app/backend/renderers/inline_renderer.py
- app/backend/renderers/pdf_generator.py
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- contracts/ci/ci-gate-contract.md
- .github/workflows/contract-driven-gates.yml
- tests/test_text_region_renderer.py
- tests/test_font_utils.py
- tests/test_renderer_convergence.py
- tests/test_golden_regression.py
- tests/test_translatable_document.py
- tests/fixtures/golden/

## Required Contracts
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- contracts/ci/ci-gate-contract.md (review only if benchmark gate added)

## Required Tests
- tests/test_text_region_renderer.py
- tests/test_font_utils.py
- tests/test_renderer_convergence.py
- tests/test_golden_regression.py
- tests/test_translatable_document.py
- tests/fixtures/golden/

## Agent Work Packets

### spec-architect
- specs/changes/p2-text-expansion/
- specs/context/project-map.md
- specs/context/contracts-index.md
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- app/backend/renderers/text_region_renderer.py
- app/backend/renderers/bbox_reflow.py
- app/backend/renderers/fitz_renderer.py
- app/backend/renderers/base.py
- app/backend/utils/font_utils.py
- app/backend/models/translatable_document.py

### contract-reviewer
- specs/changes/p2-text-expansion/
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- contracts/ci/ci-gate-contract.md

### test-strategist
- specs/changes/p2-text-expansion/
- tests/test_text_region_renderer.py
- tests/test_font_utils.py
- tests/test_renderer_convergence.py
- tests/test_golden_regression.py
- tests/fixtures/golden/
- app/backend/renderers/text_region_renderer.py
- app/backend/utils/font_utils.py

### ci-cd-gatekeeper
- specs/changes/p2-text-expansion/
- contracts/ci/ci-gate-contract.md
- .github/workflows/contract-driven-gates.yml

### implementation-planner
- specs/changes/p2-text-expansion/
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- app/backend/renderers/text_region_renderer.py
- app/backend/renderers/bbox_reflow.py
- app/backend/renderers/fitz_renderer.py
- app/backend/renderers/base.py
- app/backend/utils/font_utils.py
- app/backend/models/translatable_document.py
- tests/test_text_region_renderer.py
- tests/test_font_utils.py

### backend-engineer
- specs/changes/p2-text-expansion/
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- app/backend/renderers/text_region_renderer.py
- app/backend/renderers/bbox_reflow.py
- app/backend/renderers/fitz_renderer.py
- app/backend/renderers/base.py
- app/backend/utils/font_utils.py
- app/backend/utils/bbox_utils.py
- app/backend/utils/text_utils.py
- app/backend/models/translatable_document.py
- app/backend/fonts/

### visual-reviewer
- specs/changes/p2-text-expansion/
- tests/fixtures/golden/
- tests/test_golden_regression.py

### qa-reviewer
- specs/changes/p2-text-expansion/
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md

## Context Expansion Requests

- request-id: CER-001
  requested_paths:
    - app/backend/renderers/coordinate_renderer.py
    - app/backend/renderers/inline_renderer.py
    - app/backend/renderers/pdf_generator.py
  reason: verify no duplicated expansion logic in legacy/dual render paths (AC-6); confirm consumers route through shared bbox_reflow path
  status: approved

## Approved Expansions
- CER-001 approved: spec-architect identified that the primary cascade lives in fitz_renderer.py; backend-engineer must grep legacy paths to confirm no duplicated expansion logic (AC-6)
