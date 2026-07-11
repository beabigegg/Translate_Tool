# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- Translation acceptance — table-cell path (`table_serializer.parse_json` / `json_translation.build_table_payload`)
- Translation acceptance — body/segment path (`translation_service.translate_texts` / client `translate_once`)
- New shared length-guard helper (composition model + recovery)
- Configuration constants (`config.py`)

## Allowed Paths
- specs/changes/truncation-length-guard/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/processors/docx_processor.py
- app/backend/utils/table_serializer.py
- app/backend/utils/json_translation.py
- app/backend/services/translation_service.py
- app/backend/utils/text_utils.py
- app/backend/utils/translation_verification.py
- app/backend/utils/length_guard.py
- app/backend/config.py
- app/backend/models/translatable_document.py
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- contracts/CHANGELOG.md
- docs/adr/0020-truncation-length-guard.md
- tests/test_length_guard.py
- tests/test_json_translation_body.py
- tests/test_docx_nested_tables.py

## Required Contracts
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md (conditional — only if an IR marker is added/repurposed)

## Required Tests
- tests/test_length_guard.py
- tests/test_json_translation_body.py
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
