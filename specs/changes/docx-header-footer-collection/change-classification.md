# Change Classification

## Change Types
- primary: `feature-enhancement` (native DOCX header/footer collection + restore path)
- secondary: `business-logic-change` (new BR for the native path + COM/native mutual-exclusion invariant), `bug-fix` (originating symptom: header/footer silently dropped on Linux)

The originating symptom is a silent drop (bug-fix flavored), but the fix introduces a new collection code path plus a COM-vs-native mutual-exclusion invariant that must be pinned in `business-rules.md`. Per the "a bug-fix that requires a contract change is no longer just a bug-fix" rule, and mirroring `docx-nested-table-collection` (BR-113/BR-114), this is a feature.

## Lane
- feature

## Atomic-split assessment
No split. One primary change-type surface (DOCX processing behavior), one backend module boundary (`docx_processor.py` + its `com_helpers` collaborator), one contract (`business-rules.md`). None of the four triggers fire.

## Risk Level
- medium

## Impact Radius
- cross-module (primary edit in `docx_processor.py`; must coordinate the mutual-exclusion contract with `com_helpers.py`; alters observable output on every DOCX translation job)

## Tier
- 2

## Architecture Review Required
- yes
- reason: Two genuine design decisions. (1) COM-vs-native content-domain boundary — resolved by spec-architect/ADR-0019: the COM pass translates only header-anchored SHAPES, never header text/tables, so the two paths are disjoint and exactly-once holds by construction; the COM call site stays unchanged. (2) Linked/shared-part dedup — a section exposes 6 header/footer slots each with `is_linked_to_previous`, and shared parts must be collected once; this must reconcile with the existing BR-81 element-identity dedup seam.

## Required Agents
- `spec-architect` (writes `design.md`: COM/native ownership + linked-part dedup)
- `contract-reviewer` (`business-rules.md` new BR + mutual-exclusion invariant)
- `test-strategist` (unit/integration/regression + mutual-exclusion and dedup coverage)
- `implementation-planner` (execution packet; must verify every named seam against live source)
- `backend-engineer` (native collection/restore in `docx_processor.py`)
- `qa-reviewer` (regression on every DOCX job; real-document success criterion)

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

## Optional Artifacts (default: no — set yes only with explicit reason)
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | Captured in change-request.md with live-probe facts. |
| proposal.md | no | Behavior decision fits in design.md. |
| spec.md | no | No new user-facing surface. |
| design.md | yes | Architecture Review = yes; COM/native mutual exclusion and linked-part dedup precede planning. |
| qa-report.md | no | Routine pass/fail lives in agent-log/qa-reviewer.yml unless blocking. |
| regression-report.md | yes | Changes observable output on every DOCX job; durable evidence that body/table translation is unchanged (AC-6) and Windows does not double-translate (AC-3). |
| visual-review-report.md | no | No UI surface. |
| monkey-test-report.md | no | No interactive surface. |
| stress-soak-report.md | no | No high-load path. |

## Required Contracts
- API: none
- CSS/UI: none
- Env: none — `is_win32com_available()`, "COM", "config", "capability" are runtime-capability terms, NOT env vars or secrets. No `.env`/`env-contract.md` change. If the gate tier-floor trips on this vocabulary, use `tier-floor-override` with written rationale.
- Data shape: none — reuses the existing `_process_container_content` walker output and IR; no new IR field. (Deliberately flagged and rejected.)
- Business logic: yes — new BR (next after BR-114) for native header/footer collection over all 6 slots, the linked/shared-part collect-once rule, and the COM-vs-native mutual-exclusion invariant. `business-rules.md` is LIVE at 0.31.0 — bump from the live value.
- CI/CD: none

## Inferred Acceptance Criteria
- AC-1: On Linux (`is_win32com_available()` == False), running `translate_docx` on `EN-P-QC1102-D7` and `W-RM0901-G6` leaves 0 header/footer paragraphs or header-table cells in the source language.
- AC-2: Header content is collected through the BR-113/BR-114 `_process_container_content` walker, so header tables (15-cell) AND any nested tables within a header/footer are collected and translated, not just top-level paragraphs.
- AC-3: The native path and the COM shape pass own DISJOINT content domains — native translates header/footer paragraphs and tables; COM translates only header/footer-anchored SHAPES (`sec.Headers(...).Shapes` → `TextFrame`, com_helpers.py L126-133). Header text/tables are therefore translated exactly once BY CONSTRUCTION, on both OSes, with no switch. The COM call site and `include_headers=True` MUST remain unchanged (setting `include_headers=False` would silently regress Windows header-shape translation). Verified against live source by main Claude and spec-architect (ADR-0019).
- AC-4: A header/footer part shared across sections via `is_linked_to_previous` is collected and written back exactly once, never per-referencing-section (consistent with BR-81 element-identity dedup).
- AC-5: All six per-section slots (default / first-page / even-page × header / footer) are traversed during collection.
- AC-6: Existing body and body-table translation output is unchanged by this change (regression: golden/real-document body output segment-stable).
- AC-7: Header/footer write-back through retained python-docx references persists across `doc.save()` in the produced output file.

## Tasks Not Applicable
Frontend/UI, API-contract, env-contract/`.env.example`, CSS/design-token, visual-review, and E2E/stress/soak/monkey tasks are not applicable (backend-only, no UI/API/env surface, no high-load path). Task 1.3 (design review) IS applicable and must NOT be skipped.

## Context Manifest Draft

### Affected Surfaces
- DOCX header/footer collection + restore (`app/backend/processors/docx_processor.py`)
- COM postprocess coordination (`app/backend/processors/com_helpers.py`)
- Business rule for native path + COM mutual exclusion (`contracts/business/business-rules.md`)

### Allowed Paths
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

### Required Contracts
- contracts/business/business-rules.md

### Required Tests
- tests/test_docx_nested_tables.py (existing BR-113/BR-114 walker coverage this change extends)
- tests/test_docx_parser.py (existing DOCX unit coverage)
- tests/test_golden_regression.py (real-document body/table regression)
- tests/test_docx_header_footer.py (NEW: header/footer collection, dedup, COM mutual-exclusion)

### Context Expansion Requests
- CER-001 (approved by main Claude): read `docx_processor.py`, `com_helpers.py`, `orchestrator.py` — the exact `_collect_docx_segments` / `_process_container_content` / `translate_docx` seams and the `postprocess_docx_shapes_with_word` call site must be read to author design.md and the plan.
