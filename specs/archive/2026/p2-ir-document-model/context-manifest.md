# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- Document IR data model (`app/backend/models/translatable_document.py`)
- Parsers (`pdf_parser`, `docx_parser`, `pptx_parser`) — IR producers, reading-order source
- Renderers (`base`, `coordinate_renderer`, `pdf_generator`, `text_region_renderer`, `inline_renderer`) — IR consumers
- Processors / orchestrator — pipeline wiring
- Data-shape contract + CI gate contract
- Golden-sample regression fixtures + dual-run comparison test infrastructure

## Allowed Paths
- specs/changes/p2-ir-document-model/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/models/translatable_document.py
- app/backend/models/__init__.py
- app/backend/parsers/base.py
- app/backend/parsers/pdf_parser.py
- app/backend/parsers/docx_parser.py
- app/backend/parsers/pptx_parser.py
- app/backend/renderers/base.py
- app/backend/renderers/coordinate_renderer.py
- app/backend/renderers/pdf_generator.py
- app/backend/renderers/text_region_renderer.py
- app/backend/renderers/inline_renderer.py
- app/backend/processors/orchestrator.py
- app/backend/processors/pdf_processor.py
- app/backend/processors/docx_processor.py
- app/backend/processors/pptx_processor.py
- app/backend/utils/bbox_utils.py
- app/backend/utils/font_utils.py
- contracts/data/data-shape-contract.md
- contracts/ci/ci-gate-contract.md
- tests/test_translatable_document.py
- tests/test_pdf_parser.py
- tests/test_docx_parser.py
- tests/test_pptx_parser.py
- tests/test_coordinate_renderer.py
- tests/test_pdf_generator.py
- tests/test_text_region_renderer.py
- tests/test_inline_renderer.py
- tests/fixtures/
- docs/improvement-plan.md
- .github/workflows/contract-driven-gates.yml
- ci/gate-policy.md

## Required Contracts
- contracts/data/data-shape-contract.md
- contracts/ci/ci-gate-contract.md

## Required Tests
- tests/test_translatable_document.py
- tests/test_pdf_parser.py
- tests/test_docx_parser.py
- tests/test_pptx_parser.py
- tests/test_coordinate_renderer.py
- tests/test_pdf_generator.py
- tests/test_text_region_renderer.py
- tests/test_inline_renderer.py
- tests/fixtures/golden/ (new — golden-sample set + dual-run comparison harness)

## Agent Work Packets

### change-classifier
- specs/changes/p2-ir-document-model/
- specs/context/project-map.md
- specs/context/contracts-index.md

### spec-architect
- specs/changes/p2-ir-document-model/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/models/translatable_document.py
- app/backend/renderers/base.py
- app/backend/parsers/pdf_parser.py
- app/backend/parsers/base.py
- contracts/data/data-shape-contract.md
- docs/improvement-plan.md

### contract-reviewer
- specs/changes/p2-ir-document-model/
- contracts/data/data-shape-contract.md
- contracts/ci/ci-gate-contract.md

### test-strategist
- specs/changes/p2-ir-document-model/
- tests/test_translatable_document.py
- tests/test_pdf_parser.py
- tests/test_docx_parser.py
- tests/test_pptx_parser.py
- tests/test_coordinate_renderer.py
- tests/test_pdf_generator.py
- tests/test_text_region_renderer.py
- tests/test_inline_renderer.py
- tests/fixtures/
- app/backend/models/translatable_document.py

### ci-cd-gatekeeper
- specs/changes/p2-ir-document-model/
- contracts/ci/ci-gate-contract.md
- .github/workflows/contract-driven-gates.yml
- ci/gate-policy.md
- tests/fixtures/

### implementation-planner
- specs/changes/p2-ir-document-model/
- contracts/data/data-shape-contract.md
- contracts/ci/ci-gate-contract.md
- app/backend/models/translatable_document.py
- app/backend/parsers/base.py
- app/backend/parsers/pdf_parser.py
- app/backend/parsers/docx_parser.py
- app/backend/parsers/pptx_parser.py
- app/backend/renderers/base.py
- app/backend/renderers/coordinate_renderer.py
- app/backend/renderers/pdf_generator.py
- app/backend/renderers/text_region_renderer.py
- app/backend/renderers/inline_renderer.py
- app/backend/processors/orchestrator.py
- app/backend/processors/pdf_processor.py
- app/backend/processors/docx_processor.py
- app/backend/processors/pptx_processor.py

### backend-engineer
- specs/changes/p2-ir-document-model/
- app/backend/models/translatable_document.py
- app/backend/models/__init__.py
- app/backend/parsers/base.py
- app/backend/parsers/pdf_parser.py
- app/backend/parsers/docx_parser.py
- app/backend/parsers/pptx_parser.py
- app/backend/renderers/base.py
- app/backend/renderers/coordinate_renderer.py
- app/backend/renderers/pdf_generator.py
- app/backend/renderers/text_region_renderer.py
- app/backend/renderers/inline_renderer.py
- app/backend/processors/orchestrator.py
- app/backend/processors/pdf_processor.py
- app/backend/processors/docx_processor.py
- app/backend/processors/pptx_processor.py
- app/backend/utils/bbox_utils.py
- app/backend/utils/font_utils.py

### qa-reviewer
- specs/changes/p2-ir-document-model/
- contracts/data/data-shape-contract.md
- tests/fixtures/

## Context Expansion Requests

- request-id: CER-001
  requested_paths:
    - tests/fixtures/golden/
  reason: Golden-sample fixture directory does not yet exist; it must be created and read by test-strategist, ci-cd-gatekeeper, and qa-reviewer.
  status: approved

- request-id: CER-002
  requested_paths:
    - .github/workflows/contract-driven-gates.yml
    - ci/gate-policy.md
  reason: CI workflow and gate policy must be edited to register the offline golden-sample regression gate (no network/GPU). Required by ci-cd-gatekeeper.
  status: approved

## Approved Expansions
- tests/fixtures/golden/ — golden-sample set creation and read scope (CER-001)
- .github/workflows/contract-driven-gates.yml — CI gate wiring (CER-002)
- ci/gate-policy.md — CI gate policy reference (CER-002)
