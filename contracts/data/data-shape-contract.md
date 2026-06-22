---
contract: data
summary: Data schema, invalid-data handling, and row-level compatibility rules.
owner: application-team
surface: data
schema-version: 0.11.0
last-changed: 2026-06-22
breaking-change-policy: deprecate-2-minors
---

# Data Shape Contract

## Required Columns

### JobStatus.status (server-set enum)
| column | type | nullable | allowed values | fallback | validation |
|---|---|---:|---|---|---|
| JobStatus.status | string | no | `queued`, `running`, `completed`, `stopped`, `failed` | `queued` (initial create) | Set only by JobManager state machine; never supplied by clients. |

### Term.status (application-controlled enum)
| column | type | nullable | allowed values | fallback | validation |
|---|---|---:|---|---|---|
| Term.status | string | no | `unverified`, `needs_review`, `approved`, `rejected` | `unverified` (LLM extraction); `approved` (file import via `_dict_to_term()`) | Set by TermDB state machine methods (`approve()`, `reject()`, `flag_needs_review()`, `edit_term()`). Never supplied raw by API clients except via the state-transition endpoints. |

### POST /api/jobs — multipart/form-data required fields
| column | type | nullable | allowed values | fallback | validation |
|---|---|---:|---|---|---|
| files | file[] | no | any supported extension | — | HTTP 400 if empty; accepted extensions: `.docx .doc .pptx .xlsx .xls .pdf` |
| targets | string | no | comma-separated language codes | — | HTTP 400 if none parse to non-empty after split |

## Optional Columns

### JobStatus / JobRecord — provider field (added in p1-cloud-providers)
| column | type | nullable | allowed values | fallback | validation |
|---|---|---:|---|---|---|
| provider | string | yes | any provider ID from `config/providers.yml` (e.g. `panjit`, `deepseek`, `ollama-local`) | null | Set by orchestrator only at point of successful provider call; never supplied by clients. Null for pre-existing jobs and Ollama-only jobs. Additive optional field — backward-compatible. |

See `contracts/api/api-contract.md > ## Schemas > JobStatus` for the authoritative full field table.

### POST /api/jobs — multipart/form-data optional fields
| column | type | default | notes |
|---|---|---|---|
| src_lang | string | None | source language; auto-detected if omitted |
| include_headers | bool | false | include document headers in translation |
| profile | string | None | manual model/profile override; bypasses auto-routing |
| num_ctx | int | None | LLM context window size; validated per BR-2 |
| pdf_output_format | string | "docx" | output format for PDF jobs: `"docx"` or `"pdf"` |
| pdf_layout_mode | string | "overlay" | PDF rendering mode: `"overlay"` or `"side_by_side"` |
| mode | string | "translation" | job mode: `"translation"` or `"extraction_only"` |

## Invalid Data Behavior
| condition | expected behavior | error code / UI state | test |
|---|---|---|---|
| missing required `files` | reject | HTTP 400 "No files uploaded" | — |
| missing required `targets` | reject | HTTP 400 "No target languages provided" | — |
| wrong type for `num_ctx` (non-int) | reject | HTTP 422 Pydantic validation | — |
| empty `files` list | reject | HTTP 400 "No files uploaded" | — |
| `num_ctx` out of range | reject | HTTP 422 range message (BR-2) | — |
| over max segment/text limit | not rejected at upload; job transitions to `status: "failed"` | job error field | — |
| unexpected `JobStatus.status` | n/a — status is server-set only, never client input | — | — |
| `provider` field set by client | ignored — field is server-set only; not in POST /api/jobs input schema | — | — |
| `element_type` value in serialized IR not in current enum | `from_dict` raises `ValueError` | not caught; propagated to caller | tests/test_translatable_document.py |
| `metadata["table_structure"]` absent on a `table`-typed element (old-format IR or model unavailable) | treated as plain region marker; no cell-batch path invoked; no error | — | tests/test_table_recognizer.py |
| `TableCell.content` empty string in a recognized table | excluded from LLM batch; `translated_content` set to `""`; `translation_status = "skipped"` | — | tests/test_table_recognizer.py |
| `reading_order` absent in serialized IR (old-format document) | `from_dict` defaults to `None`; element is valid | — | tests/test_translatable_document.py |
| `render_truncated` absent in serialized IR (old-format document) | `from_dict` defaults to `False`; element is valid | — | tests/test_translatable_document.py |
| `CHUNK_OVERLAP_TOKENS` ≥ `num_ctx` at chunker init | `ValueError` raised; job transitions to `status: "failed"` | — | tests/test_doc_chunker.py |
| Single element token count > `num_ctx` (atomic oversize) | Element placed in own chunk; LLM call proceeds; failure surfaced if LLM rejects; not silently dropped | — | tests/test_doc_chunker.py |
| `GET /api/jobs/{id}/quality` when job not complete | HTTP 200 `status: "pending"`, empty scores array | — | tests/test_quality_evaluation.py |
| QE model unavailable or scoring exception | QE step skipped; job completes normally; `qe_status = "unavailable"` | — | tests/test_quality_evaluation.py |

## Export / Import Format

- **Job output**: zip archive downloaded via `GET /api/jobs/{id}/download`.
- **Term export**: `GET /api/terms/export?format={json|csv|xlsx}` — full term db or filtered by status (`approved`, `unverified`, `needs_review`, `rejected`).
- **Term import**: `POST /api/terms/import` — multipart file upload (`.json` or `.csv`); strategy controls merge behavior (BR-5).

### TermStatsResponse — data shape
| field | type | nullable | default | notes |
|---|---|---:|---|---|
| total | integer | no | — | total term count |
| unverified | integer | no | 0 | count of terms with status=unverified |
| by_target_lang | object | no | {} | map of lang -> count |
| by_domain | object | no | {} | map of domain -> count |
| needs_review | integer | no | 0 | count of terms with status=needs_review (additive, p1-term-state-machine) |
| approved | integer | no | 0 | count of terms with status=approved (additive, p1-term-state-machine) |
| rejected | integer | no | 0 | count of terms with status=rejected (additive, p1-term-state-machine) |
| by_status | string | no | {} | serialized as JSON map of status -> count for all four statuses (additive, p1-term-state-machine) |

## Row Limit / Truncation Policy

- In-memory job store capped at `MAX_JOBS_IN_MEMORY=100` (BR-8). When at capacity, oldest completed/failed jobs are evicted.
- Jobs expire after `JOB_TTL_HOURS=24` hours; cleanup runs every 30 minutes.
- Document segment/text size limits are effectively disabled (`MAX_SEGMENTS=10_000_000`, `MAX_TEXT_LENGTH=1_000_000_000`). See BR-10.

---

## Intermediate Representation (IR) — TranslatableDocument

**Added in p2-ir-document-model. Source of truth: `app/backend/models/translatable_document.py`.**

The IR is the single authoritative in-memory and serialized form that decouples parse → translate → render. Any parser produces it; any renderer consumes it; the translation layer modifies only `translated_content` fields within it.

### Decoupling guarantee

- A persisted IR (produced by `TranslatableDocument.to_dict()`) can be loaded via `TranslatableDocument.from_dict()` and rendered without invoking any parser.
- Translated text can be replaced in the IR (via `TranslatableElement.translated_content`) and the document re-serialized without re-rendering or re-parsing.

### ElementType enum — valid string values

| value | level | description | status |
|---|---|---|---|
| `text` | text-level | Body text block | existing |
| `title` | text-level | Document or section title | existing |
| `header` | text-level | Page header | existing |
| `footer` | text-level | Page footer | existing |
| `table_cell` | text-level | Single cell of a table | existing |
| `list_item` | text-level | Single item in a list | existing |
| `caption` | text-level | Figure or table caption | existing |
| `footnote` | text-level | Footnote text | existing |
| `table` | region-level | Entire table region (container; enclosing `table_cell` elements). When table structure is recognized (p3-table-structure), the region is backed by a `TableStructure` sub-element record; otherwise it remains a plain region marker. | updated p3-table-structure |
| `figure` | region-level | Figure or image region | added p2-ir-document-model |
| `formula` | region-level | Mathematical formula region | added p2-ir-document-model |
| `list` | region-level | Entire list region (container; may enclose `list_item` elements) | added p2-ir-document-model |

All pre-existing values remain valid and their serialized string forms are unchanged. New region-level values are additive non-breaking: existing consumers that do not recognize them must not raise on deserialization; they may skip or passthrough such elements.

### ElementType wire-value convention

All `ElementType` members MUST use lowercase Python string values as their wire form (e.g. `TABLE = "table"`, `LIST = "list"`). This convention is frozen by ADR 0002 (`docs/adr/0002-ir-elementtype-serialized-values.md`) to guarantee round-trip compatibility across serialized IR snapshots. Any future member whose `value` differs in case is a breaking change and requires a major version bump on this contract.

### ElementType producer inventory

| producer | file path | added in | notes |
|---|---|---|---|
| PDF parser | `app/backend/parsers/pdf_parser.py` | p2-ir-document-model | extracts structural element types from PyMuPDF text/table detection; delegates reading-order to layout detector on native-PDF path; on p3-table-structure, passes detected table regions to `table_recognizer.py` for cell decomposition |
| Layout detector | `app/backend/parsers/layout_detector.py` | p2-layout-detection | maps Docling heron-101 DocLayNet labels to `ElementType` wire values; sets `reading_order`; rasterised page image never leaves the process |
| Table recognizer | `app/backend/parsers/table_recognizer.py` | p3-table-structure | optional ML step (TableFormer/TATR); produces `TableStructure` records attached to `table`-typed `TranslatableElement`; lazy-loads model weights per ADR 0003 pattern; when unavailable, parser falls back to treating table regions as plain `table` elements without cell decomposition |
| DOCX parser | `app/backend/parsers/docx_parser.py` | p2-ir-document-model | populates `reading_order` from element extraction order |
| PPTX parser | `app/backend/parsers/pptx_parser.py` | p2-ir-document-model | populates `reading_order` from element extraction order |

**Label mapping — heron-101 → ElementType (D-4, normative)**

The following table is normative. The implementation constant in `layout_detector.py` MUST match this mapping. Unknown or unmapped heron labels default to `text` (never raise). No new `ElementType` enum members are introduced; all values are existing lowercase wire values per ADR 0002.

| heron-101 label | ElementType wire value | notes |
|---|---|---|
| Text / Paragraph | `text` | body text |
| Title / Section-header | `title` | |
| Page-header | `header` | |
| Page-footer | `footer` | |
| Table | `table` | region container; enclosed lines remain `table_cell` per existing table marking |
| Picture / Figure | `figure` | excluded from translation (future); region marked only |
| Formula | `formula` | pass-through target (future); region marked only |
| List-item | `list` / `list_item` | region → `list`; enclosed lines → `list_item` |
| Caption | `caption` | |
| Footnote | `footnote` | |

### TranslatableElement — serialized field shape (`to_dict` / `from_dict`)

| field | type | nullable | default (from_dict) | notes |
|---|---|---:|---|---|
| element_id | string | no | — | required; unique within the document |
| content | string | no | — | required; original text content |
| element_type | string | no | — | required; must be a valid `ElementType` string value |
| page_num | integer | no | — | required; 1-based page number |
| bbox | object\|null | yes | null | `BoundingBox.to_dict()` output or null |
| style | object\|null | yes | null | `StyleInfo.to_dict()` output or null |
| should_translate | boolean | no | true | whether the element should be translated |
| translated_content | string\|null | yes | null | translated text; null until translation applied |
| metadata | object | no | {} | arbitrary key-value metadata map |
| reading_order | integer\|null | yes | null | **Added p2-ir-document-model.** Explicit reading-order index (0-based) assigned by the parser. When present and non-null, takes precedence over positional sort heuristics. Old-format documents lacking this key deserialize with `reading_order=None` and remain valid. `get_elements_in_reading_order()` uses a two-bucket sort: elements with non-null `reading_order` are placed before elements with `reading_order=None`, sorted by their index value; null elements are placed after, sorted by `(page_num, bbox.y0, bbox.x0)`. In practice, all parsers assign `reading_order` to every element, so mixed-population documents do not occur in normal use. |
| render_truncated | boolean | no | false | **Added p2-text-expansion.** Render-time annotation. Set `True` by the renderer when step (e) of the fit cascade (BR-36) fires (word-boundary truncation with ellipsis). Absent keys in old-format IR deserialize as `False`; backward-compatible. Never set by parsers or the translation layer. Consumers: QA safety net, human-review tooling. See ADR-0004 (`docs/adr/0004-truncation-marker-on-ir.md`). |

### BoundingBox — serialized field shape

| field | type | nullable | notes |
|---|---|---:|---|
| x0 | float | no | left edge, points |
| y0 | float | no | top edge, points |
| x1 | float | no | right edge, points |
| y1 | float | no | bottom edge, points |

Coordinate system: top-left origin; x increases right; y increases down. Unit: points (1 pt = 1/72 inch).

### StyleInfo — serialized field shape (font metadata)

| field | type | nullable | default (from_dict) | notes |
|---|---|---:|---|---|
| font_name | string\|null | yes | null | font family name |
| font_size | float\|null | yes | null | font size in points |
| is_bold | boolean | no | false | bold weight |
| is_italic | boolean | no | false | italic style |
| color | string\|null | yes | null | hex color code (e.g. `#FF0000`) |
| background_color | string\|null | yes | null | hex background color code |

### TranslatableDocument — serialized field shape

| field | type | nullable | notes |
|---|---|---:|---|
| source_path | string | no | original file path |
| source_type | string | no | `pdf`, `docx`, `pptx`, `xlsx` |
| elements | array | no | ordered array of `TranslatableElement.to_dict()` objects |
| pages | array | no | ordered array of `PageInfo.to_dict()` objects |
| metadata | object | no | `DocumentMetadata.to_dict()` object |

### Round-trip guarantee

A document serialized by `TranslatableDocument.to_dict()` then deserialized by `TranslatableDocument.from_dict()` must produce an equivalent IR preserving all of the following fields without loss or mutation: `bbox` (all four float coordinates), `style` / font metadata (all six fields), `element_type`, `reading_order`, `render_truncated`, `element_id`, `content`, `page_num`, `should_translate`, `translated_content`, `metadata`. Floating-point bbox coordinates must round-trip without rounding or truncation. When a `table`-typed element carries `metadata["table_structure"]`, all `TableCell` fields within that structure must survive round-trip without loss (see Table/Cell IR section).

### Backward-compatibility rule

Old-format means a document dict produced by the pre-change `TranslatableElement.to_dict()` (lacking the `reading_order` key). `TranslatableElement.from_dict()` must deserialize old-format dicts without raising; `reading_order` defaults to `None` when the key is absent. Old-format documents deserialized under the new code are valid IR instances and may be passed to any renderer.

`render_truncated` follows the same rule: when the key is absent in an old-format dict, `from_dict()` defaults it to `False`. A serialized IR produced before p2-text-expansion deserializes unchanged and is a valid IR instance.

### `to_dict` compatibility rule

All pre-existing keys (`element_id`, `content`, `element_type`, `page_num`, `bbox`, `style`, `should_translate`, `translated_content`, `metadata`) must remain present in `to_dict` output with the same types and semantics. `reading_order` is added as a new key (integer or `None`). `render_truncated` is added as a new key (boolean, default `False`). No existing key may be renamed, removed, or have its type narrowed.

### Known consumers of the IR

| consumer | surface | impact |
|---|---|---|
| `app/backend/parsers/pdf_parser.py` | producer | extracts text elements; delegates reading-order assignment to `layout_detector.py` on native-PDF text-layer path; retains `round(y0,10pt)` heuristic as per-page fallback (BR-33); passes detected table regions to `table_recognizer.py` (p3-table-structure) |
| `app/backend/parsers/layout_detector.py` | producer (p2-layout-detection) | consumes rasterised page images from PyMuPDF in-process; writes `element_type` (from D-4 label mapping) and `reading_order` onto `TranslatableElement`; never changes wire schema |
| `app/backend/parsers/table_recognizer.py` | producer (p3-table-structure) | optional ML step; attaches `TableStructure` to `table`-typed elements produced by `pdf_parser.py`; falls back gracefully when model is absent (BR-71); never changes wire schema on the `TranslatableElement` level |
| `app/backend/parsers/docx_parser.py` | producer | must populate `reading_order` from element extraction order |
| `app/backend/parsers/pptx_parser.py` | producer | must populate `reading_order` from element extraction order |
| `app/backend/renderers/base.py` | consumer | may consume `reading_order`; must not raise when `None` |
| `app/backend/renderers/coordinate_renderer.py` | consumer | same as base |
| `app/backend/renderers/pdf_generator.py` | consumer — ReportLab fallback renderer (p2-renderer-convergence) | ReportLab fallback; consumes IR via shared bbox-reflow component; invoked only when fitz primary path fails per BR-34 |
| `app/backend/renderers/text_region_renderer.py` | consumer | same as base |
| `app/backend/renderers/inline_renderer.py` | consumer | same as base |
| `app/backend/renderers/fitz_renderer.py` | consumer — fitz primary renderer (p2-renderer-convergence) | fitz primary PDF renderer; consumes IR via shared bbox-reflow component; see BR-34. Writes `render_truncated=True` on elements where cascade step (e) fires (BR-38). |
| `app/backend/processors/orchestrator.py` | processor | no IR schema change required; reads elements after parsing |
| `app/backend/services/doc_chunker.py` | consumer + transformer (p2-long-doc-chunking) | reads elements to build ChunkRecords; does not mutate element fields other than triggering per-chunk translation; a `table`-typed element with a recognized `TableStructure` must be treated as an atomic unit and must not be split across chunk boundaries |
| `app/backend/services/translation_service.py` (Doc2Doc path) | consumer + transformer (p2-long-doc-chunking) | receives full TranslatableDocument; invokes chunker; merges translated_content back into elements; returns the same document instance |
| `app/backend/services/translation_service.py` (cell-batch path) | consumer + transformer (p3-table-structure) | for `table`-typed elements carrying a `TableStructure`, coalesces all translatable cells into a single LLM batch call per table; numeric cells (`is_numeric=True`) excluded from the batch; `translated_content` populated per cell after batch returns (BR-68, BR-69) |
| `app/backend/services/quality_evaluator.py` | consumer (p2-comet-qe) | reads `element_id`, `content`, `translated_content` from IR elements; never mutates IR fields; score stored separately in `JobQualityRecord` |

### Renderer IR-consumption contract

**Added in p2-renderer-convergence.**

Both the fitz primary renderer and the ReportLab fallback renderer MUST consume `TranslatableDocument` via the shared IR-bbox reflow component. Neither renderer may implement independent element-placement logic that bypasses this component.

#### Fields a renderer MUST honor

| field | renderer obligation |
|---|---|
| `bbox` | If non-null, use the bbox coordinates (x0, y0, x1, y1) as the authoritative placement region. If null, the renderer MUST apply a documented fallback placement strategy and MUST NOT raise. |
| `reading_order` | If non-null, use as the explicit placement sequence. If null, fall back to `(page_num, bbox.y0, bbox.x0)` positional sort (same as `get_elements_in_reading_order()` null-bucket rule). MUST NOT raise when `reading_order` is null. |
| `element_type` | Use the wire value to determine rendering treatment (e.g. skip non-translatable regions). An unknown or unrecognized `element_type` string MUST NOT raise; the element MUST be rendered as type `text` (passthrough fallback). |
| `page_num` | Use to assign the element to the correct output page. |
| `translated_content` | If non-null, use as the rendered text. If null, use `content` (source text) as the fallback. |
| `render_truncated` | If the renderer applies word-boundary truncation (cascade step e, BR-36), it MUST set this field to `True` on the element before any further serialization. The renderer MUST NOT set it `True` for any other reason. Parsers and the translation layer MUST NOT set this field. |

#### Malformed IR handling (AC-6)

Both render paths MUST handle the following conditions deterministically and identically:

| condition | required behavior |
|---|---|
| `bbox` is null | Apply documented fallback placement; do not raise. |
| `reading_order` is null | Apply positional sort fallback; do not raise. |
| `element_type` is an unknown string value | Treat as `text`; do not raise; do not skip. |
| `translated_content` is null | Render `content` instead; do not raise. |
| `elements` list is empty | Produce an empty (but valid) output page; do not raise. |

"Identically" means: for the same input IR, both paths must produce the same element-level decisions (skip vs. render, placement region source, text source) even if the visual output differs due to renderer capabilities.

---

## Chunk Representation

**Added in p2-long-doc-chunking. Source of truth: `app/backend/services/doc_chunker.py`.**

The chunk representation is a pure in-memory structure used exclusively within the chunking → translation → reassembly pipeline. It is not serialized to disk, not sent over HTTP, and not part of any `TranslatableDocument.to_dict()` or `from_dict()` surface. The existing `TranslatableDocument` wire schema is unchanged.

### ChunkRecord — internal data shape

| field | type | nullable | notes |
|---|---|---:|---|
| chunk_index | integer | no | 0-based sequential index; determines reassembly order |
| token_span | tuple[int, int] | no | `(start_token, end_token)` inclusive–exclusive token positions in the source element sequence |
| elements | list[TranslatableElement] | no | ordered list of `TranslatableElement` instances included in this chunk; references the same objects as the parent `TranslatableDocument` — do not deep-copy |
| overlap_tokens | integer | no | number of tokens at the start of this chunk that are shared with the previous chunk's tail; 0 for chunk_index 0 |

`ChunkRecord` is never serialized. Consumers must not persist or transmit it. If a future change requires persistence, a versioned serialized form must be defined and added to this contract.

### Doc2Doc — service entry point contract

`translation_service.translate_document(doc: TranslatableDocument, ...) -> TranslatableDocument`

| aspect | contract |
|---|---|
| Input | A fully parsed `TranslatableDocument` instance (all elements populated; `translated_content` fields may be null) |
| Output | The same `TranslatableDocument` instance with `translated_content` populated on every element that has `should_translate=True`; all other fields unchanged |
| Mutation | The input document is mutated in place and returned; callers MUST NOT rely on the pre-call state of `translated_content` after this method returns |
| Chunking transparency | Chunking is applied automatically when the document's estimated token count exceeds the resolved `num_ctx` ceiling. Callers do not pre-split the document |
| Single-chunk optimization | When the document's estimated token count is at or below `num_ctx`, exactly one chunk is produced and one LLM call is made (AC-6); no splitting overhead is incurred |
| Backward-compatibility | The existing `translate_texts()` per-segment path is entirely separate from this entry point and is unaffected (AC-8) |

### Reassembly contract

After each chunk's elements are translated independently, they are reassembled into the final document in strict `chunk_index` ascending order.

**Overlap de-duplication rule:** The overlap region is defined as the `overlap_tokens` leading tokens of each chunk (chunk_index > 0). After translation, the de-duplication rule drops the translated output of the leading `overlap_tokens`-worth of elements from the **start of each non-first chunk's translated output**. Concretely: for chunk N (N > 0), the elements in positions `[0, overlap_element_count)` of that chunk's translated output are discarded; only elements `[overlap_element_count, ...)` are appended to the reassembled document. `overlap_element_count` is the number of elements whose combined token span covers the `overlap_tokens` count recorded in the `ChunkRecord`.

Rationale for dropping from the start of N+1 rather than the end of N: the head of N+1 has already been seen in context by the LLM when it translated N; the tail of N is the "anchor" that carries semantic continuity forward.

**Content integrity invariant:** After reassembly, every element with `should_translate=True` in the original document that was successfully translated MUST have a non-null `translated_content`. No element may appear more than once in the reassembled document. No element may be silently dropped. If a single chunk's translation fails, the failure MUST be surfaced; partial reassembly from remaining chunks is permitted only if the implementation explicitly records which chunks succeeded and which failed (see BR-51).

### Invalid-data behavior — chunking path

| condition | expected behavior |
|---|---|
| Document has zero elements | `translate_document` returns the input unchanged; no LLM call is made |
| Document has all `should_translate=False` elements | Single pass; no chunking; no LLM call; returned immediately |
| Single element whose token count alone exceeds `num_ctx` | Element is placed in its own chunk; LLM call proceeds; not silently dropped (BR-48) |
| `CHUNK_OVERLAP_TOKENS` ≥ chunk token ceiling | `ValueError` raised at chunker initialization; job transitions to `failed` |
| Empty string element content | Treated as a zero-token element; `translated_content` set to empty string |

---

## Table/Cell IR (p3-table-structure)

**Added in p3-table-structure. Source of truth: `app/backend/parsers/table_recognizer.py` and `app/backend/models/translatable_document.py`.**

The table/cell IR extends the unified `TranslatableDocument` IR to represent structured table content recognized by an optional ML model (TableFormer or TATR). It is a pure in-memory structure. `TableStructure` is carried in the `metadata` dict of the parent `TranslatableElement` under the key `"table_structure"` so that old-format IR consumers that do not read `metadata` are unaffected.

### Scope

Table structure recognition applies to **PDF documents only** in p3-table-structure. DOCX/PPTX native table elements are out of scope (CER-001 deferred). For non-PDF formats, this section does not apply.

### TableCell — in-memory data shape

| field | type | nullable | default | notes |
|---|---|---:|---|---|
| cell_id | string | no | — | Unique within the parent `TranslatableElement`; format: `"{element_id}:r{row}:c{col}"` (0-based row/col indices) |
| row | integer | no | — | 0-based row index within the table |
| col | integer | no | — | 0-based column index within the table |
| row_span | integer | no | 1 | Row span for merged cells; 1 = no merge |
| col_span | integer | no | 1 | Column span for merged cells; 1 = no merge |
| content | string | no | — | Original cell text content; may be empty string for blank cells |
| is_numeric | boolean | no | false | `True` when `content` consists solely of digits, whitespace, and common numeric separators (`. , / - %`); determined by `text_utils.is_numeric_cell()`. When `True`, cell is excluded from LLM batching and `translated_content` is set to `content` unchanged (BR-68). |
| translated_content | string\|null | yes | null | Cell-level translated text; null until translation applied; populated by the cell-batch seam (BR-69); for numeric cells, set equal to `content` without an LLM call |
| translation_status | enum | no | `pending` | One of: `pending`, `translated`, `passthrough` (numeric per BR-68), `skipped` (empty cell), `failed` (LLM batch error) |

### TableStructure — in-memory data shape

| field | type | nullable | default | notes |
|---|---|---:|---|---|
| num_rows | integer | no | — | Total row count as recognized by the ML model |
| num_cols | integer | no | — | Total column count as recognized by the ML model |
| cells | list[TableCell] | no | [] | Flat ordered list of all cells in reading order (row-major); empty for tables with zero recognized cells |
| recognizer | string | no | — | Name of the model/path that produced this structure (e.g. `"TATR"`, `"TableFormer"`) |
| recognition_confident | boolean | no | true | `False` when the recognizer's confidence score falls below the configured threshold |

### Attachment to the IR

`TableStructure` is stored in the `metadata` dict of the parent `table`-typed `TranslatableElement` under the key `"table_structure"`. The `TranslatableElement.metadata` field already exists and is `object` typed. No new top-level field is added to `TranslatableElement`. Old-format consumers that do not read `metadata["table_structure"]` are unaffected.

When serialized (`to_dict()`), `metadata["table_structure"]` is a plain dict containing `num_rows`, `num_cols`, `cells` (list of cell dicts), `recognizer`, and `recognition_confident`. Each cell dict exposes all `TableCell` fields: `cell_id`, `row`, `col`, `row_span`, `col_span`, `content`, `is_numeric`, `translated_content`, `translation_status`. Round-trip guarantee: all `TableCell` fields must survive `to_dict()` → `from_dict()` without loss.

When `TableStructure` is absent from `metadata` (model unavailable, or non-PDF input), the `table` element behaves exactly as a plain region marker per existing p2-ir-document-model behavior.

### Cell-batch IR-consumption contract

| obligation | contract |
|---|---|
| Consumer | `app/backend/services/translation_service.py` (cell-batch path) |
| Input | A `TranslatableElement` with `element_type = "table"` and `metadata["table_structure"]` present |
| Batch coalescing | All `TableCell` entries from the same `TableStructure` whose `is_numeric=False` and `content` is non-empty MUST be sent to the LLM in **a single batch call** per table (BR-69) |
| Numeric exclusion | Cells with `is_numeric=True` MUST be excluded from the LLM batch; `translated_content = content`; `translation_status = "passthrough"` (BR-68) |
| Empty cell handling | Cells with `content == ""` are excluded from the batch; `translated_content = ""`; `translation_status = "skipped"` |
| Translation result assignment | After the batch call returns, each cell's `translated_content` and `translation_status` are updated in place; the parent `TranslatableElement.translated_content` is set to a reconstructed table representation (format: tab-separated cells, newline-separated rows); see design.md §Reconstruction Format |
| Batch failure | If the LLM batch call fails, the BR-25 failure placeholder is applied to all non-numeric cells' `translated_content`; `translation_status = "failed"` for those cells; job's `fail_cnt` incremented |
| No flattened translation | A `table`-typed element with a recognized `TableStructure` MUST NOT be translated as a flattened paragraph (BR-70) |
| Chunker atomicity | A `table`-typed element with a recognized `TableStructure` MUST be treated as an atomic unit by the chunker; its cell batch MUST NOT be split across chunk boundaries |
| QE scoring scope | The parent `table` element's reconstructed `translated_content` is the QE scoring surface; individual `TableCell` objects are not top-level `TranslatableElement` objects and are not scored independently |

### Degenerate table handling

| condition | expected behavior |
|---|---|
| All cells are numeric | No LLM call; all cells get `translation_status = "passthrough"` |
| All cells are empty | No LLM call; all cells get `translation_status = "skipped"` |
| `cells` list is empty | No LLM call; parent element `translated_content = ""`; job continues |
| Merged/spanning cells | Each merged cell is one `TableCell`; `row_span`/`col_span` recorded but do not affect translation logic |
| `recognition_confident = False` | Cells processed per normal flow; downstream rendering may add a visual indicator (out of scope) |
| Model unavailable at runtime | `TableStructure` not attached; `table` element treated as plain region marker; no crash (BR-71) |

### Backward-compatibility rule

A serialized IR lacking `metadata["table_structure"]` on a `table`-typed element is valid. `from_dict()` MUST NOT raise when the key is absent. All pre-p3-table-structure IR instances remain valid.

### Known consumers of TableStructure

| consumer | surface | impact |
|---|---|---|
| `app/backend/parsers/table_recognizer.py` | producer | creates `TableStructure`; attaches to parent `TranslatableElement.metadata`; lazy-loads ML model; falls back gracefully when unavailable |
| `app/backend/parsers/pdf_parser.py` | mediator | passes `table`-typed elements to `table_recognizer.py`; attaches result to element metadata |
| `app/backend/services/translation_service.py` (cell-batch path) | consumer | reads `TableStructure`; coalesces non-numeric cells into one LLM batch per table; writes `translated_content` and `translation_status` per cell |
| `tests/test_table_recognizer.py` | test consumer | asserts `TableStructure` shape, `is_numeric` classification, batch coalescing, numeric passthrough, degenerate-table handling |

---

## Quality Evaluation (QE) Score Representation

**Added in p2-comet-qe.**

QE scores are produced post-translation by the `quality_evaluator.py` service and attached to the job record in the in-memory job store. They are read-only via `GET /api/jobs/{id}/quality`. Scores are not serialized as part of `TranslatableDocument.to_dict()` and are not part of the IR wire schema.

### BlockQualityScore — data shape

| field | type | nullable | default | notes |
|---|---|---:|---|---|
| block_id | string | no | — | For PDF-IR path: the `element_id` of the scored `TranslatableElement` (stable, globally unique within the document). For non-IR formats (DOCX, PPTX, XLSX) and PDF-PyPDF2-fallback: a synthetic positional id `"{ext}:{file_stem}:{index}"` that is run-stable but not durable across re-submissions (see BR-58). Consumers MUST NOT rely on `block_id` stability across re-submissions for non-IR formats. |
| score | number | no | — | COMET/xCOMET model output; float; range and interpretation are model-dependent (see BR-54). The model field identifies which scale applies. |
| model | string | no | — | Full model name/version string used to produce this score (e.g. `Unbabel/wmt22-cometkiwi-da`). Consumers must not hard-code interpretation without checking this field. |

### JobQualityRecord — in-memory store shape

| field | type | nullable | notes |
|---|---|---:|---|
| job_id | string | no | matches the parent job |
| scores | BlockQualityScore[] | no | one entry per `TranslatableElement` with `should_translate=True`; empty list when QE is disabled or failed |
| qe_status | enum(available, pending, disabled, unavailable) | no | mirrors the `status` field in the HTTP response (see api-contract.md `JobQualityResponse`) |
| model | string | yes | model name; null when `qe_status != available` |

### Nullability and invalid-data rules

| condition | expected behavior |
|---|---|
| `QE_ENABLED=false` | No `BlockQualityScore` records are produced; `JobQualityRecord.qe_status = "disabled"`; endpoint returns HTTP 200 with `status: "disabled"` |
| QE model unavailable (load failure) | `JobQualityRecord.qe_status = "unavailable"`; endpoint returns HTTP 200 with `status: "unavailable"`; scores array is empty |
| QE scoring raises exception during post-translation step | Exception is caught; job not failed; `qe_status = "unavailable"` recorded; translation result delivered normally (BR-56) |
| Job not yet complete | `JobQualityRecord` not yet attached; endpoint returns HTTP 200 with `status: "pending"` |
| Unknown `job_id` | `JobQualityRecord` absent and job absent; endpoint returns HTTP 404 |
| `block_id` in scores not matching any current IR element | Consumers MUST treat this as a stale score and ignore it; the IR is authoritative; never raise on unknown `block_id` |
| Non-IR format job — `block_id` collision across files in the same job | Colliding entry overwritten (last-write wins) or omitted; `qe_status` stays `"available"`; never raises (BR-58, BR-56) |

---

## Terminology Audit Representation

**Added in p2-term-audit.**

The terminology audit result is produced post-translation by `term_audit.audit_terms()` and attached to the job record in the in-memory job store as `JobRecord.audit`. It is read-only and in-memory only — not serialized as part of `TranslatableDocument.to_dict()`, not persisted to disk, and not part of any HTTP response schema (no new endpoint). The lifecycle is identical to `JobQualityRecord` (attached at the end of `_run_job`, after QE scoring; discarded when the job is evicted from the in-memory store).

### TerminologyAuditResult — in-memory data shape

| field | type | nullable | default | notes |
|---|---|---:|---|---|
| terminology_hit_rate | float | no | — | `matched_approved / total_approved`; `1.0` when `total_approved == 0` (vacuously satisfied, per BR-59). Range: [0.0, 1.0]. |
| unapplied_terms | list[str] | no | [] | `source_text` key of each approved term whose `target_text` was not found in any translated block. Populated by the matcher (BR-60). Empty list when all approved terms are matched or `total_approved == 0`. |
| rejected_injections | list[str] | no | [] | `target_text` values of rejected terms (status=`rejected`) that were found in the translated output. Detected using whole-token boundary matching to avoid substring false-positives from overlapping approved terms. Empty list when no rejected terms leak into output. |
| total_approved | int | no | — | Count of approved terms in scope, filtered by `(target_lang, domain)` matching the job. Matches the denominator of `terminology_hit_rate`. |
| matched_approved | int | no | — | Count of approved terms whose `target_text` was found (case-insensitive exact substring) in at least one translated block. Matches the numerator of `terminology_hit_rate`. |

### JobRecord.audit — optional field

`JobRecord.audit: Optional[TerminologyAuditResult]`

| condition | value |
|---|---|
| Audit has not yet run (job in progress) | `None` |
| Audit ran successfully | `TerminologyAuditResult` instance |
| Audit raised an exception (BR-61) | `None` |
| Job was submitted before p2-term-audit | `None` (backward-compatible default) |

This field is additive and optional. It is parallel to `JobRecord.quality` (the `JobQualityRecord` field added in p2-comet-qe). No existing field on `JobRecord` is modified or removed. Consumers that do not yet read `audit` are unaffected.

### Nullability and invalid-data rules

| condition | expected behavior |
|---|---|
| `total_approved == 0` | `terminology_hit_rate = 1.0`; `unapplied_terms = []`; `matched_approved = 0`; result is a valid `TerminologyAuditResult`, not `None` |
| `audit_terms()` raises any exception | `JobRecord.audit = None`; job not failed; translation delivered; WARNING logged (BR-61) |
| Job pre-dates p2-term-audit | `JobRecord.audit` absent or `None`; consumers must handle `None` gracefully |
| Rejected term `target_text` is a substring of an approved term's `target_text` | Whole-token boundary check governs; bare substring match is forbidden for `rejected_injections` to avoid false positives |
| Multiple blocks contain the same approved term | Term counted as matched once (idempotent); `matched_approved` does not double-count |

### Known consumers of TerminologyAuditResult

| consumer | surface | impact |
|---|---|---|
| `app/backend/services/job_manager.py` | producer | sets `JobRecord.audit` after `_run_job` post-translate step |
| `app/backend/services/term_audit.py` | producer (new, p2-term-audit) | computes `TerminologyAuditResult`; calls `term_db.get_approved()` and the new `term_db.get_rejected()` read query |
| `tests/test_term_audit.py` | test consumer (new, p2-term-audit) | asserts result shape conforms to this section |

---

## Term DB — Embedding Similarity Query

**Added in term-extraction-db-first.**

`get_similar_terms_by_embedding()` is an in-process query method on `term_db.py`. It is not serialized, not exposed over HTTP, and not part of any IR wire schema.

### Function contract

`term_db.get_similar_terms_by_embedding(segment_text: str, target_lang: str, domain: Optional[str] = None, similarity_threshold: float = 0.75) -> list[tuple[Term, float]]`

| aspect | contract |
|---|---|
| Input: segment_text | Single source-language text segment. Length bounded by the PANJIT embedding model context window (32K tokens for Qwen3-Embedding-8B). |
| Input: target_lang | Target language code; used to filter candidate DB terms by language. |
| Input: domain | Optional; when supplied, candidate terms are further filtered to this domain. When None, all domains are searched. |
| Input: similarity_threshold | Cosine similarity floor (default: 0.75); only (Term, score) pairs with score >= threshold are returned. |
| Output | Ordered list of (Term, float) tuples, descending by similarity score. Empty list when no terms meet the threshold, when term_db is empty, or when embedding fails. |
| Cosine computation | Computed on-the-fly in Python (NumPy). Embeddings are NOT persisted. No vector-DB package (pgvector, chromadb, faiss) is introduced. |
| Embedding call | Targets `POST {PANJIT_LLM_BASE_URL}/v1/embeddings` with model `Qwen3-Embedding-8B` and `verify_ssl=False`. |
| Failure semantics | Any exception from the embedding API is caught; returns an empty list; caller logs at WARNING and skips injection. Never raises into the translation path. |

### Nullability and invalid-data rules

| condition | expected behavior |
|---|---|
| term_db is empty for the given target_lang/domain | Returns empty list immediately; no embedding call made |
| PANJIT embedding response missing `data[].embedding` field | Caught as parse error; returns empty list; WARNING logged |
| Zero-length segment_text | Returns empty list; no embedding call made |
| All DB terms embed but none meet threshold | Returns empty list; caller proceeds to extraction path |

---

## Provider API Response Shapes

**Added in settings-page-cloud-redesign.**

### ProviderHealthItem

Returned by `GET /api/providers/health` as an array element.

| field | type | required | notes |
|---|---|---|---|
| provider | string | yes | Provider identifier, e.g. `"panjit"`, `"deepseek"` |
| status | string | yes | One of `"online"`, `"offline"`, `"not_configured"` |
| latency_ms | number | no | Round-trip latency in milliseconds; omitted when `status = "not_configured"` |

### ProviderModelEntry

Returned by `GET /api/providers/models` as an array element.

| field | type | required | notes |
|---|---|---|---|
| provider | string | yes | Provider identifier |
| translate_model | string | no | Default translation model name from providers.yml |
| long_doc_model | string | no | Long-document model name from providers.yml; omitted if not configured |

### TestTranslationRequest

Request body for `POST /api/providers/test-translation`.

| field | type | required | notes |
|---|---|---|---|
| text | string | yes | Source sentence to translate (single sentence; cost-bounded) |
| src_lang | string | yes | BCP-47 source language code, e.g. `"zh-TW"` |
| targets | string[] | yes | Target language codes, e.g. `["en", "ja"]` |
| profile | string | no | Translation profile name; omitted = default profile |
| models | string[] | no | Specific model IDs to test; omitted = test all enabled providers |
| deepseek_api_key | string | no | User-supplied DeepSeek API key; NOT read from backend .env; absent → DeepSeek slot skipped |

### TestTranslationResult

Single element in the response array of `POST /api/providers/test-translation`.

| field | type | required | notes |
|---|---|---|---|
| model_id | string | yes | Model identifier, e.g. `"gemma4:latest"` |
| provider | string | yes | Provider name, e.g. `"panjit"` |
| duration_ms | number | yes | Wall-clock time for this model's translation |
| translation | string | no | Translated text; omitted when `error` is present |
| comet_score | number | no | COMET/xCOMET quality score (0–1); omitted when `QE_ENABLED=false` |
| error | string | no | Error message; present when this model's call failed; does NOT affect sibling results |

### Invalid-data rules (provider endpoints)

| condition | expected behavior |
|---|---|
| `deepseek_api_key` absent/empty in test-translation request | DeepSeek slot returns `{model_id, provider, duration_ms: 0, error: "DeepSeek API key not provided"}` |
| DeepSeek API returns 401 | DeepSeek slot returns `{..., error: "DeepSeek authentication failed"}` |
| Provider timeout | That provider's slot returns `{..., error: "Provider timeout"}` |
| All model slots fail | Response is `TestTranslationResult[]` where every element has `error`; HTTP 200 still returned |
| `text` field empty or missing | HTTP 422 Pydantic validation error |
