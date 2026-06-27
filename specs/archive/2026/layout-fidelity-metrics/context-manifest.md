# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- test suite (tests/metrics/, tests/fixtures/golden/)
- read-only reference: IR data model (BoundingBox)

## Allowed Paths
- specs/changes/layout-fidelity-metrics/
- specs/context/project-map.md
- specs/context/contracts-index.md
- tests/metrics/
- tests/fixtures/golden/
- tests/test_layout_metrics.py
- tests/conftest.py
- app/backend/models/translatable_document.py

## Required Contracts
- none

## Required Tests
- tests/test_layout_metrics.py
- tests/metrics/

## Agent Work Packets

### implementation-planner
- specs/changes/layout-fidelity-metrics/
- specs/context/project-map.md
- app/backend/models/translatable_document.py

### test-strategist
- specs/changes/layout-fidelity-metrics/
- tests/metrics/
- tests/fixtures/golden/
- tests/test_layout_metrics.py
- tests/conftest.py
- app/backend/models/translatable_document.py

### contract-reviewer
- specs/changes/layout-fidelity-metrics/
- specs/context/contracts-index.md
- app/backend/models/translatable_document.py

### qa-reviewer
- specs/changes/layout-fidelity-metrics/
- tests/metrics/
- tests/test_layout_metrics.py

## Context Expansion Requests
- request-id: CER-001
  requested_paths:
    - app/backend/renderers/bbox_reflow.py
    - app/backend/utils/bbox_utils.py
  reason: If implementer needs existing bbox/IoU geometry conventions to keep metric consistent with renderer output. Leave pending; approve only if translatable_document.py is insufficient.
  status: pending

## Approved Expansions
-
