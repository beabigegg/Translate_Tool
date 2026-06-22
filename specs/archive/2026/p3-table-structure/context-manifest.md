# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- Backend PDF/document table parsing path (`app/backend/parsers/`)
- Unified IR model (`app/backend/models/translatable_document.py`)
- Translation/batching seam (`app/backend/services/translation_service.py`, `app/backend/services/doc_chunker.py`, `app/backend/processors/orchestrator.py`, `app/backend/processors/pdf_processor.py`)
- Data-shape and business-rule contracts

## Allowed Paths
- specs/changes/p3-table-structure/
- specs/context/project-map.md
- specs/context/contracts-index.md
- docs/improvement-plan.md
- docs/adr/0003-layout-detector-runtime-and-failure-mode.md
- docs/adr/0002-ir-elementtype-serialized-values.md
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md
- app/backend/parsers/__init__.py
- app/backend/parsers/base.py
- app/backend/parsers/pdf_parser.py
- app/backend/parsers/layout_detector.py
- app/backend/parsers/table_recognizer.py
- app/backend/models/translatable_document.py
- app/backend/processors/orchestrator.py
- app/backend/processors/pdf_processor.py
- app/backend/services/translation_service.py
- app/backend/services/translation_strategy.py
- app/backend/services/doc_chunker.py
- app/backend/services/model_router.py
- app/backend/config.py
- app/backend/utils/resource_utils.py
- app/backend/utils/text_utils.py
- tests/test_pdf_parser.py
- tests/test_layout_detector.py
- tests/test_doc_chunker.py
- tests/test_table_border_protection.py
- tests/test_translatable_document.py
- tests/test_orchestrator_phase0.py
- tests/test_translation_strategy.py
- tests/conftest.py
- tests/fixtures/
- .github/workflows/contract-driven-gates.yml

## Required Contracts
- contracts/data/data-shape-contract.md (new table/cell IR + cell-batch IR-consumption contract)
- contracts/business/business-rules.md (numeric passthrough, cell-granularity, same-table batching rules)

## Required Tests
- tests/test_pdf_parser.py
- tests/test_layout_detector.py (reference pattern for optional-model failure mode)
- tests/test_doc_chunker.py (reference pattern for batch/boundary selection tests)
- tests/test_translatable_document.py
- tests/test_table_border_protection.py
- new: tests/test_table_recognizer.py (to be created)

## Agent Work Packets

### spec-architect
- specs/changes/p3-table-structure/
- specs/context/project-map.md
- specs/context/contracts-index.md
- docs/improvement-plan.md
- docs/adr/0003-layout-detector-runtime-and-failure-mode.md
- docs/adr/0002-ir-elementtype-serialized-values.md
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md
- app/backend/parsers/layout_detector.py
- app/backend/parsers/pdf_parser.py
- app/backend/parsers/base.py
- app/backend/models/translatable_document.py
- app/backend/processors/orchestrator.py
- app/backend/services/translation_service.py
- app/backend/services/doc_chunker.py
- app/backend/config.py

### contract-reviewer
- specs/changes/p3-table-structure/
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md

### test-strategist
- specs/changes/p3-table-structure/
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md
- tests/test_pdf_parser.py
- tests/test_layout_detector.py
- tests/test_doc_chunker.py
- tests/test_table_border_protection.py
- tests/test_translatable_document.py
- tests/test_orchestrator_phase0.py
- tests/test_translation_strategy.py
- tests/conftest.py
- tests/fixtures/

### ci-cd-gatekeeper
- specs/changes/p3-table-structure/
- contracts/
- .github/workflows/contract-driven-gates.yml

### implementation-planner
- specs/changes/p3-table-structure/
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md
- app/backend/parsers/pdf_parser.py
- app/backend/parsers/layout_detector.py
- app/backend/parsers/base.py
- app/backend/models/translatable_document.py
- app/backend/processors/orchestrator.py
- app/backend/processors/pdf_processor.py
- app/backend/services/translation_service.py
- app/backend/services/doc_chunker.py
- app/backend/services/model_router.py
- app/backend/config.py

### backend-engineer
- specs/changes/p3-table-structure/
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md
- app/backend/parsers/table_recognizer.py
- app/backend/parsers/__init__.py
- app/backend/parsers/base.py
- app/backend/parsers/pdf_parser.py
- app/backend/parsers/layout_detector.py
- app/backend/models/translatable_document.py
- app/backend/processors/orchestrator.py
- app/backend/processors/pdf_processor.py
- app/backend/services/translation_service.py
- app/backend/services/translation_strategy.py
- app/backend/services/doc_chunker.py
- app/backend/services/model_router.py
- app/backend/config.py
- app/backend/utils/resource_utils.py
- app/backend/utils/text_utils.py
- tests/

### qa-reviewer
- specs/changes/p3-table-structure/
- contracts/data/data-shape-contract.md
- contracts/business/business-rules.md
- tests/

## Context Expansion Requests

- request-id: CER-001
  requested_paths:
    - app/backend/parsers/pptx_parser.py
    - app/backend/parsers/docx_parser.py
  reason: DOCX/PPTX already carry native table structure; if design chooses to unify table IR across formats (not just PDF/ML), these parsers must be read. Pending until spec-architect decides PDF-only vs. cross-format scope.
  status: rejected
  resolution: spec-architect confirmed PDF-only scope in design.md §Rejected Alternatives; DOCX/PPTX table unification deferred to a future change

## Approved Expansions
-
