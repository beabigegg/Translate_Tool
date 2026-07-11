# Design: docx-header-footer-collection

## Summary
DOCX header/footer TEXT and TABLES are dropped on every OS today: the native
collector walks only `doc._body`, and the Windows-only COM postprocess touches
header-anchored SHAPES only (`sec.Headers(...).Shapes`), never `<w:hdr>`/`<w:ftr>`
paragraphs or tables. This change makes the native path collect, translate, and
restore header/footer content on both OSes by reusing the existing BR-113/BR-114
`_process_container_content` walker against each section slot's `<w:hdr>`/`<w:ftr>`
root — zero new table/restore code. Because the COM pass and the native pass now
own disjoint content domains (shapes vs. text+tables), the exactly-once invariant
holds by construction, not by a switch, and the COM call site is unchanged.

## Affected Components
| component | file path(s) | nature of change |
|---|---|---|
| header/footer collection | `app/backend/processors/docx_processor.py` (new helper near `_collect_docx_segments` L224; invoked after body walk L404-409) | walk all 6 section slots' `<w:hdr>`/`<w:ftr>` via existing `_process_container_content`; element-identity dedup of shared parts |
| COM postprocess | `app/backend/processors/com_helpers.py` (`postprocess_docx_shapes_with_word` L69) | none — remains shapes-only; call site L1102-1103 unchanged (`include_headers=True` kept; it is a shapes gate, not a text gate) |
| business rule | `contracts/business/business-rules.md` (LIVE 0.31.0) | new BR (see below) |
| decision record | `docs/adr/0019-native-header-footer-com-shape-boundary.md` | new ADR: content-ownership boundary |

## Key Decisions

**Q1 — COM vs native ownership (AC-3).** *Correction to a given fact:* live source
shows `postprocess_docx_shapes_with_word` only iterates `sec.Headers/Footers(...).Shapes`
and translates each shape's `TextFrame`; a header `<w:tbl>` is not a `Shape`, so the
user's 15-cell header tables were never translated on Windows either. The two paths
address **disjoint** content: native owns header/footer PARAGRAPH TEXT + TABLES; COM
retains header-anchored SHAPES only. **Ownership rule:** native owns header/footer
paragraph text and tables on BOTH OSes unconditionally; COM keeps `include_headers=True`
and its shapes pass.

**Boundary caveat (measured, load-bearing for AC-3):** the reused extractor
`_p_text_with_breaks` (docx_processor.py:38) uses a descendant-or-self
`.//*[local-name()='t']` xpath that reaches INTO a `<w:txbxContent>` textbox hosted by a
paragraph and folds the textbox's text into the paragraph string (proven:
`"HDR_PLAIN"` + textbox `"TEXTBOX_IN_HEADER"` → `"HDR_PLAINTEXTBOX_IN_HEADER"`). A
header-anchored textbox is ALSO translated by the COM shapes pass on Windows → double
translation. **Decision (Option C):** the native header/footer paragraph extraction must
STRIP `txbxContent` (a filtered variant of the `.//` xpath that excludes `<w:t>` nodes
under `w:txbxContent`), so the native domain is exactly "paragraph text + tables" and
header-anchored textboxes stay COM-owned on Windows. With that filter, exactly-once holds
**by construction**, no Windows regression. Header textboxes remain unhandled on Linux —
a pre-existing textbox-scope gap (same class as the body), NOT worsened here, tracked as
an out-of-scope follow-up. → Rejected Option A (reuse `_p_text_with_breaks` unchanged and
narrow AC-3 to admit a scoped Windows double-translation residual): dishonest against the
"no new defect" goal when a small filtered xpath removes the overlap cleanly.
→ Rejected: setting `include_headers=False` (the classifier's "obvious candidate") —
it would silently regress header-anchored textbox translation on Windows, since that
flag gates shapes, not header text (the call variable is literally
`include_headers_shapes_via_com`). → Rejected: a runtime mutual-exclusion flag — there
is nothing to mutually exclude; a flag would encode a phantom conflict.

**Q2 — Linked/shared-part dedup (AC-4, AC-5).** Visit all six slots per section
(`header`, `first_page_header`, `even_page_header` and the three footer counterparts)
across every `doc.sections`. Dedup by holding each visited `<w:hdr>`/`<w:ftr>` **element**
(`slot._element`) in a `set` — the same discipline as `_process_table`'s `seen_tc` and
BR-113. A linked slot (`is_linked_to_previous`) proxies the previous section's part, so
its `._element` is already in the set and is skipped. Element-holding is the correctness
guarantee; `is_linked_to_previous` may short-circuit as an optimization but is not relied
on. → Rejected: `id(slot._element)` as key — lxml recycles proxy addresses (BR-81/BR-113).
→ Rejected: keying on section index / `is_linked_to_previous` alone — misses parts shared
by non-adjacent means and duplicates the BR-81 lesson.

**Q3 — Collection order and restore (AC-6, AC-7).** Header/footer collection runs AFTER
the body walk (append after L409, before `check_document_size_limits` L411). Body segment
indices 0..N-1 stay identical, so the `docx:{stem}:{idx}` hook numbering and golden body
regression are unchanged (AC-6). Restore reuses `_insert_docx_translations`: the retained
`Paragraph`/`_Cell` references in header segments write back through `._element` and
persist across `doc.save()` (proven live) — no new restore code. Header tables and any
nested tables inside them flow through `_process_table`, so table/nested-table handling is
zero-new-code (AC-2).

**Q4 — Empty/degenerate parts.** Default-created empty header/footer parts contribute no
segments and are not an error: the walker iterates an empty `<w:hdr>`, `_add_paragraph`
skips blank text, and no `<w:tbl>` means no placeholder cells. Mirrors the body path's
empty handling.

## New Business Rule (shape only — contract-reviewer authors exact text; number from LIVE highest, provisionally BR-115)
Must guarantee: (a) on both OSes the native path collects header/footer paragraphs AND
tables (incl. nested) across all six per-section slots via `_process_container_content`;
(b) a header/footer part shared via `is_linked_to_previous` is collected and written back
exactly once, deduped by `<w:hdr>`/`<w:ftr>` element identity (never `id()`); (c) the
native header/footer paragraph extraction excludes `<w:txbxContent>` text, so the native
domain is exactly "paragraph text + tables" and the COM shapes pass exclusively owns
header-anchored textboxes — each unit translated exactly once, by construction, with no
mutual-exclusion switch.

## Migration / Rollback
Additive; no data migration, no IR field, no new config/flag. **No kill switch** — the
mechanism strictly increases collected text (like ADR-0018 recursion), fixes a silent-drop
bug, and is isolated to one helper plus one call after body collection; rollback is a code
revert of that helper/call, not a runtime toggle. A default-off flag was rejected: it would
ship the fix dormant and keep headers silently dropped — the exact failure being fixed.
The COM call site and signature are untouched, so Windows behavior for shapes is preserved.

## Open Risks
- **Given-fact correction (Q1):** change-request/classification framed COM+native as
  competing over headers and asked for a mutual-exclusion invariant. Live source refutes
  this (COM = shapes only). AC-3 is satisfied by disjoint domains, not a switch —
  contract-reviewer must reword the BR/AC accordingly, and the planner must NOT wire an
  `include_headers=False` change. Implementation-planner should re-verify the walker emits
  no shape/txbx segments before wiring.
- Header-anchored textboxes remain Windows-only (COM); on Linux they stay unhandled — a
  pre-existing textbox-scope gap, not worsened here. Out-of-scope follow-up.
- **`txbxContent`-strip is load-bearing for AC-3** (measured): without it, a header
  paragraph hosting a textbox folds the textbox text into its para segment AND the COM
  pass translates the same textbox as a shape → Windows double-translation. Option C's
  filtered xpath removes this; implementation must not reuse `_p_text_with_breaks`
  unmodified for header/footer paragraphs.
- **Pre-existing body double-count (NOT introduced here):** in the body,
  `_p_text_with_breaks` already folds a paragraph's textbox text into its para segment
  while `_txbx_iter_texts` (L406) separately emits that same textbox text — the body
  double-counts textbox text today. `_txbx_iter_texts` walks `doc._element` (body root)
  only and never reaches header/footer parts, so the native path alone does not
  double-count header textboxes. A future reader must not attribute the body's behavior
  to this change.