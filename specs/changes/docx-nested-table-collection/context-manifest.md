# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- DOCX collection path — the `<w:tbl>` branch of the block walk in `app/backend/processors/docx_processor.py` (~L261-285) and its `cell` segment emission
- Shared table-serialization / JSON-payload tail — `app/backend/utils/table_serializer.py`, `app/backend/utils/json_translation.py`, `app/backend/utils/translation_helpers.py`
- Unified IR — `app/backend/models/translatable_document.py` (`table_id`, coordinates) for nested-table identity
- BR-109 document-context sampler in `app/backend/processors/orchestrator.py` — walks only `doc.tables` (top level), so a nested-only document samples thin. Read-only context; affects the one-sentence summary, not output text.
- Contracts — `contracts/business/business-rules.md` (BR-81 reconciliation, new routing/collection rule), `contracts/data/data-shape-contract.md` (§Table Serialization Wire Format)

## Allowed Paths
- specs/changes/docx-nested-table-collection/
- specs/context/project-map.md
- specs/context/contracts-index.md
- .cdd/code-map.yml
- app/backend/processors/docx_processor.py
- app/backend/parsers/docx_parser.py
- app/backend/utils/table_serializer.py
- app/backend/utils/json_translation.py
- app/backend/utils/translation_helpers.py
- app/backend/processors/orchestrator.py
- app/backend/models/translatable_document.py
- app/backend/config.py
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- contracts/CHANGELOG.md
- docs/adr/0017-json-structured-translation-seam.md
- tests/test_docx_parser.py
- tests/test_translatable_document.py
- tests/test_table_serialization.py
- tests/test_table_context_translation.py
- tests/test_output_mode_processors.py
- tests/test_output_mode_orchestrator.py
- tests/test_translation_service.py
- tests/test_orchestrator_phase0.py
- tests/test_json_translation_body.py
- tests/test_json_translation_prompt.py
- tests/fixtures/
- tests/conftest.py

## Required Contracts
- contracts/business/business-rules.md (new routing/collection rule; BR-81 reconciliation)
- contracts/data/data-shape-contract.md (§Table Serialization Wire Format — nested-table identity and payload boundaries; legacy pipe-grid degrade note)

## Required Tests
- tests/test_docx_parser.py (`test_parse_deduplication` — BR-81 dedup)
- tests/test_translatable_document.py (dedup on the IR)
- tests/test_table_serialization.py, tests/test_table_context_translation.py (the wire format and whole-table path)
- tests/test_output_mode_processors.py, tests/test_translation_service.py, tests/test_orchestrator_phase0.py (DOCX table-cell collection)
- new: a self-built nested `.docx` fixture, recursive-walk character parity, merged-cell single-emission, false-positive routing guard, depth guard, flag-OFF degrade

## Agent Work Packets

### change-classifier
- specs/changes/docx-nested-table-collection/
- specs/context/project-map.md
- specs/context/contracts-index.md

### spec-architect
- specs/changes/docx-nested-table-collection/
- .cdd/code-map.yml
- app/backend/processors/docx_processor.py
- app/backend/utils/table_serializer.py
- app/backend/utils/json_translation.py
- app/backend/models/translatable_document.py
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- docs/adr/0017-json-structured-translation-seam.md

### contract-reviewer
- specs/changes/docx-nested-table-collection/
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md

### test-strategist
- specs/changes/docx-nested-table-collection/
- .cdd/code-map.yml
- app/backend/processors/docx_processor.py
- app/backend/utils/table_serializer.py
- app/backend/utils/json_translation.py
- tests/test_docx_parser.py
- tests/test_translatable_document.py
- tests/test_table_serialization.py
- tests/test_table_context_translation.py
- tests/test_output_mode_processors.py
- tests/test_output_mode_orchestrator.py
- tests/test_translation_service.py
- tests/test_orchestrator_phase0.py
- tests/fixtures/
- tests/conftest.py

### ci-cd-gatekeeper
- specs/changes/docx-nested-table-collection/
- tests/test_table_context_translation.py

### implementation-planner
- specs/changes/docx-nested-table-collection/
- .cdd/code-map.yml
- app/backend/processors/docx_processor.py
- app/backend/parsers/docx_parser.py
- app/backend/utils/table_serializer.py
- app/backend/utils/json_translation.py
- app/backend/utils/translation_helpers.py
- app/backend/models/translatable_document.py
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md

### backend-engineer
- specs/changes/docx-nested-table-collection/
- .cdd/code-map.yml
- app/backend/processors/docx_processor.py
- app/backend/parsers/docx_parser.py
- app/backend/utils/table_serializer.py
- app/backend/utils/json_translation.py
- app/backend/utils/translation_helpers.py
- app/backend/models/translatable_document.py
- app/backend/config.py
- tests/test_docx_parser.py
- tests/test_translatable_document.py
- tests/test_table_serialization.py
- tests/test_table_context_translation.py
- tests/test_output_mode_processors.py
- tests/test_translation_service.py
- tests/fixtures/
- tests/conftest.py

### qa-reviewer
- specs/changes/docx-nested-table-collection/
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- tests/test_table_context_translation.py
- tests/test_docx_parser.py

## Context Expansion Requests

- request-id: CER-001
  requested_paths:
    - tests/test_table_serialization.py
    - tests/test_table_context_translation.py
    - tests/test_output_mode_processors.py
    - tests/test_translation_service.py
    - tests/test_translatable_document.py
    - tests/test_orchestrator_phase0.py
  reason: the classifier could not enumerate these from the truncated project-map tests/ listing and correctly refused to invent filenames, offering globs instead. Main Claude greped and resolved them. Its globs `tests/test_docx_table*.py` and `tests/test_passthrough*.py` match nothing and are dropped.
  status: approved
  approved-by: main-claude

- request-id: CER-002
  requested_paths:
    - .cdd/code-map.yml
  reason: to confirm the exact `<w:tbl>` walk, `table_id` and segment-emission seams against live source before wiring, per the "no-shell agents can assert nonexistent seams" rule.
  status: approved
  approved-by: main-claude

## Approved Expansions
- CER-001 and CER-002 granted up front and added to Allowed Paths.
- `docs/TEST_DOC/` is deliberately NOT in Allowed Paths. It is the user's untracked test corpus; no test may depend on it and no agent may read it. The measured 17.1% / 35.8% loss figures are recorded in change-request.md as evidence, which is where agents should get them.
- Every source and test path in this manifest was verified to exist on disk before it was written.
