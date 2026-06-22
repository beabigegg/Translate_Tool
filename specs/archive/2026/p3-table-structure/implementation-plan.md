---
change-id: p3-table-structure
schema-version: 0.1.0
last-changed: 2026-06-22
---

# Implementation Plan: p3-table-structure

## Objective
Ship an optional ML table-structure recognizer for the PDF parse path that decomposes `table`-typed regions into a row/col/cell `TableStructure` (attached to `TranslatableElement.metadata["table_structure"]`), plus a cell-batch translation seam that translates each table's text-bearing cells in exactly one coalesced LLM call, passes numeric/empty cells through unchanged, and reconstructs the parent element's `translated_content`. The recognizer follows the ADR-0003 lazy-load + fail-soft pattern. All work is config-gated (`TABLE_RECOGNITION_ENABLED`, default off) and PDF-only. Authoritative decisions: `design.md` D1–D6; contracts: `contracts/data/data-shape-contract.md §Table/Cell IR`, `contracts/business/business-rules.md BR-68..BR-71 / Table T`.

## Execution Scope

### In Scope
- New module `app/backend/parsers/table_recognizer.py` (lazy-load ONNX session, fail-soft, region-crop inference) producing `TableStructure`.
- `TableCell` / `TableStructure` dataclasses + `to_dict`/`from_dict` in `app/backend/models/translatable_document.py`, carried under `metadata["table_structure"]` (no new top-level field).
- `is_numeric_cell()` predicate added to existing `app/backend/utils/text_utils.py`.
- `translate_table_cells()` cell-batch seam (new method) in `app/backend/services/translation_service.py`.
- PDF parser hook in `app/backend/parsers/pdf_parser.py` to hand `table` regions to the recognizer and attach results.
- PDF processor routing in `app/backend/processors/pdf_processor.py`: structured-table elements go through the cell-batch seam before/instead of the flatten batch (BR-70).
- Chunker atomicity guard in `app/backend/services/doc_chunker.py` (D5).
- Config flags in `app/backend/config.py`: `TABLE_RECOGNITION_ENABLED`, `TABLE_RECOGNITION_MODEL_PATH`.
- New test file `tests/test_table_recognizer.py` (all classes/tests in `test-plan.md`), written RED-first.

### Out of Scope
- DOCX/PPTX native table translation (CER-001 deferred; `pptx_parser.py`/`docx_parser.py` NOT touched).
- Any new/changed API endpoint or job-API schema change.
- UI / rendering of recognized cells; PDF table re-rendering (design.md Open Risks — renderer follow-up only).
- Per-cell QE scoring (parent `table` element stays the QE surface — D4).
- New top-level `TranslatableElement.table_structure` field (D2 rejected).
- Adding packages to `requirements.txt` (see Constraints).

## Required Changes
| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | config | Add `TABLE_RECOGNITION_ENABLED` (default false) + `TABLE_RECOGNITION_MODEL_PATH` env-backed flags, mirroring `LAYOUT_DETECTOR_*` at config.py:151-155 | backend-engineer |
| IP-2 | IR model | Add `TableCell`/`TableStructure` dataclasses + `to_dict`/`from_dict`; serialize/deserialize under `metadata["table_structure"]`; `from_dict` must not raise when key absent | backend-engineer |
| IP-3 | predicate | Add `is_numeric_cell()` to `text_utils.py` per BR-68 (digits, whitespace, separators `. , / - %`); empty string is NOT numeric | backend-engineer |
| IP-4 | recognizer | New `table_recognizer.py`: `TableRecognizer` class mirroring `LayoutDetector` (lazy `_load_session`, `_session_load_failed` latch, 3-tier weight resolution, CPU-only ONNX default, fail-soft per BR-71); input is rasterized table-region crop (D1) | backend-engineer |
| IP-5 | pdf parser | Hand `table`-typed elements to recognizer after detection; attach `TableStructure` to `metadata["table_structure"]`; fail-soft (no attachment) when disabled/unavailable | backend-engineer |
| IP-6 | cell-batch seam | New `translation_service.translate_table_cells(...)`: coalesce non-numeric non-empty cells into one `translate_blocks_batch` call; numeric→passthrough, empty→skipped, batch failure→BR-25 placeholder/failed; set parent `translated_content` per D3 | backend-engineer |
| IP-7 | pdf processor | Route `should_translate` `table` elements with `metadata["table_structure"]` through the cell-batch seam before the flatten batch; exclude them from the flatten batch (BR-70) | backend-engineer |
| IP-8 | chunker | Guard so a structured `table` element is atomic (never a mid-element split target); BR-48 own-chunk path when oversized (D5) | backend-engineer |
| IP-9 | tests | Create `tests/test_table_recognizer.py` with all `test-plan.md` classes, RED-first; collection-time module-reference `patch.object` for LLM client | backend-engineer |

## Source Artifact Pointers
| source | relevant pointer | used for |
|---|---|---|
| design.md | D1 (ML runtime/failure), D2 (attachment point), D3 (reconstruction format, NORMATIVE), D4 (QE scope), D5 (chunker atomicity), D6 (batch seam placement) | implementation constraints |
| contracts/data/data-shape-contract.md | §Table/Cell IR — `TableCell` / `TableStructure` field tables, Attachment to the IR, Cell-batch IR-consumption contract, Degenerate table handling, Backward-compatibility rule | IR shape + serialization + cell-batch obligations |
| contracts/business/business-rules.md | BR-68 (numeric passthrough), BR-69 (same-table batching), BR-70 (cell-granularity / no flatten), BR-71 (fail-soft), Table T | business logic |
| test-plan.md | AC→test mapping, Test Names, Anti-Tautology Rules (AC-2/AC-3/AC-4), Test Execution Ladder | tests to write/run |
| ci-gates.md | Required Gates table (`targeted-table-recognizer`, `full-test-suite`, `layout-detector-dependency`) | verification commands |
| app/backend/parsers/layout_detector.py:115-226 | `__init__`, `_resolve_model_path`, `_resolve_hf_path`, `_load_session` | exact lazy-load / latch / 3-tier / ONNX pattern to copy |
| app/backend/parsers/pdf_parser.py:365-451 | `_run_layout_detector` per-page pixmap rasterization + fail-soft `detect()` call | where/how to crop the table region and invoke recognizer |
| app/backend/processors/pdf_processor.py:264-341 | translatable collection + `translate_blocks_batch` + per-element output loop | flatten-batch path the cell-batch seam diverts from |
| app/backend/utils/translation_helpers.py:365-377 | `translate_blocks_batch(texts, tgt, src_lang, client, ...)` signature | reuse as the single per-table LLM batch call |

## File-Level Plan
| path or glob | action | notes |
|---|---|---|
| `app/backend/config.py` | edit | Add `TABLE_RECOGNITION_ENABLED` (default `false`) and `TABLE_RECOGNITION_MODEL_PATH` after the `LAYOUT_DETECTOR_*` block (~line 155), same `os.environ.get(...).lower() in (...)` idiom |
| `app/backend/models/translatable_document.py` | edit | Add `TableCell` and `TableStructure` `@dataclass` (fields per data-shape §Table/Cell IR) with `to_dict`/`from_dict`. Serialize into the `metadata` dict under `"table_structure"`; `TranslatableElement.from_dict` already passes `metadata` through — ensure `table_structure` survives round-trip without loss and absence does not raise |
| `app/backend/utils/text_utils.py` | edit | Add `is_numeric_cell(content: str) -> bool` per BR-68; empty/whitespace-only is NOT numeric (see data-shape: empty cell → skipped, not passthrough) |
| `app/backend/parsers/table_recognizer.py` | create | `TableRecognizer` class mirroring `LayoutDetector` (lazy session, `_session_load_failed` latch, 3-tier path: explicit/env → HF cache → HF download, CPU-only ONNX, opt-in CUDA). Input = PyMuPDF pixmap crop of the `table` bbox (D1). Returns `Optional[TableStructure]`; attaches nothing and logs WARNING once on failure (BR-71). No network/translation-client import |
| `app/backend/parsers/__init__.py` | edit (only if imported) | Export `TableRecognizer` only if another module imports it via the package; otherwise leave untouched (verify import sites first — CLAUDE.md orphaned-import learning) |
| `app/backend/parsers/pdf_parser.py` | edit | After layout detection, for each `table`-typed element (when `TABLE_RECOGNITION_ENABLED`), crop the page pixmap to the element bbox and call the recognizer; attach result to `metadata["table_structure"]`. Reuse the rasterization approach from `_run_layout_detector` (pixmap created/consumed/discarded in-module). Fail-soft: no structure attached on any error |
| `app/backend/services/translation_service.py` | edit | Add `translate_table_cells(element, targets, src_lang, client, ...)`. Coalesce cells where `is_numeric=False` and `content != ""` into one `translate_blocks_batch` call; set numeric→(`translated_content=content`, status `passthrough`), empty→(`""`, `skipped`), batched→`translated`, batch error→BR-25 placeholder + `failed`. Set parent `translated_content` per D3 (tab within row `\t`, newline between rows `\n`, row-major; merged-cell text at origin, spanned positions empty) |
| `app/backend/processors/pdf_processor.py` | edit | Before the flatten `translate_blocks_batch` loop, partition out `should_translate` `table` elements carrying `metadata["table_structure"]`; run them through `translate_table_cells`; exclude them from `unique_texts`/flatten batch (BR-70). Wire for each target language |
| `app/backend/services/doc_chunker.py` | edit | Add guard: a `table` element with `metadata["table_structure"]` is atomic — never a mid-element split target; trigger BR-48 own-chunk path when oversized (D5) |
| `tests/test_table_recognizer.py` | create | All classes/tests in `test-plan.md` §Test Names. RED before `table_recognizer.py` implemented. Import the module under test at module/collection time and use `patch.object(<module_ref>, ...)` for the LLM client — never string-based `patch("...")` (CLAUDE.md mock-target learning) |

## Contract Updates
- API: none (no new/changed endpoint; runs through existing job pipeline).
- CSS/UI: none.
- Env: none (model auto-downloads/lazy-loads per ADR-0003; `TABLE_RECOGNITION_*` are non-secret feature flags, no `.env` key required).
- Data shape: already specified in `contracts/data/data-shape-contract.md §Table/Cell IR` — implement to that contract; do NOT modify the contract.
- Business logic: already specified in `contracts/business/business-rules.md BR-68..BR-71 / Table T` — implement to that contract; do NOT modify.
- CI/CD: workflow edits already applied per `ci-gates.md §Workflow Changes Applied`; backend-engineer does not modify `.github/workflows/`.

## Test Execution Plan
| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 (IR shape) | tests/test_table_recognizer.py::TestTableStructureIRShape | TableStructure attached in metadata; plain region when absent |
| AC-1 (round-trip) | tests/test_table_recognizer.py::TestTableStructureRoundTrip | to_dict/from_dict lossless; old-format IR (no key) does not raise |
| AC-2 (cell granularity) | tests/test_table_recognizer.py::TestCellGranularityTranslation | parent translated_content built from cell results, not a flattened single call; placeholder on batch failure |
| AC-3 (numeric predicate) | tests/test_table_recognizer.py::TestNumericPassthrough | is_numeric_cell boundaries per BR-68; empty cell not numeric |
| AC-3 (numeric wiring) | tests/test_table_recognizer.py::TestNumericPassthroughWiring | numeric cell NOT sent to LLM AND translated_content == content exactly |
| AC-4 (batching) | tests/test_table_recognizer.py::TestSameTableCellBatching | one batch call per table; payload contains text cells, excludes numeric; separate tables → separate batches |
| AC-5 (model unavailable) | tests/test_table_recognizer.py::TestModelUnavailableFallback | WARNING logged; no TableStructure attached; no crash |
| AC-6 (degenerate) | tests/test_table_recognizer.py::TestDegenerateTableHandling | all-numeric / all-empty → no LLM call; merged cell = single TableCell |

Ladder phases (run via `cdd-kit test run`; gate validates `test-evidence.yml`). Floor: collect → targeted → changed-area; add contract (IR/business contracts affected) and full (final/CI). See `test-plan.md §Test Execution Ladder` and `references/sdd-tdd-policy.md`.

- collect: `cdd-kit test run --phase collect`
- targeted: `cdd-kit test run --phase targeted`
- changed-area: `cdd-kit test run --phase changed-area`
- contract: `cdd-kit validate --contracts` (data-shape + business-rules affected)
- full: `cdd-kit test run --phase full`

CI targeted gate (must pass before the full suite, per `ci-gates.md`): `pytest tests/test_table_recognizer.py -x -q --tb=short`.

## Constraints and Non-Goals
- **PDF-only**: table recognition applies only to the PDF parse path. DOCX/PPTX out of scope (CER-001 pending).
- **No new API endpoints** and no job-API schema change; the cell-batch seam reuses the existing `translate_blocks_batch` + model_router fallback chain.
- **`TABLE_RECOGNITION_ENABLED` defaults to `false`** until weights are validated; when off (or model unavailable), every `table` region falls back to the existing flatten path with no crash (BR-71). Rollback is config-only.
- **No new packages**: TATR/TableFormer uses `onnxruntime` (already in `requirements.txt`) plus `transformers` + `torch` (already present). The backend-engineer MUST confirm `onnxruntime` is already in `requirements.txt` before writing code and add nothing. The `layout-detector-dependency` gate fails on `ultralytics`/`onnxruntime-gpu`.
- Do not modify `contracts/` or `.github/workflows/` — those updates are owned by contract-reviewer and ci-cd-gatekeeper and are already applied.
- Do not write `design.md`.

## Handoff Constraints
- TDD: write each AC's failing tests FIRST, confirm RED, then implement. All new tests must be RED before `table_recognizer.py` exists.
- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into code or new docs; follow the source pointers above.
- Follow `layout_detector.py` (lines 115-226) exactly for lazy-load, `_session_load_failed` latch, ONNX session creation, and 3-tier weight resolution.
- Cell-batch tests MUST use `patch.object` on a collection-time module-level reference for the LLM client (per CLAUDE.md learnings) — never string-based `patch("...")`. `test_table_recognizer.py` must import the module under test at collection time so `patch.object` targets the live reference.
- Reconstruction format (D3) is NORMATIVE: tab within row, newline between rows, row-major; merged-cell text at origin, spanned positions empty.
- Keep implementation within the File-Level Plan; before adding any import of the new module, grep consumer call sites (avoid orphaned shared module — CLAUDE.md learning). Anything beyond the plan requires an approved Context Expansion Request.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.

## Known Risks
- D3 tab/newline reconstruction is lossy for cells containing literal tabs/newlines; acceptable because `TableStructure.cells` stays authoritative (design.md Open Risks). Flag for renderer-side follow-up if PDF table re-rendering is added later.
- Region-crop inference assumes the `table` bbox from PyMuPDF/layout detector is reliable; a wrong bbox degrades recognition quality but not correctness (fail-soft applies).
- `.cdd/code-map.yml` does not yet list `table_recognizer.py` (new file); the map is stale until regenerated after implementation — not a blocker for this plan.
