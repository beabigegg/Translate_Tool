# Change Classification

## Change Types
- primary: feature-enhancement (completion of stubbed seam)
- secondary: none

## Lane
- feature

## Risk Level
- low

## Impact Radius
- module-level

## Tier
- 3

## Architecture Review Required
- no

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

## Optional Artifacts (default: no — set yes only with explicit reason)
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | Stub behavior fully described in change-request; no separate investigation needed |
| proposal.md | no | No product/behavior decision open (TATR format documented, scope clear) |
| spec.md | no | No user-facing behavior decision beyond classification/plan |
| design.md | no | Algorithm fully specified in constraints; no architecture review |
| qa-report.md | no | Routine pass/fail belongs in agent-log/qa-reviewer.yml |
| regression-report.md | no | Feature gated off by default (TABLE_RECOGNITION_ENABLED=false); no existing behavior changes |
| visual-review-report.md | no | No UI surface touched |
| monkey-test-report.md | no | No interactive surface |
| stress-soak-report.md | no | No high-load/long-running/auto-refresh path |

## Required Contracts
- API: none
- CSS/UI: none
- Env: none
- Data shape: review-only — confirm `TableStructure`/`TableCell` output conforms to `contracts/data/data-shape-contract.md` (§TableCell, §TableStructure); no schema change expected
- Business logic: none (TABLE_RECOGNITION_ENABLED stays false; behavior is opt-in)
- CI/CD: none

## Required Tests
- unit: yes — TestParseOutputs in tests/test_table_recognizer.py; SELECTION tests calling `_parse_outputs` directly
- contract: none
- integration: none
- E2E: none
- visual: none
- data-boundary: yes — degenerate model outputs (zero rows/cols, empty detections, malformed CXCYWH) return safe TableStructure; fold into unit class
- resilience: none
- fuzz/monkey: none
- stress: none
- soak: none

## Required Agents
- contract-reviewer — read-only confirmation that IR emitted by `_parse_outputs` does not drift from data-shape contract
- test-strategist — designs SELECTION tests and degenerate-input cases in test-plan.md
- ci-cd-gatekeeper — writes ci-gates.md
- implementation-planner — turns request constraints into execution packet
- backend-engineer — implements `_parse_outputs` in table_recognizer.py
- qa-reviewer — release-readiness verdict

## Inferred Acceptance Criteria
- AC-1: Given TATR output with N "table row" bboxes, `_parse_outputs` returns a TableStructure whose cells are assigned row indices 0..N-1 in ascending y-coordinate order.
- AC-2: Given M "table column" bboxes, cells are assigned col indices 0..M-1 in ascending x-coordinate order.
- AC-3: Each emitted TableCell is assigned the (row_index, col_index) of the row/column intersection it overlaps (IoU/overlap), not a fixed position.
- AC-4: Every emitted TableCell has content="" (text extraction is not performed here).
- AC-5: TATR boxes are interpreted as normalized CXCYWH (converted to absolute pixel coords before sorting/overlap detection).
- AC-6: Degenerate model output (zero rows, zero columns, or no detections) returns a safe, well-formed TableStructure instead of raising.
- AC-7: TABLE_RECOGNITION_ENABLED default remains false; no other TableRecognizer behavior is altered.
- AC-8: New unit tests are SELECTION tests asserting specific row/col assignments and call `_parse_outputs` directly (not through `recognize()` or `_run_recognition()`).

## Tasks Not Applicable
- not-applicable: 1.3, 2.1, 2.2, 2.3, 2.5, 2.6, 3.2, 3.3, 3.5, 4.2, 4.3, 5.1, 5.2, 6.3, 6.4

## Clarifications or Assumptions
- Assumption: `TableStructure`/`TableCell` IR fields are already finalized in `contracts/data/data-shape-contract.md`; this change populates existing IR, does not redefine it.
- Assumption: TATR pred_boxes format is normalized CXCYWH (center_x, center_y, width, height), normalized 0-1 relative to image size. Must convert to pixel absolute before overlap comparison.
- Assumption: content assignment (text from pdf_parser) stays out of scope.

## Context Manifest Draft

### Affected Surfaces
- Table structure recognition (parsers module)

### Allowed Paths
- specs/changes/tatr-parse-outputs/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/parsers/table_recognizer.py
- app/backend/models/translatable_document.py
- app/backend/config.py
- tests/test_table_recognizer.py
- contracts/data/data-shape-contract.md

### Required Contracts
- contracts/data/data-shape-contract.md (review-only; no edit expected)

### Required Tests
- tests/test_table_recognizer.py

### Agent Work Packets

#### implementation-planner
- allowed:
  - specs/changes/tatr-parse-outputs/
  - specs/context/project-map.md
  - specs/context/contracts-index.md
  - app/backend/parsers/table_recognizer.py
  - app/backend/models/translatable_document.py
  - app/backend/config.py

#### backend-engineer
- allowed:
  - specs/changes/tatr-parse-outputs/
  - app/backend/parsers/table_recognizer.py
  - app/backend/models/translatable_document.py
  - app/backend/config.py

#### test-strategist
- allowed:
  - specs/changes/tatr-parse-outputs/
  - tests/test_table_recognizer.py
  - app/backend/parsers/table_recognizer.py
  - app/backend/models/translatable_document.py

#### contract-reviewer
- allowed:
  - specs/changes/tatr-parse-outputs/
  - contracts/data/data-shape-contract.md
  - app/backend/models/translatable_document.py

#### qa-reviewer
- allowed:
  - specs/changes/tatr-parse-outputs/
  - tests/test_table_recognizer.py
  - app/backend/parsers/table_recognizer.py

### Context Expansion Requests
- none
