---
change-id: docx-header-footer-collection
schema-version: 0.1.0
last-changed: 2026-07-11
---

> **R-1 CLOSED by main Claude (live probe, conda translate-tool).** All six slots (`header`, `first_page_header`, `even_page_header`, `footer`, `first_page_footer`, `even_page_footer`) expose `._element` with tag `hdr`/`ftr`, plus `.is_linked_to_previous`, `.paragraphs`, `.tables`. Decisively for AC-4: a second section's linked header returns `is_linked_to_previous == True` AND `s2.header._element is section0.header._element` — the SAME element object — so the element-identity `seen_parts` set dedups linked parts by construction. Evidence: `evidence/probe_r1_slots_and_linking.py`. Backend-engineer need not re-verify the accessor; proceed with `slot._element`.

# Implementation Plan: docx-header-footer-collection

## Objective
Make the native DOCX path collect, translate, and restore header/footer PARAGRAPH
TEXT and TABLES (incl. nested tables) across all six per-section `<w:hdr>`/`<w:ftr>`
slots, on both OSes, by reusing the existing `_process_container_content` walker —
appended AFTER the body walk, deduped by `<w:hdr>`/`<w:ftr>` element identity, with
header/footer paragraph/cell extraction stripping `<w:txbxContent>` so the native
domain stays disjoint from the unchanged Windows COM shapes pass. Zero new table or
restore code; no config flag; no COM call-site change. Satisfies AC-1..AC-7
(change-classification.md) and BR-115 (business-rules.md).

## Execution Scope

### In Scope
- `app/backend/processors/docx_processor.py` only: add a txbx-stripping extractor,
  thread it through the collection closures, and add a six-slot header/footer
  collection block after the body walk.
- New tests in `tests/test_docx_header_footer.py` (test author owns authoring;
  backend-engineer makes them pass).

### Out of Scope
- `com_helpers.py` — untouched. The COM call site (docx_processor.py L1102-1103,
  `include_headers=True`) MUST NOT change (design.md Q1; ADR-0019; AC-3).
- Header-anchored textboxes on Linux (pre-existing textbox-scope gap; design.md Open
  Risks; test-plan.md Out of Scope).
- The body's pre-existing `_p_text_with_breaks` + `_txbx_iter_texts` textbox
  double-count — MUST NOT be "fixed" here (design.md Open Risks).
- Any change to `_p_text_with_breaks` itself, or to the body call at L404 (AC-6
  byte-for-byte body stability).
- PPTX/XLSX header/footer (BR-115 is DOCX-only).
- `business-rules.md` (BR-115 already LIVE 0.32.0), `design.md`, ADR-0019 — do not edit.

## Required Changes

| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | txbx-strip extractor | Add module-level `_p_text_no_txbx(p)` mirroring `_p_text_with_breaks` but excluding `<w:t>/<w:br>/<w:tab>` under `<w:txbxContent>` | backend-engineer |
| IP-2 | closure threading | Thread an optional `text_extractor` param (default = `_p_text_with_breaks`) through the 5 collection closures so the body path is byte-for-byte unchanged and only the header/footer walk uses `_p_text_no_txbx` | backend-engineer |
| IP-3 | header/footer walk | Add six-slot `<w:hdr>`/`<w:ftr>` collection with element-identity dedup, AFTER the body/txbx walk, before `check_document_size_limits` | backend-engineer |
| IP-4 | seam verification | Confirm the `_Header`/`_Footer` root-element accessor by execution before wiring (Known Risks R-1); correct the plan and report if wrong | backend-engineer |
| IP-5 | tests green | Make `tests/test_docx_header_footer.py` pass; keep `test_docx_nested_tables.py`/`test_docx_parser.py`/golden regression green | backend-engineer |

## Source Artifact Pointers

| source | relevant pointer | used for |
|---|---|---|
| design.md | Q1 (COM/native disjoint, Option C strip), Q2 (element-identity dedup), Q3 (order + restore reuse), Q4 (empty parts) | implementation constraints |
| contracts/business/business-rules.md | BR-115; BR-81/BR-113 (element-identity, never `id()`) | behavior contract |
| docs/adr/0019-native-header-footer-com-shape-boundary.md | Decision 1-3, Consequences | ownership boundary invariant |
| change-classification.md | AC-1..AC-7 | acceptance criteria |
| test-plan.md | AC→test mapping; Falsifiability; Test Execution Ladder | tests + phases |
| ci-gates.md | Required Gates; Local Pre-PR Command Sequence | verification commands |

## File-Level Plan

| path or glob | action | notes |
|---|---|---|
| `app/backend/processors/docx_processor.py` after L48 | add helper | `_p_text_no_txbx(p)` — copy of L38-48 with the filtered xpath (Contract Updates → Business logic for the exact predicate). Leave `_p_text_with_breaks` (L38-48) byte-for-byte unchanged. |
| `docx_processor.py` L235 `_add_paragraph` | edit | signature → `_add_paragraph(p, ctx, text_extractor=_p_text_with_breaks)`; L241 `_p_text_with_breaks(p)` → `text_extractor(p)`. |
| `docx_processor.py` L249 `_cell_direct_text` | edit | signature → `_cell_direct_text(cell, text_extractor=_p_text_with_breaks)`; L254 call → `text_extractor(p)`. |
| `docx_processor.py` L261 `_flatten_nested_table_text` | edit | signature → `(table, text_extractor=_p_text_with_breaks)`; L275 pass `text_extractor` into `_cell_direct_text`; L279 recurse `_flatten_nested_table_text(nested, text_extractor)`. |
| `docx_processor.py` L284 `_process_table` | edit | signature → `_process_table(table, ctx, depth, text_extractor=_p_text_with_breaks)`; forward `text_extractor` to L313 `_flatten_nested_table_text`, L333-334 `_add_paragraph`, L346 `_cell_direct_text`, L362-363 recursive `_process_table`. |
| `docx_processor.py` L365 `_process_container_content` | edit | signature → `_process_container_content(container, ctx, depth=1, text_extractor=_p_text_with_breaks)`; forward `text_extractor` to L372 `_add_paragraph`, L375 `_process_table`, L402 recursive `_process_container_content`. |
| `docx_processor.py` L404 body call | DO NOT edit | `_process_container_content(doc._body, "Body", 1)` stays as-is → default extractor → AC-6 byte-for-byte. |
| `docx_processor.py` between L409 and L411 | add block | Six-slot header/footer collection (IP-3 detail below). MUST sit AFTER the body walk (L404) and the body-txbx loop (L406-409), BEFORE `check_document_size_limits` (L411). |

### IP-3 header/footer walk (insert after L409, before L411)
```
seen_parts = set()  # holds <w:hdr>/<w:ftr> ELEMENTS, never id() — BR-81/BR-113/BR-115
_HF_SLOTS = ("header", "footer", "first_page_header",
             "first_page_footer", "even_page_header", "even_page_footer")
for s_idx, section in enumerate(doc.sections):
    for slot_name in _HF_SLOTS:
        slot = getattr(section, slot_name)
        if slot.is_linked_to_previous:      # optimization only, NOT the guarantee
            continue
        root_el = slot._element             # <w:hdr>/<w:ftr> root — VERIFY (R-1)
        if root_el is None or root_el in seen_parts:
            continue                        # element-identity dedup = the guarantee
        seen_parts.add(root_el)
        _process_container_content(
            slot, f"HdrFtr[s{s_idx}:{slot_name}]", 1,
            text_extractor=_p_text_no_txbx,
        )
```
- Pass `slot` itself as `container`: `_process_container_content` reads only
  `container._element` and passes `container` as parent to `Paragraph(...)`/`Table(...)`
  (element-relative; restore is element-relative too, L560-576, L580-630).
- If R-1 shows `slot._element` is NOT the `<w:hdr>`/`<w:ftr>` root, wrap the true root
  element with the existing `SdtContentWrapper`-style `{_element, _parent}` pattern
  (docx_processor.py L397-401) and dedup on that root element — do not change the
  mechanism otherwise.
- Empty/default parts: an iterated empty `<w:hdr>` yields zero segments (design.md Q4).

## Contract Updates

- API: none.
- CSS/UI: none.
- Env: none — no new env var / kill switch (design.md Migration/Rollback; ci-gates.md
  Rollback Policy). If the gate tier-floor trips on capability vocabulary, use
  `tier-floor-override` with rationale (change-classification.md §Required Contracts).
- Data shape: none — reuses existing `Segment` IR and walker output; no new field.
- Business logic: BR-115 already LIVE (business-rules.md 0.32.0) — DO NOT edit. The
  txbx-strip xpath the code MUST implement (IP-1):
  `.//*[(local-name()='t' or local-name()='br' or local-name()='tab') and not(ancestor::*[local-name()='txbxContent'])]`
  (valid lxml XPath 1.0; `ancestor::` axis + `local-name()` predicate supported).
- CI/CD: none — no workflow edit (ci-gates.md §New Workflow Changes).

## Test Execution Plan

| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 | tests/test_docx_header_footer.py::TestNativeCollectionLeavesNoSourceText | header/footer source text collected as segments; none left in source language |
| AC-2 | tests/test_docx_header_footer.py::TestHeaderTableAndNestedTableCollected | 15-cell header table + nested-table cells present in segments |
| AC-3 | tests/test_docx_header_footer.py::TestTxbxContentStrippedFromHeader | header para `Segment.text` excludes textbox string; body-paragraph control keeps existing fold-in (guards against a global `_p_text_with_breaks` change) |
| AC-3 | tests/test_docx_header_footer.py::TestComCallSiteUnchanged | captured `include_headers` kwarg at the COM boundary is still `True` |
| AC-4 | tests/test_docx_header_footer.py::TestLinkedPartCollectedOnce | linked-slot header text appears exactly once (match string, not `len`) |
| AC-5 | tests/test_docx_header_footer.py::TestAllSixSlotsTraversed | each slot's distinct marker text present in segments |
| AC-6 | tests/test_docx_header_footer.py::TestBodyIndicesUnaffectedByHeaderCollection | body segment 0..N-1 order/text identical with/without header content |
| AC-6 | tests/test_docx_nested_tables.py tests/test_docx_parser.py | pass unmodified (byte-for-byte body/table behavior) |
| AC-7 | tests/test_docx_header_footer.py::TestWriteBackPersistsAcrossSave | reopened saved file shows translated header/footer text |

Required phases (floor: collect, targeted, changed-area; contract added because
`business-rules.md` is an affected contract; full for CI). Run via `cdd-kit test run`;
the gate validates `test-evidence.yml`. Ladder and exact commands: test-plan.md
§Test Execution Ladder and ci-gates.md §Local Pre-PR Command Sequence. The
`translate-tool` conda env is required for the full phase (torch import).

## Handoff Constraints

- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved.
- Do not touch `com_helpers.py`, the COM call site, `_p_text_with_breaks`, the L404 body call, or `business-rules.md`/`design.md`/ADR-0019.

## Known Risks

- **R-1 (must verify by execution before wiring — IP-4):** the `_Header`/`_Footer`
  root-element accessor `slot._element` could not be confirmed against live
  python-docx (it resides in the `translate-tool` conda env, outside read scope, and
  this agent has no shell). design.md Q2 and ADR-0019 assert `slot._element` is the
  `<w:hdr>`/`<w:ftr>` root. Backend-engineer MUST confirm by execution, e.g.
  `conda run -n translate-tool python -c "import docx; d=docx.Document(); s=d.sections[0]; h=s.header; print(type(h._element), h._element.tag, h.is_linked_to_previous)"`
  — and that a linked slot has `is_linked_to_previous == True` (so the loop skips it
  before touching `._element`). If `slot._element` is not the `<w:hdr>`/`<w:ftr>` root
  or raises, use the `SdtContentWrapper` wrapper fallback (IP-3) and correct this plan.
  The Section slot properties (`header`, `footer`, `first_page_header`,
  `first_page_footer`, `even_page_header`, `even_page_footer`) and
  `is_linked_to_previous` are stable public python-docx API and are treated as confirmed.
- **R-2 (element-identity, not `id()`):** `seen_parts` MUST hold the root elements
  themselves (lxml proxies are hashable and cached while referenced), never
  `id(root_el)` — a recycled proxy address would double-collect/double-write a linked
  part (BR-81/BR-113/BR-115). The set retains the elements for the collection duration,
  same discipline as the existing `seen_tc`/`seen_par_keys`.
- **R-3 (txbx-strip scope):** the strip MUST apply to header/footer paragraph AND cell
  text (a header table cell can host a textbox), which is why `text_extractor` is
  threaded through `_process_table`/`_cell_direct_text`/`_flatten_nested_table_text`,
  not only `_add_paragraph`. Reusing `_p_text_with_breaks` for header/footer would
  reintroduce a Windows double-translation (ADR-0019 Consequences; AC-3).
- **R-4 (order):** the block MUST be inserted after L409 and before L411 so body para
  indices 0..N-1 and `docx:{stem}:{idx}` hook numbering are unchanged (AC-6). Header
  tables get `next_table_id` values continuing after body tables; body table_ids are
  already assigned during the L404 walk and stay stable.
- **R-5 (code-map freshness):** line numbers above are from a direct read of live
  `docx_processor.py` (1105 lines) this session; if edits shift lines mid-task,
  re-anchor by symbol name, not by number.
