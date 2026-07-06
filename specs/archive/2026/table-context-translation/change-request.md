# Change Request

## Original Request

Wave 2 Track D — table-context-translation: serialize whole table to HTML/Markdown for LLM context, add column context to dedup key, number+unit+header co-occurrence (items 1.1, 1.2, 1.4 from docs/improvement-plan.md).

Specifically:
- 1.1: Tables should no longer be sent cell-by-cell. Serialize each table to HTML or Markdown with the instruction placed before the table, send whole table in one LLM call.
- 1.2: Dedup key must include column context (key = (text, column_index) instead of text only) so the same string in different columns can receive different translations.
- 1.4: Each cell's LLM context should include adjacent header/unit cells so that numbers+units+headers appear together.

## Business / User Goal

Table cell translations currently lack context: the same cell text (e.g. "No.", "Lead", numbers) is translated in isolation, causing wrong translations due to missing column/row/table-header context. This is a key differentiator: even commercial CAT tools still translate tables cell-by-cell.

## Non-goals

- 1.3 (fix `_parse_outputs()` placeholder for TATR) — already shipped in Wave 1 PR#5 (tatr-parse-outputs change)
- 2.x Office output mode changes — separate Track F (Wave 3)
- PDF rendering refactor — separate Track G (Wave 2)
- Any changes to the quality evaluator or critique loop

## Constraints

- `processors/{docx,xlsx,pptx}_processor.py` are owned by this track; Track F (Wave 3) waits for this track to merge.
- `ollama_client.py` prompt builder is the single shared translation entry point for all formats.
- `TABLE_RECOGNITION_ENABLED` defaults to false; the TATR path is for PDF tables only.
- Must not break existing non-table translation paths.
- Must not change API surface (no new endpoints needed).

## Known Context

- All four formats (DOCX, XLSX, PPTX, PDF) currently send table cells as flat deduplicated strings with no row/column context.
- The only prompt builder is `clients/ollama_client.py:625-647` which creates a flat list.
- `translation_service.py:614` sends `batch_texts=[c.content ...]` for PDF TableCell IR — the IR already has row/col/span fields but they are not used.
- Dedup in xlsx_processor.py:134-139 drops r/c before translation.
- DOCX computes Tbl(r,c) labels for dedup only (docx_processor.py:243, :584-589).

## Open Questions

None — improvement-plan.md items 1.1, 1.2, 1.4 are the full scope.

## Requested Delivery Date / Priority

Wave 2 — high priority (unblocks Track F in Wave 3).
