# Design: p3-table-structure

## Summary
Adds an optional ML table-structure recognizer (`parsers/table_recognizer.py`, TableFormer/TATR) that decomposes PDF `table`-typed regions into a row/col/cell `TableStructure`, attached to the parent `TranslatableElement.metadata["table_structure"]`. A new cell-batch seam in `translation_service.py` translates each table's text-bearing cells in exactly one coalesced LLM call, passing numeric/empty cells through unchanged, and reconstructs the parent element's `translated_content` as tab/newline-delimited text. The recognizer follows the ADR 0003 lazy-load + fail-soft pattern: when weights or the runtime are absent, the table region degrades to a plain `table` element and the existing flatten path applies. No wire-schema change to `TranslatableElement`; no data migration; PDF-only scope. See `contracts/data/data-shape-contract.md §Table/Cell IR` and `contracts/business/business-rules.md BR-68..BR-71 / Table T`.

## Affected Components
| component | file path(s) | nature of change |
|---|---|---|
| Table recognizer (new) | `app/backend/parsers/table_recognizer.py` | new optional ML module; produces `TableStructure`; lazy-load + fail-soft |
| IR model | `app/backend/models/translatable_document.py` | add `TableCell`/`TableStructure` dataclasses + `to_dict`/`from_dict` under `metadata["table_structure"]`; no new top-level field |
| PDF parser | `app/backend/parsers/pdf_parser.py` | after table detection, hand `table`-region elements to recognizer; attach result to metadata |
| Numeric predicate | `app/backend/utils/text_utils.py` | add `is_numeric_cell()` (BR-68 predicate) |
| Cell-batch seam | `app/backend/services/translation_service.py` | new `translate_table_cells()` pre-pass per table element |
| PDF processor | `app/backend/processors/pdf_processor.py` | route `table`+structure elements through cell-batch seam before flatten batch |
| Chunker | `app/backend/services/doc_chunker.py` | treat structured `table` element as atomic (never split) |
| Config | `app/backend/config.py` | add `TABLE_RECOGNITION_ENABLED`, `TABLE_RECOGNITION_MODEL_PATH` |

## Key Decisions

**D1 — ML runtime / failure mode**: `TableRecognizer` mirrors `LayoutDetector` (ADR 0003): lazy `_load_session()` cached after first use, `_session_load_failed` latch, 3-tier weight resolution (env path → HF cache → HF auto-download), CPU-only ONNX default with opt-in CUDA. Inference **input is the rasterized table-region crop** of the PDF page (PyMuPDF pixmap of the `table` bbox), consistent with the privacy boundary (image created/consumed/discarded in-module, no network client import). Failure mode is **fail-soft per BR-71**: absent weights/runtime/load-error → WARNING logged once (reason + doc id), no `TableStructure` attached, region stays a plain `table` element → existing flatten path. Gated by `TABLE_RECOGNITION_ENABLED` (default off until weights are validated). → Rejected full-page rasterization: wasteful and conflates with `layout_detector`'s own page raster; the region crop is the precise unit TATR/TableFormer expect.

**D2 — Cell IR attachment point**: Confirm `metadata["table_structure"]` on the parent `table`-typed `TranslatableElement` (per `data-shape §Attachment to the IR`). The `metadata` dict already round-trips and is `object`-typed, so old-format consumers and pre-p3 serialized IR are unaffected. → Rejected new top-level `TranslatableElement.table_structure` field: forces every consumer/serializer to defend a nullable field and breaks the additive-compatibility guarantee for no benefit.

**D3 — Reconstruction format (NORMATIVE)**: After cell-batch translation, the parent element's `translated_content` is the cells' `translated_content` joined **tab-separated within a row (`\t`), newline-separated between rows (`\n`)**, emitted in row-major order over `num_rows`×`num_cols`. Merged cells emit their text once at their origin `(row, col)`; spanned positions emit empty string. A literal tab/newline inside a cell's source is not escaped — cells are short; renderers treat the reconstruction as a layout hint, and the authoritative per-cell text remains in `TableStructure.cells`.

**D4 — QE scoring scope**: QE scores **only the parent `table` element's reconstructed `translated_content`**, not individual cells. Per `data-shape §QE scoring scope`, `BlockQualityScore.block_id` keys on `TranslatableElement.element_id`; `TableCell` objects are not top-level elements and have no stable scorable id. Scoring the reconstruction keeps one score per element, avoids inflating the score array per table, and keeps QE decoupled from the cell-batch internals.

**D5 — Chunker atomicity**: A `table`-typed element carrying `metadata["table_structure"]` is an **atomic chunk unit**. The chunker never places a cut boundary mid-element (elements are already atomic at the `TranslatableElement` level). The cell batch is executed by the translation seam, not the chunker. Add a guard so a structured `table` element is never a mid-element split target and the BR-48 own-chunk path is triggered when the element is oversized.

**D6 — Batch seam placement**: The cell-batch logic lives in **`translation_service.translate_table_cells(element, targets, src_lang, client, ...)`** — a per-table pre-pass invoked by `pdf_processor` (and the Doc2Doc path) for each `should_translate` element where `element_type == "table"` and `metadata["table_structure"]` is present, *before* the flatten `translate_blocks_batch` call. It coalesces non-numeric, non-empty cells into one `translate_blocks_batch` call (reusing the existing model_router fallback), writes per-cell `translated_content`/`translation_status`, then sets the parent's `translated_content` per D3. Structured-table elements are then excluded from the flatten batch (BR-70).

## Rejected Alternatives
- **Per-cell LLM calls** instead of one batch per table: violates BR-69, multiplies latency/cost by cell count, and defeats context sharing across a table's cells.
- **DOCX/PPTX in scope** (CER-001): those formats already carry native table structure with no ML needed; unifying them is a separate data-flow with different producers. Deferred; CER-001 stays pending.
- **New top-level IR field** vs. metadata: see D2 — breaks additive backward-compat for no gain.

## Migration / Rollback
No data migration: `TableStructure` lives in the existing `metadata` dict; pre-p3 serialized IR deserializes unchanged (`from_dict` never raises on absent key). Rollback is config-only: set `TABLE_RECOGNITION_ENABLED=false` (or remove weights) → recognizer never attaches structure → every `table` region falls back to the pre-change flatten path. Graceful degradation (BR-71) means a partial or failed model load on a live job never fails the job.

## Open Risks
- D3 tab/newline reconstruction is lossy for cells containing literal tabs/newlines; acceptable because `TableStructure.cells` stays authoritative, but renderers must consume cells (not the flattened string) for coordinate placement — flag for renderer-side follow-up if PDF table re-rendering is added later.
- Inference input as region-crop assumes the `table` bbox from PyMuPDF/layout detector is reliable; a wrong bbox degrades recognition quality (not correctness — fail-soft still applies).
