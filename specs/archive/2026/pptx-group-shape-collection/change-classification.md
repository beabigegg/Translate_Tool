# Change Classification

## Change Types
- primary: `business-logic-change`, `bug-fix`
- secondary: `refactor` (the same-loop `id(shape)` → document-order counter migration)

The originating symptom is a silent drop (bug-fix), but correcting it changes the collection contract on every PPTX job and requires a business-rules entry, forcing the `business-logic-change` contract path. The `id()`→counter swap is a bounded refactor of the table-cell grouping key.

## Lane
- bug-fix

Symptom-driven (grouped text/tables silently never translated; masked `id()` collision). The bug-fix evidence workflow fits: a synthetic fixture must reproduce the drop (RED) before the recursion lands (GREEN). A business-rules entry is also required, so the `business-logic-change` change-type carries the contract path; `bug-fix-engineer` remains the evidence/implementation owner.

## Bug Symptom Type
- data (grouped text/tables silently absent from output — a content-drop; also carries a coordinate-correctness facet via the `id()` collision)

## Diagnostic Only
- no

## Risk Level
- medium

## Impact Radius
- module-level (contained to `pptx_processor.py`; changes output on every PPTX job; no cross-module coupling — SmartArt path and other processors untouched)

## Tier
- 3

Bounded to a single module, mirrors an already-ratified and test-covered sibling (`docx-nested-table-collection` / BR-113 / ADR-0018), fully synthetic-fixture testable, no auth/migration/env/queue/cache risk.

## Architecture Review Required
- no
- The depth-bounded recursion, document-order counter, and never-drop semantics directly mirror the already-ratified ADR-0018 (nested-table-frame-routing) and BR-113 on the sibling DOCX surface. Reuse ADR-0018's pattern on the PPTX surface; record the PPTX behavior as a new business rule that references (does not re-derive) BR-113. No fresh ADR, no design.md.

## Required Agents
- `contract-reviewer` — business-rules.md new BR (referencing BR-113/BR-81; schema-version bump from live 0.32.0)
- `test-strategist` — bug-fix lane; AC → test mapping (data-boundary + resilience emphasis)
- `implementation-planner` — execution packet; must verify every named seam against live source before wiring
- `bug-fix-engineer` — reproduction + root-cause + failing-test evidence, then the recursion + counter migration in `pptx_processor.py`
- `qa-reviewer` — bug-fix lane release readiness + regression-report sign-off

(No `spec-architect` — architecture review not required.)

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

## Optional Artifacts (default: no — set yes only with explicit reason)
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | Captured by change-request live probes. |
| proposal.md | no | Scope fixed; mirrors a ratified sibling. |
| spec.md | no | No user-facing product decision beyond the contract entry. |
| design.md | no | No architecture review (ADR-0018 pattern reused); task 1.3 skipped. |
| qa-report.md | no | Routine pass/fail → agent-log/qa-reviewer.yml unless blocking. |
| regression-report.md | yes | Behavior changes on every PPTX job; durable evidence that flat-shape PPTX is unchanged AND grouped/nested/table coverage is proven, plus the no-collision-after-counter result. |
| visual-review-report.md | no | No UI surface. |
| monkey-test-report.md | no | Not applicable. |
| stress-soak-report.md | no | No load/soak surface. |

## Required Contracts
- API: no
- CSS/UI: no
- Env: no — the bounded-depth limit is a `config.py` constant mirroring DOCX `MAX_TABLE_NESTING_DEPTH` (e.g. `MAX_GROUP_NESTING_DEPTH`), NOT a new `.env` variable. Avoids both an env-contract change and the env-vocab tier-floor false positive; use `tier-floor-override` with rationale if the floor trips on "config"/"collision"/"counter".
- Data shape: no — grouped-table cells reuse the existing coordinate/IR shape; no new IR field.
- Business logic: yes — add a NEW BR (**BR-116**; highest live is BR-115) for PPTX group-shape recursion + document-order table-cell keying that REFERENCES BR-113 and BR-81 rather than duplicating them (python-pptx shapes are the same lxml-backed proxies as python-docx). Bump `schema-version` from the LIVE 0.32.0.
- CI/CD: no

## Inferred Acceptance Criteria
- AC-1: A synthetic slide with a plain textbox plus a single-level 2-textbox group yields all three text frames collected and translated (pre-fix: only the plain textbox).
- AC-2: Text inside a group-within-a-group (nested group) is collected and translated.
- AC-3: A table nested inside a group has every cell collected and written back to its correct coordinates (assert cell → coordinate selection, not just cell count).
- AC-4: After replacing `id(shape)` with a document-order counter, two distinct tables never share a grouping key, including under a forced-GC scenario (assert on the captured key at the grouping boundary, not on `id()` acceptance).
- AC-5: Existing flat-shape (non-grouped) PPTX translation output is behavior-unchanged versus pre-fix (regression).
- AC-6: Group recursion is depth-bounded (config constant mirroring `MAX_TABLE_NESTING_DEPTH`); at/over the bound shapes are handled gracefully and never silently dropped without a log.
- AC-7: The SmartArt path (`_extract_smartart_texts`) is untouched and remains out of scope.

## Tasks Not Applicable
Task 1.3 (design/architecture review — ADR-0018 pattern reused). UI/frontend/visual/E2E/stress/soak/monkey and API/CSS/env/data-shape contract tasks are not applicable (backend-only, no UI, no user `.pptx` files, no load surface).

## Context Manifest Draft

### Affected Surfaces
- PPTX processing (`app/backend/processors/pptx_processor.py` collection loop + restore path)
- Business behavior contract (`contracts/business/business-rules.md`)

### Allowed Paths
- specs/changes/pptx-group-shape-collection/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/processors/pptx_processor.py
- app/backend/config.py
- contracts/business/business-rules.md
- contracts/CHANGELOG.md
- docs/adr/0018-nested-table-frame-routing.md
- tests/test_docx_nested_tables.py
- tests/test_pptx_parser.py
- tests/test_pptx_group_shapes.py

### Required Contracts
- contracts/business/business-rules.md (new BR-116 referencing BR-113, BR-81)

### Required Tests
- tests/test_pptx_group_shapes.py (NEW — single-group, nested-group, grouped-table coord mapping, no-collision, flat-shape regression, bounded-depth)
- tests/test_pptx_parser.py (existing PPTX processor test file — confirmed the only one)
- tests/test_docx_nested_tables.py (read-only sibling pattern reference)

### Context Expansion Requests
- CER-001 (resolved by main Claude): the existing PPTX test module is `tests/test_pptx_parser.py` (confirmed; no `test_pptx_processor.py` exists).
