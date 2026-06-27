# ADR 0007: Bilingual DOCX output as a two-column source/translation table

## Status
proposed

## Context
Wave 3 Track F adds a `bilingual` value to the `output_mode` enum for DOCX
(`office-output-mode` change). The feature is benchmarked against CAT/MT platforms
(DeepL, Smartcat, Crowdin, Phrase, Trados), all of which export bilingual DOCX as an
aligned dual-column artifact. The architectural choice is between:
(a) a two-column Word table — col-A = source, col-B = translation, one row per segment; or
(b) alternating paragraphs — a translation paragraph inserted below each source paragraph in
a distinct style/color.

The existing `append` mode already inserts the translation as a separate styled paragraph
below the source, so option (b) is effectively indistinguishable from `append`.

## Decision
Bilingual DOCX is rendered as a two-column table, source in col-A and translation in col-B,
one row per body paragraph. The source paragraph's `<w:p>` element is relocated into col-A so
run-level formatting (bold, color, size) is preserved. Non-paragraph blocks (existing tables,
images, text boxes, headers/footers) are NOT wrapped into the table; they remain in document
order under their existing append/replace handling. `bilingual` requested on a non-DOCX file
in a mixed-format job degrades to `append` at the orchestrator (mirroring the BR-67
multi-target `replace`→`append` clamp) and emits a job `warnings` notice.

## Consequences
- Round-trip into CAT tooling works: dual-column tables re-import as aligned bitext.
- The new enum value is meaningfully distinct from `append`, justifying the contract change.
- Layout fidelity for the document as a whole is intentionally traded for side-by-side
  comparison; embedded objects keep single-language layout. This is acceptable because
  `bilingual` is an opt-in review artifact, not the default layout-faithful path.
- Future engineers must not silently re-implement `bilingual` as styled alternating
  paragraphs — that would collapse it back into `append` and break CAT round-trip.
- Implementation must handle paragraphs already inside tables, headers/footers, multi-column
  sections, and SDT-wrapped content as explicit pass-through cases.
