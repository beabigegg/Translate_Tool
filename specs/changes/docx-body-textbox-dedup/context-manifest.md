# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- DOCX processor body + table-cell paragraph extraction and restore-matching (`app/backend/processors/docx_processor.py`)
- Business rules contract (BR-115 scope)

## Allowed Paths
- specs/changes/docx-body-textbox-dedup/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/processors/docx_processor.py
- contracts/business/business-rules.md
- contracts/CHANGELOG.md
- tests/test_docx_header_footer.py
- tests/test_docx_parser.py
- tests/test_docx_nested_tables.py
- tests/test_golden_regression.py
- tests/test_docx_body_textbox_dedup.py

## Required Contracts
- contracts/business/business-rules.md

## Required Tests
- tests/test_docx_header_footer.py
- tests/test_docx_parser.py
- tests/test_docx_nested_tables.py
- tests/test_golden_regression.py
- tests/test_docx_body_textbox_dedup.py

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
