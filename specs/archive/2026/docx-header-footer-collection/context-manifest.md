# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- DOCX header/footer collection + restore (`app/backend/processors/docx_processor.py`)
- COM postprocess coordination (`app/backend/processors/com_helpers.py`)
- Business rule for native path + COM mutual exclusion (`contracts/business/business-rules.md`)

## Allowed Paths
- specs/changes/docx-header-footer-collection/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/processors/docx_processor.py
- app/backend/processors/com_helpers.py
- app/backend/processors/orchestrator.py
- contracts/business/business-rules.md
- contracts/CHANGELOG.md
- docs/adr/0018-nested-table-frame-routing.md
- docs/adr/0019-native-header-footer-com-shape-boundary.md
- tests/test_docx_nested_tables.py
- tests/test_docx_parser.py
- tests/test_golden_regression.py
- tests/test_docx_header_footer.py

## Required Contracts
- contracts/business/business-rules.md

## Required Tests
- tests/test_docx_nested_tables.py
- tests/test_docx_parser.py
- tests/test_golden_regression.py
- tests/test_docx_header_footer.py

## Agent Work Packets

### change-classifier
- specs/changes/docx-header-footer-collection/
- specs/context/project-map.md
- specs/context/contracts-index.md

### spec-architect
- specs/changes/docx-header-footer-collection/
- app/backend/processors/docx_processor.py
- app/backend/processors/com_helpers.py
- contracts/business/business-rules.md
- docs/adr/0018-nested-table-frame-routing.md

### contract-reviewer
- specs/changes/docx-header-footer-collection/
- contracts/business/business-rules.md
- contracts/CHANGELOG.md

### test-strategist
- specs/changes/docx-header-footer-collection/
- app/backend/processors/docx_processor.py
- tests/test_docx_header_footer.py
- tests/test_docx_nested_tables.py
- tests/test_docx_parser.py
- tests/test_golden_regression.py

### implementation-planner
- specs/changes/docx-header-footer-collection/
- app/backend/processors/docx_processor.py
- app/backend/processors/com_helpers.py
- app/backend/processors/orchestrator.py
- contracts/business/business-rules.md

### backend-engineer
- specs/changes/docx-header-footer-collection/
- app/backend/processors/docx_processor.py
- app/backend/processors/com_helpers.py
- app/backend/processors/orchestrator.py
- tests/test_docx_header_footer.py
- tests/test_docx_nested_tables.py

### qa-reviewer
- specs/changes/docx-header-footer-collection/
- contracts/business/business-rules.md

## Context Expansion Requests
-

## Approved Expansions
- CER-001: read `app/backend/processors/docx_processor.py`, `com_helpers.py`, `orchestrator.py` — the `_collect_docx_segments` / `_process_container_content` / `translate_docx` seams and the `postprocess_docx_shapes_with_word` call site must be read to author design.md and the plan. Approved by main Claude (already in Allowed Paths).
