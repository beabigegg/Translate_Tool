# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- PPTX processing (`app/backend/processors/pptx_processor.py` collection loop + restore path)
- Business behavior contract (`contracts/business/business-rules.md`)

## Allowed Paths
- specs/changes/pptx-group-shape-collection/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/processors/pptx_processor.py
- app/backend/config.py
- contracts/business/business-rules.md
- contracts/CHANGELOG.md
- docs/adr/0018-nested-table-frame-routing.md
- tests/test_docx_nested_tables.py
- tests/test_pptx_parser.py
- tests/test_pptx_group_shapes.py

## Required Contracts
- contracts/business/business-rules.md

## Required Tests
- tests/test_pptx_group_shapes.py
- tests/test_pptx_parser.py
- tests/test_docx_nested_tables.py

## Agent Work Packets
<!-- One sub-section per required agent. Each path list must be a subset of Allowed Paths above.
     Add or remove sub-sections to match Required Agents in change-classification.md.
     These sub-sections are documentation only — gate enforces Allowed Paths, not individual packets. -->

### change-classifier
- specs/changes/<change-id>/
- specs/context/project-map.md
- specs/context/contracts-index.md

### <implementation-agent>
<!-- Replace with actual agent name, e.g. backend-engineer, frontend-engineer -->
- specs/changes/<change-id>/
- contracts/
- src/
- tests/

### <review-agent>
<!-- Replace with actual agent name, e.g. contract-reviewer, qa-reviewer -->
- specs/changes/<change-id>/
- contracts/

## Context Expansion Requests

<!--
Agents must request context expansion instead of reading outside their work
packet. Format example for real requests:

- request-id: CER-001
  requested_paths:
    - src/example.ts
  reason: why this file is required
  status: pending
-->
-

## Approved Expansions
-
