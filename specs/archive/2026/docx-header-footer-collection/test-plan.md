---
change-id: docx-header-footer-collection
schema-version: 0.1.0
last-changed: 2026-07-11
risk: medium
tier: 2
---

# Test Plan: docx-header-footer-collection

All fixtures are built in-test with `python-docx` (mirrors
`tests/test_docx_nested_tables.py`). No test reads `docs/TEST_DOC/`; AC-1's
real-document names (`EN-P-QC1102-D7`, `W-RM0901-G6`) are satisfied by
in-test fixtures with equivalent structure (header table, footer paragraph,
header-hosted textbox) — the sample files themselves are out of scope.

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | unit (collection) | tests/test_docx_header_footer.py::TestNativeCollectionLeavesNoSourceText | 0 |
| AC-2 | unit (collection, walker reuse) | tests/test_docx_header_footer.py::TestHeaderTableAndNestedTableCollected | 0 |
| AC-3 | unit (txbxContent-strip) + unit (COM call-site guard) | tests/test_docx_header_footer.py::TestTxbxContentStrippedFromHeader, tests/test_docx_header_footer.py::TestComCallSiteUnchanged | 0 |
| AC-4 | unit (element-identity dedup) | tests/test_docx_header_footer.py::TestLinkedPartCollectedOnce | 0 |
| AC-5 | unit (six-slot traversal) | tests/test_docx_header_footer.py::TestAllSixSlotsTraversed | 0 |
| AC-6 | unit (body-order stability) + regression (existing suites unmodified) | tests/test_docx_header_footer.py::TestBodyIndicesUnaffectedByHeaderCollection, tests/test_docx_nested_tables.py, tests/test_docx_parser.py | 0 / 1 |
| AC-7 | integration (restore + doc.save round-trip) | tests/test_docx_header_footer.py::TestWriteBackPersistsAcrossSave | 1 |

## Test Families Required

Mark all that apply: **unit**, **integration**. (contract / e2e / data-boundary
/ resilience / monkey / stress / soak: not applicable — no API/UI/env/load
surface; per change-classification "Tasks Not Applicable".)

| family | tier | notes |
|---|---|---|
| unit — collection | 0 | `_collect_docx_segments` against in-test docs with header/footer content across all 6 slots; asserts on the returned `Segment` list content (text, kind, ctx), never on an internal helper being called |
| unit — dedup (AC-4) | 0 | selection-not-count: assert the linked slot's header text appears in the segment list exactly once, by matching the exact text string, not `len(segs) == N` |
| unit — txbxContent-strip (AC-3) | 0 | header paragraph hosting a textbox: assert the para `Segment.text` excludes the textbox string; a second case builds a BODY paragraph with the same textbox shape and asserts its existing (pre-existing, out-of-scope) fold-in behavior is unchanged, guarding against an accidental global change to `_p_text_with_breaks` |
| unit — COM call-site guard (AC-3) | 0 | patch `com_helpers.postprocess_docx_shapes_with_word` (the process boundary — win32com itself is already absent on Linux) inside a `translate_docx` run and assert the captured `include_headers` kwarg is still `True`; a regression guard, not a Windows-shape-translation test |
| integration — restore/round-trip (AC-7) | 1 | full `translate_docx` (or `_insert_docx_translations` directly) with a mocked LLM client (mock at the client boundary, e.g. the client argument `translate_texts` receives), then `doc.save()` + reopen via `docx.Document()` and assert the header/footer paragraph text changed in the reopened file |
| regression — body/table unchanged (AC-6) | 0 / 1 | `tests/test_docx_nested_tables.py` (all existing tests, unmodified) and `tests/test_docx_parser.py` continue to pass byte-for-byte with no edits; plus one new targeted test asserting body segment 0..N-1 order/text is identical whether or not the document has header/footer content |

## Falsifiability (per family, the exact production change that turns it RED)

- AC-1 (native collection): skip header/footer traversal entirely → collected segments still contain header/footer source text → RED.
- AC-2 (walker reuse): remove the recursive `_process_table`/nested-table call for header/footer roots → header table cells absent from segments → RED.
- AC-3 txbxContent-strip: revert to unfiltered `_p_text_with_breaks` for header/footer paragraphs → textbox text folds into the header para segment → RED.
- AC-3 COM call-site guard: change `include_headers` argument to `False` at the call site → captured kwarg mismatches `True` → RED.
- AC-4 dedup: key the visited-slot set by `id(slot._element)` (or drop the set) → linked header text collected twice → RED (count != 1).
- AC-5 six-slot: omit iterating any one slot (e.g. even-page header) → that slot's distinct marker text is absent from segments → RED.
- AC-6 body-order: move header/footer collection call BEFORE the body walk → body segment 0 text no longer matches the expected first body paragraph → RED.
- AC-7 write-back: pass only body segments (drop header segments) into `_insert_docx_translations` → reopened file's header paragraph still shows source text → RED.

## Existing-fake sweep

Grepped `tests/` for `_collect_docx_segments(`, `docx_processor.Segment(`, and
`from app.backend.processors.docx_processor import`. Only
`tests/test_docx_nested_tables.py` calls `_collect_docx_segments` directly (no
stub reproduces it). `tests/test_output_mode_processors.py` and
`tests/test_ir_pipeline_decoupling.py` call the real `translate_docx`/`Segment`
against real in-test-built documents (default, empty headers/footers per
design.md Q4 — zero added segments), not a hand-rolled fake of the collector.
No DOCX collection fake/stub found that this change would break.

## Test Execution Ladder

| phase | required | command source | max failures | result artifact |
|---|---:|---|---:|---|
| collect | yes | `conda run -n translate-tool cdd-kit test select` | 1 | test-runs/<run-id>/summary.json |
| targeted | yes | `conda run -n translate-tool pytest tests/test_docx_header_footer.py -v` | 1 | test-evidence.yml |
| changed-area | yes | `conda run -n translate-tool pytest tests/test_docx_header_footer.py tests/test_docx_nested_tables.py tests/test_docx_parser.py -v` | 1 | test-evidence.yml |
| contract | if affected | `cdd-kit validate --contracts` | 1 | test-evidence.yml |
| full | final/CI | `conda run -n translate-tool cdd-kit test run --phase full` | 1 | test-evidence.yml |

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| tests/test_docx_nested_tables.py | none (run unmodified) | proves AC-6 body/table behavior is unaffected by this change |
| tests/test_docx_parser.py | none (run unmodified) | proves parser-layer body behavior is unaffected |

## Stop Rules

- Do not run broad pytest before targeted and changed-area phases pass.
- Do not investigate more than the first failure per phase.
- Do not classify any failure as known, pre-existing, waived, or allowed.
- If full suite fails, record the first failure and block the gate.

## Out of Scope

- Header-anchored textboxes on Linux (pre-existing textbox-scope gap, not introduced here).
- The body's pre-existing textbox double-count (`_p_text_with_breaks` + `_txbx_iter_texts` overlap) — must NOT be "fixed" as part of this change.
- PPTX/XLSX header/footer collection (DOCX only, per BR-115).
- Windows COM shape-translation path itself (no COM available in CI; AC-3 is proven by construction via the unit tests above, not by running COM).
- `docs/TEST_DOC/` real sample documents — never read by any test.

## Notes

BR-115 is the sole contract anchor; all seven ACs map onto it. Tier 0 covers
every collection/dedup/strip/order unit (fast, in-memory python-docx only).
Tier 1 covers the `doc.save()` round-trip and the full existing regression
suites. No contract/e2e/data-boundary/resilience/monkey/stress/soak family
applies (no API/UI/env/load surface).
