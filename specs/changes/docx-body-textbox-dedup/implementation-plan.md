---
change-id: docx-body-textbox-dedup
schema-version: 0.1.0
last-changed: 2026-07-11
---

# Implementation Plan: docx-body-textbox-dedup

## Objective

Route the DOCX body + table-cell paragraph extraction through the existing
`_p_text_no_txbx` extractor so a body/cell paragraph hosting a `<w:txbxContent>`
textbox has that textbox text collected and translated EXACTLY ONCE via the
dedicated `_txbx_iter_texts` path — never folded into the enclosing
paragraph/cell segment, never restored into the paragraph body. Textbox-free
DOCX output stays byte-for-byte unchanged. This is a bug-fix-lane change with an
explicit RED→GREEN boundary; the contract side (BR-115 amendment) is already
landed by contract-reviewer (`business-rules.md` schema-version 0.33.1).

All seams below were verified against LIVE source of
`app/backend/processors/docx_processor.py` at planning time; the three facts the
contract-reviewer corrected are confirmed accurate (see `## Known Risks`).

## Execution Scope

### In Scope
- One correctness-bearing extractor swap at the body collection call site.
- Three extractor-family-consistency swaps at restore-time re-read sites (inert
  to output; guarded by an AC-4 extractor-family test).
- Docstring correction on `_p_text_no_txbx`.
- Repurpose (flip) one existing pinning test that currently locks in the bug.
- New test module `tests/test_docx_body_textbox_dedup.py` (owned by
  bug-fix-engineer per test-plan.md, incl. the RED repro).

### Out of Scope
- `_p_text_with_breaks` itself (L38) — MUST stay byte-for-byte unchanged (AC-5).
- `_txbx_iter_texts`'s own internal `_p_text_flags` closure (L132) — the
  textbox's own multi-paragraph content extraction is unchanged (AC-6).
- Header/footer strip (already shipped under BR-115 original scope).
- Any IR/schema/API/env/CI change; the `Segment` write path at L696; the
  Windows COM shapes pass (`postprocess_docx_shapes_with_word`,
  `include_headers=True`).
- No opportunistic refactor of `_process_container_content`/`_process_table`
  threading beyond passing the existing `text_extractor` param.

## Required Changes

| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | docx_processor collection | Thread `text_extractor=_p_text_no_txbx` into the body walk (the sole correctness-bearing edit) | bug-fix-engineer |
| IP-2 | docx_processor restore hygiene | Swap the SDT-branch restore re-read to `_p_text_no_txbx` | bug-fix-engineer |
| IP-3 | docx_processor restore hygiene | Swap the table-cell-branch restore re-read to `_p_text_no_txbx` | bug-fix-engineer |
| IP-4 | docx_processor restore hygiene | Make `_scan_our_tail_texts`'s internal re-read use `_p_text_no_txbx` | bug-fix-engineer |
| IP-5 | docx_processor docstring | Correct `_p_text_no_txbx` docstring (remove "Must NOT be used for the body walk") | bug-fix-engineer |
| IP-6 | test repurpose | Flip the pinning test assertion + docstring to the stripped behavior | bug-fix-engineer |
| IP-7 | new tests | Author `tests/test_docx_body_textbox_dedup.py` incl. RED repro (AC-1..AC-7) | bug-fix-engineer |
| IP-8 | bug evidence | Record RED (behavioral assertion failure) → GREEN run evidence + regression-report.md | bug-fix-engineer |

## Source Artifact Pointers

| source | relevant pointer | used for |
|---|---|---|
| change-classification.md | Inferred AC-1..AC-7; Bug Evidence Required; Lane=bug-fix | scope, RED/GREEN duty |
| test-plan.md | AC→Test mapping; RED reproduction (AC-7); Falsifiability; Test Execution Ladder | tests to write/run, RED boundary |
| ci-gates.md | Required Gates table; Local Pre-PR Command Sequence; Rollback Policy | verification commands, rollback |
| contracts/business/business-rules.md | BR-115 (amended, uniform-strip clause) | implementation constraint, single contract anchor |
| change-request.md | Verified facts (main Claude live probes) | seam pointers |

## File-Level Plan

| path or glob | action | notes |
|---|---|---|
| app/backend/processors/docx_processor.py | edit L427 | body call: `_process_container_content(doc._body, "Body", 1)` → add `text_extractor=_p_text_no_txbx`. The extractor threads down through `_process_table`/`_cell_direct_text`/`_add_paragraph` from this single site (sig at L388 defaults to `_p_text_with_breaks`), so it covers both body paras (AC-1) and table cells (AC-2). SOLE correctness-bearing edit — `tmap` key `(tgt, seg.text, seg.col)` is fixed here. |
| app/backend/processors/docx_processor.py | edit L550 | SDT-content restore branch: `existing_texts.append(_p_text_with_breaks(p_obj))` → `_p_text_no_txbx(p_obj)`. Inert to output (only reads pipeline-created paras); extractor-family hygiene. |
| app/backend/processors/docx_processor.py | edit L596 | table-cell restore branch: `existing_texts.append(_p_text_with_breaks(cell_paragraphs[idx]))` → `_p_text_no_txbx(cell_paragraphs[idx])`. Inert; hygiene. |
| app/backend/processors/docx_processor.py | edit L123 | inside `_scan_our_tail_texts` (called at L664): change `out.append(_p_text_with_breaks(q))` → `out.append(_p_text_no_txbx(q))`. See mechanism decision below. Inert; hygiene. |
| app/backend/processors/docx_processor.py | edit L52-57 | `_p_text_no_txbx` docstring: remove the "Used ONLY for header/footer" and "Must NOT be used for the body walk (AC-6)" claims; restate as the uniform native-DOCX collection extractor that excludes `<w:txbxContent>` (BR-115). Do NOT touch `_p_text_with_breaks`. |
| tests/test_docx_header_footer.py | edit L181-191 | `TestTxbxContentStrippedFromHeader::test_body_paragraph_textbox_fold_in_unchanged`: flip `assert body_seg.text == "BODY_PLAINTB_TEXT"` → `== "BODY_PLAIN"` and add `assert "TB_TEXT" not in body_seg.text`; rewrite the docstring (it currently claims the body path keeps fold-in — now the opposite). Consider renaming to reflect stripped behavior (optional; keep node-id churn minimal if renamed, update test-plan reference). |
| tests/test_docx_body_textbox_dedup.py | create | New module per test-plan.md AC→Test mapping. Reuse `_add_textbox_to_paragraph` from `tests/test_docx_header_footer.py:69` (do NOT duplicate). Contains the RED repro. |

### `_scan_our_tail_texts` mechanism decision (IP-4)
Change the internal call at L123 directly to `_p_text_no_txbx(q)`. Do NOT add a
param. Rationale: `_scan_our_tail_texts` has a single call site (L664), the swap
is inert to its output (it only ever scans this pipeline's own inserted
paragraphs, never a nested textbox), and `_p_text_no_txbx` resolves as a
module-global at call time — so an AC-4 restore-hygiene spy that patches
`docx_processor._p_text_no_txbx` still observes the call fired from inside
`_scan_our_tail_texts`. A param default would be dead surface. Keep it minimal.

## Contract Updates

- API: none.
- CSS/UI: none.
- Env: none (no env var / kill-switch; rollback = git revert).
- Data shape: none (no IR/schema field change; routes existing text through the
  existing extractor).
- Business logic: BR-115 amendment ALREADY LANDED by contract-reviewer
  (`contracts/business/business-rules.md`, schema-version 0.33.1, uniform-strip
  clause covering body + cell collection and the three restore reads). Do NOT
  re-edit the contract; implement to it. If any seam contradicts BR-115, stop
  and report `blocked` (none found at planning time).
- CI/CD: none (`.github/workflows/contract-driven-gates.yml` byte-for-byte
  unchanged; ci-gates.md tasks 2.6/4.4 skipped).

## Test Execution Plan

Bug-fix lane: bug-fix-engineer MUST first produce a genuinely RED behavioral
assertion failure (not a collection/import error) BEFORE the IP-1 fix, then the
same node passes GREEN after. RED boundary: with L427 still on the default
`_p_text_with_breaks`,
`tests/test_docx_body_textbox_dedup.py::TestBodyTextboxCollectedOnce::test_body_paragraph_excludes_textbox_text`
asserts the body `para` segment excludes the textbox text and FAILS (segment
equals the folded string). Apply IP-1 → GREEN. Preserve the failed run-dir as
the reproduction reference (per CLAUDE.md bug-fix evidence rules).

Required test phases (floor): collect, targeted, changed-area. Add contract
(affected) and full (final/CI). Full ladder + commands live in test-plan.md
"Test Execution Ladder" and ci-gates.md "Local Pre-PR Command Sequence".

| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 / AC-7 (RED→GREEN) | tests/test_docx_body_textbox_dedup.py::TestBodyTextboxCollectedOnce::test_body_paragraph_excludes_textbox_text | body `para` seg excludes textbox text; RED pre-IP-1, GREEN post |
| AC-2 | tests/test_docx_body_textbox_dedup.py::TestBodyTextboxCollectedOnce::test_cell_paragraph_excludes_textbox_text | cell seg excludes textbox text |
| AC-3 | tests/test_docx_body_textbox_dedup.py::TestRestoreIsolatesTextboxTranslation | textbox translation lands only in `<w:txbxContent>`; enclosing para/cell has none |
| AC-4 | tests/test_docx_body_textbox_dedup.py::TestExtractorFamilyConsistency | `_p_text_no_txbx` fires at SDT, cell (L596), and `_scan_our_tail_texts` (L664) reads; revert any one → RED |
| AC-5 | tests/test_docx_body_textbox_dedup.py::TestTextboxFreeBodyUnchanged | textbox-free collected segments unchanged |
| AC-5 (regression) | tests/test_golden_regression.py | byte-identical, no re-baseline |
| AC-6 | tests/test_docx_body_textbox_dedup.py::TestTextboxOwnContentUnaffected::test_txbx_iter_texts_extracts_full_multiparagraph_textbox_content | full multi-paragraph textbox content still extracted |
| bug-pin repurpose | tests/test_docx_header_footer.py::TestTxbxContentStrippedFromHeader::test_body_paragraph_textbox_fold_in_unchanged | flipped assertion passes GREEN post-fix |
| changed-area | tests/test_docx_body_textbox_dedup.py tests/test_docx_header_footer.py tests/test_docx_nested_tables.py | all green |

Run all pytest/`cdd-kit test run` phases conda-scoped (`conda run -n
translate-tool ...`) so torch/onnxruntime resolve to the CI-matching interpreter
(CLAUDE.md). Contract phase: `cdd-kit validate --contracts`.

## Rollback

git revert of the four extractor swaps (L427, L550, L596, L123) restores
byte-for-byte pre-change behavior. No flag, no migration, no wire-format break
(ci-gates.md Rollback Policy). The BR-115 amendment is a separate landed commit.

## Handoff Constraints

- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved.
- No `design.md` for this change (Architecture Review = no); do not create one.

## Known Risks

- **Fixture text mismatch (assertion-alignment)**: the shared helper
  `_add_textbox_to_paragraph` (`tests/test_docx_header_footer.py:69`) appends
  textbox text literally `"TB_TEXT"`, so a body paragraph "BODY_PLAIN" hosting
  it folds to `"BODY_PLAINTB_TEXT"` — NOT `"BODY_PLAINTEXTBOX_TEXT"` as the
  change-request/test-plan prose loosely writes. bug-fix-engineer MUST align
  new-test assertions and the flipped pinning test to the helper's ACTUAL
  output (`"TB_TEXT"` / `"BODY_PLAIN"`), or reuse a fixture that emits
  `"TEXTBOX_TEXT"` consistently. A mismatch yields a test that never matches.
- **Inert-swap tautology (AC-4)**: the three restore-site swaps do not change
  output, so a test that merely asserts they "accept" the extractor proves
  nothing. The AC-4 test MUST spy on the module-level `_p_text_no_txbx` and
  assert it is actually INVOKED at each of the three restore reads (SDT, cell,
  tail-scan) across a resume-idempotency round trip; falsify by reverting one
  read to `_p_text_with_breaks` (test-plan Falsifiability).
- **Seam verification (no-shell-agent hazard)**: all `file:line` seams above
  were confirmed against live source at planning time. Line numbers can drift as
  bug-fix-engineer edits; anchor on the symbol/string, not the raw line number,
  and re-grep before each edit.
- **Golden regression**: no golden fixture contains a body textbox (change-request
  verified), so AC-5 requires NO re-baseline; a byte diff = real regression,
  investigate, do not re-baseline.
- `.cdd/code-map.yml` was not re-read this session because every seam was
  verified directly against live `docx_processor.py` (the higher bar); if a
  broader search is later needed, run `cdd-kit code-map` first.
