# ADR 0019: Native header/footer text ownership and the COM shape boundary

## Status
proposed

## Context
DOCX header/footer paragraphs and tables were never translated on any OS. The
native collector (`_collect_docx_segments`, docx_processor.py) walked only
`doc._body`. The only header-touching code — `postprocess_docx_shapes_with_word`
(com_helpers.py), gated by `is_win32com_available()` and Windows-only — iterates
`sec.Headers/Footers(...).Shapes` and translates each shape's `TextFrame`. A
header `<w:tbl>` or paragraph is not a `Shape`, so the user's real 15-cell header
tables were dropped on Windows as well as Linux, not merely on Linux.

The change classification assumed the native path and the COM path would compete
over headers and asked for a runtime mutual-exclusion invariant. Live source
refutes that premise: the two paths address disjoint content domains.

## Decision
1. The native path owns header/footer PARAGRAPH TEXT and TABLES (including nested
   tables) on BOTH operating systems, unconditionally, by reusing the BR-113/BR-114
   `_process_container_content` walker against each section slot's
   `<w:hdr>`/`<w:ftr>` root. The native paragraph extraction must EXCLUDE
   `<w:txbxContent>` text: the reused `_p_text_with_breaks` xpath is
   descendant-or-self and otherwise folds a hosted textbox's text into the
   paragraph string, which the COM shapes pass also translates — a filtered xpath
   keeps the native domain to "paragraph text + tables" and prevents a Windows
   double-translation of header-anchored textboxes.
2. The COM pass retains ownership of header-anchored SHAPES only. Its call site
   and `include_headers=True` argument are unchanged; that flag gates a shapes
   pass, not header text.
3. All six per-section slots (default / first-page / even-page × header / footer)
   across every section are visited; shared/linked parts are collected once,
   deduplicated by holding the `<w:hdr>`/`<w:ftr>` element in a set (never `id()`,
   whose lxml proxy address recycles — BR-81/BR-113).

## Consequences
- **The invariant future changes must not reverse:** header/footer PARAGRAPH
  TEXT+TABLES and header-anchored SHAPES (incl. paragraph-hosted textboxes) are
  disjoint content domains owned by the native path and the COM path respectively.
  The `txbxContent` strip in native paragraph extraction is what makes them disjoint
  — reverting it (reusing `_p_text_with_breaks` unmodified) re-introduces a Windows
  double-translation of header textboxes. Separately, setting `include_headers=False`
  to "prevent double translation" would be a silent regression — it disables the
  Windows-only shape pass while translating nothing extra. Exactly-once holds by
  construction (given the strip), not by a switch.
- Residual: header-anchored textboxes stay unhandled on Linux — a pre-existing
  textbox-scope gap (the body already leaves header textboxes to COM), not worsened
  here. The body itself double-counts body textbox text today
  (`_p_text_with_breaks` fold + `_txbx_iter_texts`); that predates and is orthogonal
  to this change.
- Additive: strictly increases collected text (like ADR-0018 recursion). No new IR
  field, no config flag, no kill switch — rollback is a code revert of the new
  helper and its single call.
- Element-identity dedup keeps linked/shared parts collected and written back once,
  consistent with the BR-81 merged-cell discipline.
- Extends ADR-0018's walker reuse to a new container root; supersedes nothing.