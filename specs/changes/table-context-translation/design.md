# Design: table-context-translation

## Summary
Tables stop being translated as isolated, position-stripped cell strings. Each recognized table is serialized once into a Markdown pipe-grid (header row and header column included inline), wrapped with an instruction-before-table prompt, sent as a single LLM call, and remapped back onto cells by grid position. Serialization + remap live in one shared utility so the Ollama (local) and OpenAI-compatible (cloud) clients behave identically. Across the flat per-format dedup streams the cell dedup key gains a column dimension so identical text in different columns gets independent translations. The PDF `TableCell` IR path (already one-batch-per-table) is upgraded to the same serializer, consuming its existing `row`/`col` fields. No API, env, or IR-schema change.

## Affected Components
| component | file path(s) | nature of change |
|---|---|---|
| Shared table serializer/remap | `app/backend/utils/table_serializer.py` (NEW) | `serialize(cells)->str`, `parse(text, num_rows, num_cols)->grid\|None` |
| Local prompt builder | `app/backend/clients/ollama_client.py` (~625) | add `_build_table_translate_prompt` (instruction before serialized table) |
| Cloud prompt builder | `app/backend/clients/openai_compatible_client.py` (~193) | mirror table prompt method; identical wording |
| PDF cell-batch path | `app/backend/services/translation_service.py` (540–660, esp. :614) | replace raw `batch_texts=[c.content]` with serialize→single call→remap by (row,col) |
| DOCX processor | `app/backend/processors/docx_processor.py` (239–244, 584–589, restore) | group table cells per `Tbl(r,c)`; dedup+tmap key gains `col` |
| XLSX processor | `app/backend/processors/xlsx_processor.py` (120–139) | per-table grouping; dedup+tmap key gains `col` (sheet col) |
| PPTX processor | `app/backend/processors/pptx_processor.py` (258–262) | per-table grouping; dedup+tmap key gains `col` |
| IR model | `app/backend/models/translatable_document.py` | NO change — positional header heuristic; no `is_header` field added |
| Contracts | `contracts/business/business-rules.md`, `contracts/data/data-shape-contract.md` | new BR (one-serialized-call, instruction-before-table, per-column dedup) + D-section (serialization shape, remap) — owned by contract-reviewer |

## Key Decisions
- **Q1 Format = Markdown pipe-grid**: rationale → Gemma/local models are far more reliable on Markdown than HTML, it is token-cheap, row delimiter is `\n` and cell delimiter `|` (trivial round-trip). Cell content is sanitized: newline→space, literal `|`→`\|`. → rejected HTML (`<td>`: verbose, models mutate whitespace/attributes, harder/looser to parse), rejected OTSL (models untrained on it, niche).
- **Q2 Remap = strict positional match with full-table fallback**: parse response to a grid; accept only when `line_count==num_rows` AND every row has `num_cols` cells; assign back by origin `(row,col)`. Any shape/parse mismatch DISCARDS the whole-table result and falls back to the existing per-cell SEG batch (BR-69). → rejected best-effort partial assignment: silent off-by-one shifts corrupt cell mapping (violates AC-8).
- **Q3 Dedup key = `(text, col)`**: change set/dict key and the `tmap` key `(tgt, src_text)` → `(tgt, src_text, col)` in all three office processors; non-table segments use `col=None` so paragraph behavior is unchanged. Both build and restore (`_insert_*translations`) must use the new key. → rejected key-on-text-only: collapses cross-column homographs (e.g. "Lead" the metal vs "Lead" the verb) into one translation (violates AC-3).
- **Q4 PDF uses the same shared serializer**: `translation_service.py` serializes directly from `TableStructure.cells` (true `row`/`col`/`span` already present) via the shared utility, not via a client-internal path. PDF does NOT get the `(text, col)` flat-dedup change — its cells are already position-unique inside `TableStructure` and never enter the office tmap stream. → rejected duplicating serialization inside the client: PDF would diverge from office formats.
- **Q5 Serialization lives in a shared utility, not the clients**: the cloud client translates sequentially and the local client batches with SEG markers — neither is table-aware; duplicating logic in both risks divergence. The utility emits ONE string; the instruction-before-table wrapper is the only client-side addition (one mirrored method per client) to satisfy AC-2's "produced by the builder". → rejected per-processor serialization: 3× duplication, drift across formats.
- **Q6 Header detection = positional heuristic (row 0 = column headers, col 0 = row headers)**: no `is_header` flag exists in `TableCell`, and 1.4 is satisfied for free — because the WHOLE table (header row + header column) is in the single serialized string, every cell co-occurs with its column header, row header, and unit cells. → rejected adding an `is_header` IR field: schema churn for no gain; rejected ML header inference: out of scope. Accepted limitation: tables without a header row/col get no semantic header (positional cells still co-occur).

## Data Flow
```
table cells [(row,col,content,is_numeric)]
        │  (numeric/empty cells kept as positional placeholders)
        ▼
serialize() ── num_rows × num_cols Markdown pipe-grid (| esc, \n→space)
        ▼
client._build_table_translate_prompt(instruction BEFORE grid)
        ▼
single LLM call  (translate_once — identical for Ollama & cloud)
        ▼
parse(response, num_rows, num_cols)
   ├─ shape OK ──► grid ──► assign grid[r][c] → cell.translated_content @ origin
   └─ shape BAD ─► discard ─► fallback: per-cell SEG batch (BR-69) ─► cell map intact
```

## Remap Contract
Input: LLM `response`, expected `num_rows`, `num_cols`, ordered translatable cells (numeric/empty excluded, kept as passthrough/skipped).
1. Keep only response lines containing `|`; for each, strip leading/trailing `|`, split on unescaped `|`, unescape `\|`→`|`, trim.
2. Validate shape: `len(lines)==num_rows` AND `all(len(row)==num_cols)`. Also drop a Markdown header-separator line (`---`) if emitted.
3. If valid: for each non-numeric, non-empty cell at origin `(r,c)` set `translated_content=grid[r][c]`, `translation_status="translated"`. Numeric→`passthrough`, empty→`skipped` (unchanged, BR-68).
4. If invalid (row count, col count, or no delimiters): log mismatch (expected vs got), return `None`; caller falls back to the existing per-cell SEG batch so each cell still maps 1:1 (AC-8). On total LLM failure apply BR-25 placeholder + `failed` status (existing behavior).
5. Spanning cells (`row_span>1`/`col_span>1`) occupy their origin only; spanned grid positions are empty placeholders and are not reassigned.

## Open Risks
- **Manifest path drift**: `Allowed Paths` lists `app/backend/services/translation_helpers.py`, but the real module is `app/backend/utils/translation_helpers.py` (where `translate_blocks_batch` lives) and the new serializer is proposed under `app/backend/utils/`. Implementer needs a context expansion for `app/backend/utils/`.
- **Office grouping is structural, not cosmetic**: DOCX/PPTX/XLSX currently flatten table cells into the same flat paragraph stream; one-call-per-table (AC-1) requires materializing per-table `(row,col)` cell groups separate from the paragraph dedup. This is the largest blast radius and the main regression hazard for non-table paths (regression-report.md required).
- **Delimiter collision**: cells legitimately containing `|` or multi-line content rely on escaping; an LLM that normalizes escapes will trip the strict shape check and force fallback (safe but loses whole-table context for that table).
- **No `is_header` ground truth**: positional heuristic mislabels headerless or transposed tables; acceptable given scope.
