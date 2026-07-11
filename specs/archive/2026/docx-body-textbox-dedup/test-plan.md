---
change-id: docx-body-textbox-dedup
schema-version: 0.1.0
last-changed: 2026-07-11
risk: medium
tier: 2
---

# Test Plan: docx-body-textbox-dedup

Bug-fix lane. All fixtures are built in-test with `python-docx` (a paragraph or
table cell hosting a synthetic `<w:pict>/v:txbxContent` run), reusing the
`_add_textbox_to_paragraph` helper already defined in
`tests/test_docx_header_footer.py:69` rather than duplicating it. No
`docs/TEST_DOC/` fixtures are read by any test.

## RED reproduction (AC-7)

`tests/test_docx_body_textbox_dedup.py::TestBodyTextboxCollectedOnce::test_body_paragraph_excludes_textbox_text`
fails behaviorally before the fix: for a body paragraph "BODY_PLAIN " hosting
textbox "TEXTBOX_TEXT", the collected `para` `Segment.text` currently equals
`"BODY_PLAINTEXTBOX_TEXT"` (textbox text folded in) against a required
`"BODY_PLAIN"` with zero occurrences of `"TEXTBOX_TEXT"`. This is a genuine
assertion failure, not a collection/import error, produced by
`_process_container_content(doc._body, "Body", 1)` at docx_processor.py L427
threading the default `_p_text_with_breaks` instead of `_p_text_no_txbx`.

**Existing test that pins the bug and must be repurposed, not left as-is**:
`tests/test_docx_header_footer.py::TestTxbxContentStrippedFromHeader::test_body_paragraph_textbox_fold_in_unchanged`
currently asserts `body_seg.text == "BODY_PLAINTB_TEXT"` — written under the
pre-amendment BR-115 scope, it locks in the exact bug this change reverses. It
must be updated in this change to assert the corrected behavior, or the
amended BR-115 and this test permanently contradict each other.

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | unit (collection, body) | tests/test_docx_body_textbox_dedup.py::TestBodyTextboxCollectedOnce::test_body_paragraph_excludes_textbox_text | 0 |
| AC-2 | unit (collection, cell) | tests/test_docx_body_textbox_dedup.py::TestBodyTextboxCollectedOnce::test_cell_paragraph_excludes_textbox_text | 0 |
| AC-3 | integration (restore round-trip) | tests/test_docx_body_textbox_dedup.py::TestRestoreIsolatesTextboxTranslation | 1 |
| AC-4 | unit (extractor identity) + integration (extractor-family spy) | tests/test_docx_body_textbox_dedup.py::TestExtractorFamilyConsistency | 0 / 1 |
| AC-5 | unit (textbox-free baseline) + regression | tests/test_docx_body_textbox_dedup.py::TestTextboxFreeBodyUnchanged, tests/test_golden_regression.py | 0 / 1 |
| AC-6 | unit (`_txbx_iter_texts` unaffected) | tests/test_docx_body_textbox_dedup.py::TestTextboxOwnContentUnaffected::test_txbx_iter_texts_extracts_full_multiparagraph_textbox_content | 0 |
| AC-7 | unit (RED-then-green repro) | tests/test_docx_body_textbox_dedup.py::TestBodyTextboxCollectedOnce::test_body_paragraph_excludes_textbox_text | 0 |
| bug-pin repurpose | unit (update, not new) | tests/test_docx_header_footer.py::TestTxbxContentStrippedFromHeader::test_body_paragraph_textbox_fold_in_unchanged | 0 |

## Test Families Required

Mark all that apply: **unit**, **integration**. (contract / e2e /
data-boundary / resilience / monkey / stress / soak: not applicable — no
API/UI/env/load surface, per change-classification "Tasks Not Applicable".)

| family | tier | notes |
|---|---|---|
| unit — collection (AC-1/AC-2) | 0 | asserts on the collected `Segment` list — SELECTION (which unit holds the textbox text), not `len(segs)`: textbox text present in exactly the `txbx` segment, absent from `para`/`cell` |
| unit — extractor identity (AC-4 collection) | 0 | proves the body/cell collection call uses the stripping extractor by feeding a fixture through `_collect_docx_segments` and observing stripped output, never by reading a variable/line |
| integration — extractor-family spy (AC-4 restore hygiene) | 1 | spies on `_p_text_no_txbx` across a full resume-idempotency round trip (translate once, save, reopen, re-run collect+restore) and asserts it fires for the SDT-branch, cell-branch, and `_scan_our_tail_texts` restore reads — proves the shared helper is actually invoked at all three sites, not just accepted as a parameter |
| integration — restore round-trip (AC-3) | 1 | mocks the LLM client at the client-call boundary; full collect→translate→restore for a body-textbox and a cell-textbox fixture; asserts the textbox translation lands only in `<w:txbxContent>` runs and the enclosing paragraph/cell runs contain no textbox-derived text |
| unit — textbox-own-content unaffected (AC-6) | 0 | `_txbx_iter_texts` against a multi-paragraph textbox; asserted via its own public `(tx, text)` yield, not an internal helper name |
| unit/regression — textbox-free unchanged (AC-5) | 0 / 1 | textbox-free body+cell fixture: collected segments match the pre-existing `_p_text_with_breaks`-era shape; plus `tests/test_golden_regression.py` run unmodified, no re-baseline |

## Falsifiability (per family, the exact production change that turns it RED)

- AC-1/AC-2/AC-4(collection): revert docx_processor.py L427 to the bare `_process_container_content(doc._body, "Body", 1)` call (drop `text_extractor=_p_text_no_txbx`) → both body and cell tests RED (the extractor threads down through `_process_table`/`_cell_direct_text` from this single call site, so one revert covers both).
- AC-3: same L427 revert also turns the restore round-trip RED, since the `tmap` key is fixed from the (now unstripped) collection text.
- AC-4(restore hygiene): revert any one of the three restore-time reads (SDT branch, cell branch L596, `_scan_our_tail_texts` call at L664) back to `_p_text_with_breaks` → the spy-based family-consistency test goes RED even though functional output is unchanged (per contract-reviewer, these reads are inert to result but must not silently diverge from the collection-side extractor).
- AC-6: any change to `_txbx_iter_texts`'s private `_p_text_flags` closure that drops or truncates textbox lines → RED.
- AC-5: any change to `_p_text_with_breaks` itself, or to a textbox-free fixture's collected segments, or a golden-regression byte diff → RED.

## Existing-fake sweep

Grepped `tests/` for `_collect_docx_segments`, `_insert_docx_translations`,
`Segment("para"`, `Segment("txbx"`, `_p_text_with_breaks`, `_p_text_no_txbx`.
Hits: `tests/test_docx_header_footer.py` (the one test requiring repurposing,
noted above); `tests/test_docx_nested_tables.py`, `tests/test_table_context_translation.py`,
`tests/test_translation_service.py` (generic body/table collection calls, no
textbox fixtures — unaffected, and serve as part of the AC-5 regression net);
`tests/test_output_mode_processors.py::test_docx_textbox_replace_overwrites_source`
(builds a `Segment("txbx", ...)` directly and calls `_insert_docx_translations`
against the txbx write path only, bypassing collection entirely — confirmed
unaffected by reading the write path at L696, which this change does not
touch). No fake reproduces the collection extractor threading this change
modifies.

## Test Execution Ladder

| phase | required | command source | max failures | result artifact |
|---|---:|---|---:|---|
| collect | yes | `conda run -n translate-tool cdd-kit test select` | 1 | test-runs/<run-id>/summary.json |
| targeted | yes | `conda run -n translate-tool pytest tests/test_docx_body_textbox_dedup.py -v` | 1 | test-evidence.yml |
| changed-area | yes | `conda run -n translate-tool pytest tests/test_docx_body_textbox_dedup.py tests/test_docx_header_footer.py tests/test_docx_nested_tables.py -v` | 1 | test-evidence.yml |
| contract | if affected | `cdd-kit validate --contracts` | 1 | test-evidence.yml |
| full | final/CI | `conda run -n translate-tool cdd-kit test run --phase full` | 1 | test-evidence.yml |

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| tests/test_docx_header_footer.py::TestTxbxContentStrippedFromHeader::test_body_paragraph_textbox_fold_in_unchanged | update | BR-115 amendment reverses the body fold-in this test pinned as "unchanged"; must now assert the stripped body-paragraph behavior |
| tests/test_docx_nested_tables.py | none (run unmodified) | proves AC-5 table/body behavior outside textbox scope is unaffected |
| tests/test_golden_regression.py | none (run unmodified) | proves textbox-free byte-identical output; no re-baseline |

## Stop Rules

- Do not run broad pytest before targeted and changed-area phases pass.
- Do not investigate more than the first failure per phase.
- Do not classify any failure as known, pre-existing, waived, or allowed.
- If full suite fails, record the first failure and block the gate.

## Out of Scope

- Header/footer `<w:txbxContent>` strip — already shipped under BR-115's
  original scope (`tests/test_docx_header_footer.py::TestTxbxContentStrippedFromHeader::test_header_paragraph_excludes_textbox_text`).
- The textbox's own content extraction mechanism beyond the AC-6 non-regression check.
- SmartArt (PPTX, unrelated path, BR-116 territory).
- Windows COM shapes pass (`postprocess_docx_shapes_with_word`) — unchanged, header-anchored shapes only.

## Notes

BR-115 (amended) is the sole contract anchor for all seven ACs. Tier 0 covers
every collection/extraction/regression unit (fast, in-memory python-docx
only). Tier 1 covers the restore round-trip, the extractor-family spy, and the
existing golden/nested-table regression suites. No contract/e2e/data-boundary/
resilience/monkey/stress/soak family applies (no API/UI/env/load surface).
