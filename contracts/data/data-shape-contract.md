---
contract: data
summary: Data schema, invalid-data handling, and row-level compatibility rules.
owner: application-team
surface: data
schema-version: 0.7.0
last-changed: 2026-06-19
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
| `table` | region-level | Entire table region (container; may enclose `table_cell` elements) | added p2-ir-document-model |
| `figure` | region-level | Figure or image region | added p2-ir-document-model |
| `formula` | region-level | Mathematical formula region | added p2-ir-document-model |
| `list` | region-level | Entire list region (container; may enclose `list_item` elements) | added p2-ir-document-model |

All pre-existing values remain valid and their serialized string forms are unchanged. New region-level values are additive non-breaking: existing consumers that do not recognize them must not raise on deserialization; they may skip or passthrough such elements.

### ElementType wire-value convention

All `ElementType` members MUST use lowercase Python string values as their wire form (e.g. `TABLE = "table"`, `LIST = "list"`). This convention is frozen by ADR 0002 (`docs/adr/0002-ir-elementtype-serialized-values.md`) to guarantee round-trip compatibility across serialized IR snapshots. Any future member whose `value` differs in case is a breaking change and requires a major version bump on this contract.

### ElementType producer inventory

| producer | file path | added in | notes |
|---|---|---|---|
| PDF parser | `app/backend/parsers/pdf_parser.py` | p2-ir-document-model | extracts structural element types from PyMuPDF text/table detection; delegates reading-order to layout detector on native-PDF path |
| Layout detector | `app/backend/parsers/layout_detector.py` | p2-layout-detection | maps Docling heron-101 DocLayNet labels to `ElementType` wire values; sets `reading_order`; rasterised page image never leaves the process |
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

A document serialized by `TranslatableDocument.to_dict()` then deserialized by `TranslatableDocument.from_dict()` must produce an equivalent IR preserving all of the following fields without loss or mutation: `bbox` (all four float coordinates), `style` / font metadata (all six fields), `element_type`, `reading_order`, `render_truncated`, `element_id`, `content`, `page_num`, `should_translate`, `translated_content`, `metadata`. Floating-point bbox coordinates must round-trip without rounding or truncation.

### Backward-compatibility rule

Old-format means a document dict produced by the pre-change `TranslatableElement.to_dict()` (lacking the `reading_order` key). `TranslatableElement.from_dict()` must deserialize old-format dicts without raising; `reading_order` defaults to `None` when the key is absent. Old-format documents deserialized under the new code are valid IR instances and may be passed to any renderer.

`render_truncated` follows the same rule: when the key is absent in an old-format dict, `from_dict()` defaults it to `False`. A serialized IR produced before p2-text-expansion deserializes unchanged and is a valid IR instance.

### `to_dict` compatibility rule

All pre-existing keys (`element_id`, `content`, `element_type`, `page_num`, `bbox`, `style`, `should_translate`, `translated_content`, `metadata`) must remain present in `to_dict` output with the same types and semantics. `reading_order` is added as a new key (integer or `None`). `render_truncated` is added as a new key (boolean, default `False`). No existing key may be renamed, removed, or have its type narrowed.

### Known consumers of the IR

| consumer | surface | impact |
|---|---|---|
| `app/backend/parsers/pdf_parser.py` | producer | extracts text elements; delegates reading-order assignment to `layout_detector.py` on native-PDF text-layer path; retains `round(y0,10pt)` heuristic as per-page fallback (BR-33) |
| `app/backend/parsers/layout_detector.py` | producer (p2-layout-detection) | consumes rasterised page images from PyMuPDF in-process; writes `element_type` (from D-4 label mapping) and `reading_order` onto `TranslatableElement`; never changes wire schema |
| `app/backend/parsers/docx_parser.py` | producer | must populate `reading_order` from element extraction order |
| `app/backend/parsers/pptx_parser.py` | producer | must populate `reading_order` from element extraction order |
| `app/backend/renderers/base.py` | consumer | may consume `reading_order`; must not raise when `None` |
| `app/backend/renderers/coordinate_renderer.py` | consumer | same as base |
| `app/backend/renderers/pdf_generator.py` | consumer — ReportLab fallback renderer (p2-renderer-convergence) | ReportLab fallback; consumes IR via shared bbox-reflow component; invoked only when fitz primary path fails per BR-34 |
| `app/backend/renderers/text_region_renderer.py` | consumer | same as base |
| `app/backend/renderers/inline_renderer.py` | consumer | same as base |
| `app/backend/renderers/fitz_renderer.py` | consumer — fitz primary renderer (p2-renderer-convergence) | fitz primary PDF renderer; consumes IR via shared bbox-reflow component; see BR-34. Writes `render_truncated=True` on elements where cascade step (e) fires (BR-38). |
| `app/backend/processors/orchestrator.py` | processor | no IR schema change required; reads elements after parsing |
| `app/backend/services/doc_chunker.py` | consumer + transformer (p2-long-doc-chunking) | reads elements to build ChunkRecords; does not mutate element fields other than triggering per-chunk translation |
| `app/backend/services/translation_service.py` (Doc2Doc path) | consumer + transformer (p2-long-doc-chunking) | receives full TranslatableDocument; invokes chunker; merges translated_content back into elements; returns the same document instance |
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
