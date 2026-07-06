# Context Manifest

This manifest defines the approved context boundaries for agents working on
this change. The forbidden-paths baseline lives in `.cdd/context-policy.json`
and is automatically applied by `cdd-kit gate` — do not duplicate it here.

## Affected Surfaces
- Shared LLM prompt builder (table serialization) — app/backend/clients/ollama_client.py
- Format processors (table cell extraction + dedup) — app/backend/processors/docx_processor.py, xlsx_processor.py, pptx_processor.py
- Translation orchestration / PDF TableCell path — app/backend/services/translation_service.py, translation_helpers.py
- Unified IR (TableCell row/col/span) — app/backend/models/translatable_document.py
- Business rules + data-shape contracts

## Allowed Paths
- specs/changes/table-context-translation/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/clients/ollama_client.py
- app/backend/clients/openai_compatible_client.py
- app/backend/processors/docx_processor.py
- app/backend/processors/xlsx_processor.py
- app/backend/processors/pptx_processor.py
- app/backend/processors/pdf_processor.py
- app/backend/processors/orchestrator.py
- app/backend/services/translation_service.py
- app/backend/services/translation_helpers.py
- app/backend/models/translatable_document.py
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- contracts/ci/ci-gate-contract.md
- .github/workflows/contract-driven-gates.yml
- app/backend/utils/
- tests/test_translation_service.py
- tests/test_table_recognizer.py

## Required Contracts
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md

## Required Tests
- tests/test_translation_service.py (existing, to verify non-regression)
- tests/test_table_context_translation.py (new — whole-table flow, dedup key, header/unit context, resilience)
- tests/test_table_serialization.py (new or co-located — data-boundary round-trip)

## Agent Work Packets

### change-classifier
- specs/changes/table-context-translation/
- specs/context/project-map.md
- specs/context/contracts-index.md

### spec-architect
- specs/changes/table-context-translation/
- specs/context/project-map.md
- specs/context/contracts-index.md
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- app/backend/clients/ollama_client.py
- app/backend/models/translatable_document.py
- app/backend/services/translation_service.py
- app/backend/processors/docx_processor.py
- app/backend/processors/xlsx_processor.py
- app/backend/processors/pptx_processor.py

### contract-reviewer
- specs/changes/table-context-translation/
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md

### test-strategist
- specs/changes/table-context-translation/
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md
- tests/test_translation_service.py
- tests/test_table_recognizer.py

### ci-cd-gatekeeper
- specs/changes/table-context-translation/
- .github/workflows/contract-driven-gates.yml
- contracts/ci/ci-gate-contract.md

### implementation-planner
- specs/changes/table-context-translation/
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md

### backend-engineer
- specs/changes/table-context-translation/
- app/backend/clients/ollama_client.py
- app/backend/clients/openai_compatible_client.py
- app/backend/processors/docx_processor.py
- app/backend/processors/xlsx_processor.py
- app/backend/processors/pptx_processor.py
- app/backend/processors/pdf_processor.py
- app/backend/services/translation_service.py
- app/backend/services/translation_helpers.py
- app/backend/models/translatable_document.py
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md

### qa-reviewer
- specs/changes/table-context-translation/
- tests/

## Context Expansion Requests
- request-id: CER-001
  requested_paths:
    - app/backend/processors/docx_processor.py
    - app/backend/processors/xlsx_processor.py
    - app/backend/processors/pptx_processor.py
    - app/backend/clients/ollama_client.py
    - app/backend/services/translation_service.py
  reason: spec-architect and backend-engineer need to read these files to design the serialization/remap/dedup change; context indexes alone do not expose the seam internals.
  status: approved

- request-id: CER-close-1
  requested_paths:
    - CLAUDE.md
  reason: cdd-close Step 3 lesson-promotion needs to check/edit the cdd-kit:learnings managed region for a candidate workflow lesson about verifying archival state
  status: approved
## Approved Expansions
- CER-001 approved — source files are the primary work surface for this change.
- CER-close-1 approved — main Claude self-approved per cdd-close skill Step 3 ("main Claude owns the final writes" to CLAUDE.md's learnings region).
