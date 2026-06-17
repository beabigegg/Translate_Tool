# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- PDF rendering — font buffer loading in `app/backend/renderers/pdf_generator.py`

## Allowed Paths
- specs/changes/p1-font-lru-cache/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/renderers/pdf_generator.py
- app/backend/utils/font_utils.py
- app/backend/fonts/
- tests/test_pdf_generator.py
- contracts/
- .github/workflows/contract-driven-gates.yml

## Required Contracts
- none

## Required Tests
- tests/test_pdf_generator.py

## Agent Work Packets

### change-classifier
- specs/changes/p1-font-lru-cache/
- specs/context/project-map.md
- specs/context/contracts-index.md

### contract-reviewer
- specs/changes/p1-font-lru-cache/
- contracts/

### test-strategist
- specs/changes/p1-font-lru-cache/
- app/backend/renderers/pdf_generator.py
- tests/test_pdf_generator.py

### ci-cd-gatekeeper
- specs/changes/p1-font-lru-cache/
- .github/workflows/contract-driven-gates.yml

### implementation-planner
- specs/changes/p1-font-lru-cache/
- app/backend/renderers/pdf_generator.py
- app/backend/utils/font_utils.py
- tests/test_pdf_generator.py

### backend-engineer
- specs/changes/p1-font-lru-cache/
- app/backend/renderers/pdf_generator.py
- app/backend/utils/font_utils.py
- app/backend/fonts/
- tests/test_pdf_generator.py

### qa-reviewer
- specs/changes/p1-font-lru-cache/
- tests/test_pdf_generator.py

## Context Expansion Requests

- request-id: CER-001
  requested_paths:
    - app/backend/renderers/pdf_generator.py
    - app/backend/utils/font_utils.py
  reason: Implementation and planning agents need to confirm the actual _insert_text_in_rect location and any existing font-loading helper before implementing the cache.
  status: approved

## Approved Expansions
- CER-001 approved: app/backend/renderers/pdf_generator.py + app/backend/utils/font_utils.py added to Allowed Paths.
