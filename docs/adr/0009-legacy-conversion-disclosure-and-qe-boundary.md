# ADR 0009: Legacy-format lossy-conversion disclosure and QE boundary

## Status
proposed

## Context
Legacy `.doc`/`.xls`/`.ppt` files are supported by converting them to
`.docx`/`.xlsx`/`.pptx` via LibreOffice-headless *before* they enter the existing
extraction → layout-detection → translation → rendering → QE pipeline. LibreOffice
conversion is inherently lossy for layout (fonts, spacing, table structure), so a
"successful" pipeline run on a converted file can still be lower-fidelity than the
same content authored natively. The existing QE machinery (`quality_evaluator.py`)
is a reference-free COMET scorer of `(src, mt)` pairs and has no way to know a document
passed through an extra lossy step. Two coupled questions had to be settled before
implementation: (1) how to signal the lossy step to the user, and (2) whether QE should
treat converted documents differently.

## Decision
1. Disclose conversion through the existing `warnings: string[]` job-status field — one
   entry per converted file — reusing the orchestrator's existing `warnings_callback`
   seam. Do NOT add a new `source_format_converted` boolean or other new API field.
2. Do NOT introduce any distinct QE threshold, penalty, or reinterpretation for converted
   documents. QE measures *translation adequacy*; conversion loss is a *layout-fidelity*
   axis that is orthogonal to what COMET scores. Converted documents flow through the
   identical QE path, and a QE score means exactly the same thing regardless of source
   format.

## Consequences
- Disclosure is nearly free: `warnings[]` is already additive, backward-compatible, and
  rendered by the frontend; no new schema or OpenAPI surface beyond a note extension.
- QE remains a single-meaning signal across all formats; users are not led to read QE as
  a layout-fidelity indicator.
- Future engineers MUST NOT silently add a conversion-specific QE penalty or a "QE is only
  advisory for converted docs" reinterpretation — that would conflate two independent
  quality axes and regress the guarantee established here. Any such change must supersede
  this ADR.
- Layout-fidelity concerns for legacy formats are addressed by disclosure, not by QE; if a
  true fidelity metric is ever wanted, it belongs in a new dedicated signal, not in QE.
