# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- Office output processors (DOCX, XLSX, PPTX)
- Orchestrator output_mode routing
- API request schema (output_mode enum — new `bilingual` value)
- API contract + OpenAPI export
- Data-shape contract (per-format output structure)

## Allowed Paths
- specs/changes/office-output-mode/
- specs/context/project-map.md
- specs/context/contracts-index.md
- docs/improvement-plan.md
- app/backend/processors/docx_processor.py
- app/backend/processors/xlsx_processor.py
- app/backend/processors/pptx_processor.py
- app/backend/processors/orchestrator.py
- app/backend/api/schemas.py
- contracts/api/api-contract.md
- contracts/api/openapi.yml
- contracts/api/openapi.json
- contracts/data/data-shape-contract.md
- tests/test_output_mode_processors.py
- tests/test_output_mode_orchestrator.py
- tests/test_output_mode_api.py
- tests/fixtures/golden/docx/
- tests/fixtures/golden/pptx/
- .cdd/code-map.yml

## Required Contracts
-

## Required Tests
-

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
