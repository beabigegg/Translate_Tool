# Change Classification

## Change Types
- primary: feature-enhancement (Office output-mode expansion across DOCX/XLSX/PPTX)
- secondary: business-logic-change (per-format `output_mode` semantics), api-only-change (new `bilingual` enum value), data-shape-change (XLSX cell output structure)

## Lane
- feature

## Risk Level
- medium

## Impact Radius
- cross-module (three format processors + orchestrator routing + API schema + 2 contracts)

## Tier
- 2

## Architecture Review Required
- yes
- reason: "bilingual dual-column DOCX" has no existing structure decision — choosing two-column table vs side-by-side paragraphs is a non-obvious, industry-benchmarked design call. The `output_mode` enum is becoming a shared contract value with different semantics per format (DOCX paragraph/column, XLSX adjacent/annotation/replace, PPTX SmartArt replace). That cross-format data-flow + contract-shape decision must be settled in `design.md` before implementation.

## Required Artifacts

| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | current hard-coded append / `src\n譯文`+wrap_text behavior is short enough to capture in design.md + implementation-plan |
| proposal.md | no | scope settled in improvement-plan §階段 2 |
| spec.md | no | no separate product investigation needed |
| design.md | yes | bilingual DOCX structure + cross-format `output_mode` semantics need an architecture decision |
| qa-report.md | no | promote to yes only on blocking/approved-with-risk findings |
| regression-report.md | no | promote to yes only if a regression is found and accepted with risk |
| visual-review-report.md | no | no CSS/web UI surface touched |
| monkey-test-report.md | no | not applicable |
| stress-soak-report.md | no | not applicable |

## Required Contracts
- API: `contracts/api/api-contract.md` — add `bilingual` to the `output_mode` enum; regenerate `contracts/api/openapi.yml` (+ `openapi.json`) via `cdd-kit openapi export`
- Env: none
- Data shape: `contracts/data/data-shape-contract.md` — document per-format `output_mode` output structure (DOCX dual-column, XLSX adjacent/annotation/replace-no-wrap, PPTX SmartArt replace)
- Business logic: none new
- CI/CD: none

## Required Tests
- unit: yes — branch logic in each processor for every `output_mode` value
- contract: yes — `output_mode` enum accepts `bilingual`; invalid values still rejected; API contract / openapi conformance
- integration: yes — orchestrator routes `output_mode` correctly into each processor end-to-end
- E2E: no
- visual: no
- data-boundary: yes — XLSX export shape (adjacent column does not overwrite source; annotation attaches comment without altering value; replace overwrites with no wrap_text / no row-height inflation); DOCX dual-column structure assertions
- resilience: no
- fuzz/monkey: no
- stress/soak: no

## Required Agents
- spec-architect — writes `design.md` (bilingual DOCX structure, cross-format `output_mode` semantics) before planner runs
- implementation-planner — turns design + contracts + tests into the execution packet
- backend-engineer — processor branches, `api/schemas.py` enum value, contract + openapi updates
- contract-reviewer — reviews API enum change + data-shape contract + openapi regen
- test-strategist — AC to test mapping, regression coverage of existing append/replace paths
- qa-reviewer — release readiness, regression sign-off

## Inferred Acceptance Criteria

- AC-1: `output_mode` enum in `app/backend/api/schemas.py` accepts a new value `bilingual`; previously valid values (`append`, `replace`) still validate and unknown values are still rejected; `contracts/api/api-contract.md` and the exported `openapi.yml`/`openapi.json` reflect the new enum.
- AC-2 (2.1): DOCX `output_mode=bilingual` emits original text and translation in separate columns/paragraphs — they are NOT concatenated into the same run; a structural assertion proves original and translation occupy distinct cells/paragraphs.
- AC-3 (2.2): XLSX `output_mode=adjacent` writes the translation into the next column while leaving the source cell value unchanged and applies no `wrap_text` row-height inflation to the source.
- AC-4 (2.2): XLSX `output_mode=annotation` attaches the translation as a cell comment/annotation and leaves the source cell value unchanged.
- AC-5 (2.2): XLSX `output_mode=replace` overwrites the source cell with the translation, with no `wrap_text` and no stacked `"src\n譯文"` content (row height no longer inflates).
- AC-6 (2.3): DOCX table cell, SDT, and text box honor `output_mode=replace` — the translation replaces the source instead of being appended.
- AC-7 (2.3): PPTX SmartArt honors `output_mode=replace` — the translation replaces the source instead of being appended.
- AC-8 (regression): Existing default `append` and existing `replace` behavior in already-working paths (DOCX body, PPTX shapes) is unchanged; current output_mode tests continue to pass.

## Tasks Not Applicable
- 2.2 (CSS/UI contract): no frontend change
- 4.2 (Frontend implementation): no frontend change
- 5.1 (UI/UX review): no UI surface
- 5.2 (Visual review): no CSS/web UI
- 3.3 (E2E/resilience tests): not applicable
- 3.5 (Stress/soak tests): not applicable

## Context Manifest Draft

### Affected Surfaces
- Office output processors: DOCX, XLSX, PPTX
- Orchestrator output_mode routing
- API request schema (`output_mode` enum)
- API contract + OpenAPI export
- Data-shape contract (per-format output structure)

### Allowed Paths
- specs/changes/office-output-mode/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/processors/docx_processor.py
- app/backend/processors/xlsx_processor.py
- app/backend/processors/pptx_processor.py
- app/backend/processors/orchestrator.py
- app/backend/api/schemas.py
- contracts/api/api-contract.md
- contracts/api/openapi.yml
- contracts/data/data-shape-contract.md
- tests/test_output_mode_processors.py
- tests/test_output_mode_orchestrator.py
- tests/test_output_mode_api.py
- docs/improvement-plan.md

### Agent Work Packets

#### spec-architect
Reads: specs/changes/office-output-mode/, docs/improvement-plan.md, app/backend/processors/{docx,xlsx,pptx}_processor.py, app/backend/api/schemas.py, contracts/api/api-contract.md, contracts/data/data-shape-contract.md

#### implementation-planner
Reads: specs/changes/office-output-mode/, app/backend/processors/, app/backend/api/schemas.py, contracts/api/api-contract.md, contracts/data/data-shape-contract.md

#### backend-engineer
Reads + writes: specs/changes/office-output-mode/, app/backend/processors/{docx,xlsx,pptx,orchestrator}.py, app/backend/api/schemas.py, contracts/api/*, contracts/data/data-shape-contract.md, tests/

### Context Expansion Requests
- CER-001: app/backend/processors/libreoffice_helpers.py — pending; approve only if planner confirms helpers are on the XLSX write path
