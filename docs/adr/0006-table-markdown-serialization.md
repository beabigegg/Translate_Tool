# ADR 0006: Markdown pipe-grid as the table-translation wire format

## Status
proposed

## Context
Tables (DOCX/XLSX/PPTX/PDF) were translated cell-by-cell with no row/column
context, producing wrong translations for homographs, bare numbers, and
units. The table-context-translation change sends each table to the LLM as one
serialized string with the instruction before the table, then remaps the
response onto cells. The chosen serialization format is a long-lived, hard-to-
reverse decision: it is baked into the shared serializer, both client prompt
builders, the remap/fallback logic, and the data-shape contract, and every
table translation flows through it. Candidate formats: HTML (`<table><tr><td>`),
Markdown pipe-grid (`| a | b |`), and OTSL.

## Decision
Use a Markdown pipe-grid. Cell content is sanitized (newline→space, literal
`|`→`\|`); numeric/empty cells are kept as positional placeholders so the grid
shape is stable. The response is accepted only when it round-trips to the exact
`num_rows × num_cols` shape; any mismatch discards the whole-table result and
falls back to the existing per-cell SEG batch. Serialization and parsing live in
one shared utility consumed by all formats; the instruction-before-table wrapper
is the only client-side addition.

## Consequences
- Local models (Gemma/Ollama) handle Markdown more reliably than HTML and emit
  fewer tokens; round-trip parsing is `split('\n')` then `split('|')`.
- Strict shape validation makes malformed responses safe (deterministic fallback)
  but a model that normalizes `\|` escapes or reflows multi-line cells forces
  that table back to per-cell translation, losing whole-table context.
- Reversing to HTML/OTSL later means re-touching the serializer, both prompt
  builders, the remap contract, and the data-shape contract — hence this ADR.
- No IR schema change; header semantics rely on a positional heuristic
  (row 0 = column headers, col 0 = row headers), not an `is_header` field.
