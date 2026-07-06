# Change Classification

## Change Types
- primary: business-logic-change (table translation batching/context rules)
- secondary: feature-enhancement, refactor (shared prompt-builder seam)

## Risk Level
- medium

## Impact Radius
- cross-module (clients ↔ processors ↔ services; affects DOCX/XLSX/PPTX/PDF translation flows)

## Tier
- 2

## Architecture Review Required
- yes
- reason: Non-obvious design decisions at a shared seam: (a) HTML vs Markdown serialization format, (b) how a single translated table response remaps back onto individual cells when LLM returns malformed/mis-sized output, (c) how the new `(text, column_index)` dedup key interacts with existing dedup across three processors, (d) how PDF `TableCell` IR row/col/span fields feed serialization.

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

## Optional Artifacts (default: no — set yes only with explicit reason)
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | yes | Existing-behavior change across 4 formats; baseline of current cell-by-cell flow + dedup needed to scope regression. |
| proposal.md | no | Scope is pre-decided (improvement-plan 1.1/1.2/1.4). |
| spec.md | no | No new user-facing behavior decision beyond design.md. |
| design.md | yes | Architecture Review Required = yes (serialization, remap, dedup, shared-seam contract). |
| qa-report.md | no | Use agent-log/qa-reviewer.yml unless blocking. |
| regression-report.md | yes | High regression risk to existing non-table translation paths across all formats warrants durable prose evidence. |
| visual-review-report.md | no | No UI/visual output. |
| monkey-test-report.md | no | No interactive surface. |
| stress-soak-report.md | no | No high-load change; batching reduces, not increases, call volume. |

## Required Contracts
- API: none (no API surface change, no new endpoints)
- CSS/UI: none
- Env: none (TABLE_RECOGNITION_ENABLED already exists; no new env var)
- Data shape: contracts/data/data-shape-contract.md — table serialization shape, (text, column_index) dedup key, TableCell IR row/col/span consumption, translated-table → cell remap contract
- Business logic: contracts/business/business-rules.md — one-LLM-call-per-table rule, instruction-before-table prompt rule, header/unit co-occurrence rule, per-column differentiated translation
- CI/CD: none

## Required Tests
- unit: yes — dedup key (text, column_index) differentiation in xlsx/docx/pptx; HTML/Markdown serializer; header/unit context assembly
- contract: yes — business-rules (one-call-per-table, instruction placement) + data-shape (serialization shape, remap) conformance
- integration: yes — whole-table translation flow per format (DOCX/XLSX/PPTX) end-to-end; PDF TableCell IR path via translation_service
- E2E: no (covered by per-format integration tests)
- visual: no
- data-boundary: yes — table serialize → translate → remap-to-cells round-trip preserves row/col structure and cell count
- resilience: yes — malformed/mis-sized LLM table response handling (row/cell-count mismatch) must degrade safely
- fuzz/monkey: no
- stress: no
- soak: no

## Required Agents
- spec-architect (design.md — serialization format, remap strategy, dedup-key semantics, shared-builder contract)
- contract-reviewer (business-rules + data-shape contract updates)
- test-strategist (unit/contract/integration/data-boundary/resilience test design)
- ci-cd-gatekeeper (ci-gates.md)
- implementation-planner (execution packet from design + contracts + tests)
- backend-engineer (ollama_client prompt builder, docx/xlsx/pptx processors, translation_service PDF TableCell path)
- qa-reviewer (release readiness, regression sign-off)

## Inferred Acceptance Criteria
- AC-1: Each table is serialized into a single HTML or Markdown representation and sent as exactly one LLM batch call per table (not one call per cell) for DOCX, XLSX, and PPTX.
- AC-2: The translation instruction is placed before the serialized table in the prompt produced by the shared `ollama_client.py` builder.
- AC-3: The table-cell dedup key is `(text, column_index)`; identical cell text appearing in different columns can receive different translations in xlsx/docx/pptx processors.
- AC-4: Each cell's LLM context includes its adjacent column header and/or row header (and unit cell where present) so numbers, units, and headers co-occur in the prompt.
- AC-5: The PDF `TableCell` IR row/col/span fields (currently unused at `translation_service.py:614`) are consumed to drive serialization/context.
- AC-6: Existing non-table translation paths are unchanged (no regression in the full pytest suite).
- AC-7: No API surface change — no endpoints added, renamed, or re-shaped.
- AC-8: A malformed or mis-sized table response from the LLM is handled without corrupting cell mapping or non-table output.

## Tasks Not Applicable
- not-applicable: 2.1, 2.2, 2.3, 2.6, 3.3, 3.5, 4.2, 4.3, 5.1, 5.2, 6.4

## Clarifications or Assumptions
- Assumption: "one call per table" applies per-format at the processor seam; openai_compatible_client.py (cloud path) must mirror ollama_client.py serialization — design.md to confirm scope.
- Assumption: PDF TableCell IR path (via translation_service) is in-scope for context/serialization since the request cites translation_service.py:614. design.md should confirm whether PDF also gets the (text, column_index) dedup change.
- Open risk: remapping a single translated table response onto individual cells when LLM returns mismatched row/cell counts — primary regression hazard, drives the resilience test requirement.

## Context Manifest Draft

### Affected Surfaces
- Shared LLM prompt builder (table serialization) — clients/ollama_client.py
- Format processors (table cell extraction + dedup) — processors/docx_processor.py, processors/xlsx_processor.py, processors/pptx_processor.py
- Translation orchestration / PDF TableCell path — services/translation_service.py, services/translation_helpers.py
- Unified IR (TableCell row/col/span) — models/translatable_document.py

### Allowed Paths
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
- tests/test_translation_service.py
- tests/test_table_recognizer.py

### Agent Work Packets

#### spec-architect
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

#### contract-reviewer
- specs/changes/table-context-translation/
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md

#### test-strategist
- specs/changes/table-context-translation/
- tests/test_translation_service.py
- tests/test_table_recognizer.py

#### ci-cd-gatekeeper
- specs/changes/table-context-translation/
- .github/workflows/contract-driven-gates.yml
- contracts/ci/ci-gate-contract.md

#### implementation-planner
- specs/changes/table-context-translation/
- contracts/business/business-rules.md
- contracts/data/data-shape-contract.md

#### backend-engineer
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

#### qa-reviewer
- specs/changes/table-context-translation/
- tests/

### Context Expansion Requests
- request-id: CER-001
  requested_paths:
    - app/backend/processors/docx_processor.py
    - app/backend/processors/xlsx_processor.py
    - app/backend/processors/pptx_processor.py
    - app/backend/clients/ollama_client.py
    - app/backend/services/translation_service.py
  reason: spec-architect and backend-engineer need read access to these files to design the serialization/remap/dedup change; the indexes alone do not expose the seam internals.
  status: approved
