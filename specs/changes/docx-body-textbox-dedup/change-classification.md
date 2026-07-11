# Change Classification

## Change Types
- primary: bug-fix (data — hosted-textbox text translated twice and misplaced into paragraph body on restore)
- secondary: business-logic-change (amends BR-115's txbxContent-strip scope, which currently excludes the body/cell path)

## Lane
- bug-fix

## Bug Symptom Type
- data

## Diagnostic Only
- no

## Bug Evidence Required
- symptom: a body paragraph (or table cell) hosting a `<w:txbxContent>` produces both a `para`/`cell` segment containing the textbox text folded in AND a separate `txbx` segment with the same text → translated twice, restored into the paragraph body.
- expected: hosted-textbox text collected/translated exactly once via `_txbx_iter_texts`; the enclosing paragraph/cell segment excludes `<w:txbxContent>`; restore places the textbox translation only in the textbox.
- actual: `_p_text_with_breaks`'s `.//` xpath reaches into `<w:txbxContent>` and folds the textbox text into the para/cell string, double-counting against `_txbx_iter_texts`.
- reproduction status: live repro recorded ("BODY_PLAIN TEXTBOX_TEXT" para + "TEXTBOX_TEXT" txbx; `_p_text_no_txbx` yields "BODY_PLAIN"). bug-fix-engineer must convert to a genuinely RED behavioral assertion failure before the fix.
- root cause pointer: `docx_processor.py` body walk `_process_container_content(doc._body, "Body", 1)` at L427 threads the default `_p_text_with_breaks`; header walk at L458 already threads `_p_text_no_txbx`. Restore-matching sites L550 (paragraph), L596 (cell) also use `_p_text_with_breaks`.
- regression evidence: existing DOCX golden regression byte-identical for textbox-free docs (no golden fixture has a body textbox → no re-baseline); new fixture proves single-collection.

## Atomic-split assessment
No split. Single change-type on one surface plus one contract amendment.

## Risk Level
- medium

## Impact Radius
- module-level (DOCX processor extraction + restore; behavior-neutral for textbox-free docs, but the body path runs on every DOCX job)

## Tier
- 2

## Architecture Review Required
- no
- reason: reuses the existing `_p_text_no_txbx` helper and the extractor-threading pattern established by BR-115; no new boundary, data-flow, or migration.

## Required Agents
- contract-reviewer — BR-115 scope amendment (or new sibling BR); confirm no api/env/data-shape drift
- test-strategist — bug-fix lane; AC → test mapping; ensure repro is behavioral and extractor-consistency covered
- implementation-planner — execution packet; verify every named seam against live source
- bug-fix-engineer — bug-fix lane owner; RED repro + root cause + regression evidence, then the fix
- qa-reviewer — bug-fix lane; release readiness; textbox-free regression clean

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

## Optional Artifacts (default: no — set yes only with explicit reason)
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | Captured in change-request + Bug Evidence. |
| proposal.md | no | Fix is deterministic. |
| spec.md | no | No new behavior surface. |
| design.md | no | No architecture review; reuses BR-115 pattern. |
| qa-report.md | no | Routine pass → agent-log/qa-reviewer.yml. |
| regression-report.md | yes | Body-path extraction/restore change on a path every DOCX job runs; durable evidence that textbox-free output is unchanged AND the extractor-consistency invariant holds. |
| visual-review-report.md | no | No UI surface. |
| monkey-test-report.md | no | Not applicable. |
| stress-soak-report.md | no | No load behavior change. |

## Required Contracts
- API: none
- CSS/UI: none
- Env: none — no env var/secret/runtime-config change. No tier-floor false-positive vocabulary; use `tier-floor-override` with rationale if a spurious floor fires.
- Data shape: none — no IR/schema field change; routes existing text through the correct existing extractor.
- Business logic: yes — `contracts/business/business-rules.md`. BR-115 currently scopes the `<w:txbxContent>`-strip to the header/footer path and explicitly leaves the body double-count OUT. contract-reviewer decides: AMEND BR-115's scope to extend the strip to the body + table-cell paragraph extraction (collection AND both restore-matching sites), or add a small sibling BR referencing BR-115. Preference: amend BR-115 (same mechanism; closes BR-115's documented follow-up). Bump `schema-version` from the LIVE 0.33.0.
- CI/CD: none

## Inferred Acceptance Criteria
- AC-1: For a body paragraph hosting a textbox ("BODY_PLAIN " + textbox "TEXTBOX_TEXT"), the collected units contain the textbox text in exactly one unit (the `txbx` segment); the `para` segment equals "BODY_PLAIN" with zero occurrences of the textbox text.
- AC-2: For a table cell hosting a textbox, the same single-collection property holds: textbox text appears only in the `txbx` segment, never folded into the `cell` segment.
- AC-3: On restore, the textbox translation is written only into the textbox; the enclosing paragraph/cell body contains no textbox-derived text.
- AC-4: The COLLECTION call `_process_container_content(doc._body, "Body", 1)` uses `_p_text_no_txbx` — this is the SOLE correctness-bearing site, since the `tmap` key `(tgt, seg.text, seg.col)` is fixed from the collection extractor's output. The THREE restore-time resume-idempotency reads inside `_insert_docx_translations` (SDT-content branch, table-cell branch L596, and the plain-paragraph tail-scan `_scan_our_tail_texts` called at L664) also switch to `_p_text_no_txbx` for extractor-family consistency; those reads only see pipeline-inserted paragraphs (never a nested textbox), so the swap is inert to their result but a test asserts the whole family uses one extractor so a future divergence fails loudly.
- AC-5: For textbox-free DOCX documents, collected segments and restored output are byte-identical to pre-change (existing DOCX golden regression unchanged, no re-baseline).
- AC-6: `_txbx_iter_texts`'s own internal extraction (its private `_p_text_flags` closure — NOT `_p_text_with_breaks`; the L123 `_p_text_with_breaks` call is in the unrelated `_scan_our_tail_texts`) is unchanged — the textbox's own paragraphs are still fully extracted (the fix does not strip the textbox's real content). Assert via `_txbx_iter_texts`'s public output, not on an internal line.
- AC-7: The pre-fix repro is a genuinely FAILED behavioral (assertion) `cdd-kit test run`, and the same test passes green after the fix.

## Tasks Not Applicable
Task 1.3 (no design/architecture review). UI/frontend/visual/E2E/stress/soak/monkey and API/CSS/env/data-shape contract tasks are not applicable (backend-only, no UI/API/env surface, no load surface).

## Context Manifest Draft

### Affected Surfaces
- DOCX processor body + table-cell paragraph extraction and restore-matching (`app/backend/processors/docx_processor.py`)
- Business rules contract (BR-115 scope)

### Allowed Paths
- specs/changes/docx-body-textbox-dedup/
- specs/context/project-map.md
- specs/context/contracts-index.md
- app/backend/processors/docx_processor.py
- contracts/business/business-rules.md
- contracts/CHANGELOG.md
- tests/test_docx_header_footer.py
- tests/test_docx_parser.py
- tests/test_docx_nested_tables.py
- tests/test_golden_regression.py
- tests/test_docx_body_textbox_dedup.py

### Required Contracts
- contracts/business/business-rules.md

### Required Tests
- tests/test_docx_header_footer.py (sibling txbx/header extraction test — the pattern to mirror)
- tests/test_docx_parser.py
- tests/test_docx_nested_tables.py
- tests/test_golden_regression.py
- tests/test_docx_body_textbox_dedup.py (candidate new)

### Context Expansion Requests
- none at classification time. Line numbers L38/L123/L131/L427/L458/L550/L596 are pointers from main Claude's verified probe; implementation agents must grep-confirm every seam against live source before editing.
