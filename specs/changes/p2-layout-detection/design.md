# Design: p2-layout-detection

## Architecture Summary
A new `app/backend/parsers/layout_detector.py` module wraps the local Docling heron-101 ONNX model (`docling-project/docling-layout-heron-onnx`) and runs per-page region detection inside the existing `PyMuPDFParser.parse()` flow. It replaces the `round(y0,10pt)` bucket heuristic (`_sort_by_reading_order`) with region-aware reading-order assignment and writes typed regions into the existing IR (`ElementType` + `reading_order` on `TranslatableElement`) — no parallel data structure. Inference is forced local: the page is rasterised in-process via PyMuPDF and the image array never leaves the machine. The detector is an additive, internally-encapsulated stage: it does not change the IR wire schema (already provides the needed `ElementType`/`reading_order` fields from `p2-ir-document-model`), no public API, no persistence, no network egress.

## Affected Components
| component | file path | nature of change |
|---|---|---|
| layout detector (new) | `app/backend/parsers/layout_detector.py` | new module: page-image → ONNX → typed region boxes → reading-order assignment |
| PDF parser | `app/backend/parsers/pdf_parser.py` | inject detector after text extraction; replace `_sort_by_reading_order` heuristic on native-PDF path; map text lines into detected regions |
| config | `app/backend/config.py` | add `LAYOUT_DETECTOR_MODEL_PATH`, `LAYOUT_DETECTOR_ENABLED` reads; existing `PDF_PARSER_ENGINE` block is the home |
| IR model | `app/backend/models/translatable_document.py` | no schema change — consume existing `ElementType`/`reading_order` (verify only) |
| dependency manifest | `app/backend/requirements.txt`, `environment.yml` | add `onnxruntime` (CPU), `huggingface_hub`; no `ultralytics` |
| env contract | `contracts/env/env-contract.md` (+ `.env.example.template`, `env.schema.json`) | declare `LAYOUT_DETECTOR_MODEL_PATH` (optional) |
| data-shape contract | `contracts/data/data-shape-contract.md` | confirm detector as IR producer; label→`ElementType` mapping note |
| business rules | `contracts/business/business-rules.md` | new BR: local-inference privacy boundary + inference-failure degradation rule |

## Key Decisions

### D-1: Runtime (CPU vs GPU)
**Decision**: Default to CPU-only `onnxruntime` as the declared dependency. GPU is opt-in only (operator installs `onnxruntime-gpu` out-of-band; the detector selects the CUDA execution provider when present and silently uses `CPUExecutionProvider` otherwise).
**Rationale**: heron-101 is a single forward pass per page on a small layout model — CPU latency is acceptable for a batch translation tool and the local Ollama GPU is already contended for translation. CPU-only keeps the Docker image portable, the CI/CD/offline environment reproducible, and user setup zero-config. Provider auto-selection means a GPU box benefits without a code or dependency change.
**Rejected alternative**: Declaring `onnxruntime-gpu` as the default dependency — rejected: pulls a CUDA toolchain into every image, breaks CPU-only CI runners and air-gapped installs, and competes with Ollama for VRAM. Recorded in ADR 0003.

### D-2: Inference Failure Strategy
**Decision**: Fail-soft with a logged warning. On any inference failure (model file absent, ONNX load error, OOM, corrupt/unrasterisable page) the detector falls back to the legacy `round(y0,10pt)` reading-order heuristic for the affected page and the job continues. Failures are logged at WARNING (page number + reason); no page image or content is logged.
**Rationale**: The parse path is the only route to a translated document; a hard error would convert a layout-quality regression into total job failure. `pdf_processor.py` already establishes a fail-soft parsing contract (PyMuPDF→PyPDF2 on exception). The heuristic is a strictly-correct (if lower-quality) ordering, so degradation is graceful and bounded per-page, not silent data loss. A model fully absent at startup is surfaced once as a WARNING so operators notice without the job dying.
**Rejected alternative**: (b) Raise a controlled error and fail the job — rejected: makes a missing/optional model a hard dependency, turns transient OOM into job loss, and contradicts the existing parser fallback contract. Recorded in ADR 0003. (Mitigation: detector availability is a candidate future health surface, called out as a separate change in classification.)

### D-3: Module Boundary & Data Flow
`layout_detector.py` exposes a single stateless-after-init class (lazy model load, cached) with one method that takes a rasterised page image + the page's already-extracted `TranslatableElement` text lines and returns detected typed regions plus a reading-order index. Boundary contract:
- Input: PyMuPDF `page.get_pixmap()` raster (in-process numpy array) + page text lines. **The image array is created, consumed, and discarded inside this module; it is never serialised, persisted, or sent over any socket** — this is the privacy boundary, enforced by the module having no network/IO client imports.
- Processing: image → ONNX session → region boxes with class labels → assign each text line to the enclosing region (geometric containment, same tolerance pattern as `_is_inside`) → order regions (column-aware) then lines within region → produce 0-based `reading_order`.
- Output written to IR: each `TranslatableElement.element_type` upgraded from region label (where applicable), `reading_order` set, region provenance in `metadata` (e.g. `layout_region`, `layout_confidence`). `pdf_parser.py` keeps existing `_extract_page_elements`/`_detect_and_mark_tables`; the detector replaces only the final sort+index step.
- The detector is invoked only on the native-PDF, text-layer path. No-text-layer (scanned) PDFs are out of scope (P3-1) and keep current behaviour.

### D-4: Label Mapping (heron → ElementType)
Docling heron-101 emits DocLayNet-style class labels mapped to existing `ElementType` wire values (all lowercase per ADR 0002 — no new enum members):

| heron label | ElementType | note |
|---|---|---|
| Text / Paragraph | `text` | body text |
| Title / Section-header | `title` | |
| Page-header | `header` | |
| Page-footer | `footer` | |
| Table | `table` | region container; enclosed lines stay `table_cell` per existing table marking |
| Picture / Figure | `figure` | excluded from translation (future); marked region only |
| Formula | `formula` | pass-through target (future); marked region only |
| List-item | `list` / `list_item` | region → `list`; enclosed lines `list_item` |
| Caption | `caption` | |
| Footnote | `footnote` | |

Unknown/unmapped heron labels default to `text` (never raise — consistent with additive-non-breaking IR rule). The mapping table is the single source of truth and lives in the detector module as a constant.

### D-5: Offline Bundle / Weight Location
Three-tier resolution, first hit wins: (1) `LAYOUT_DETECTOR_MODEL_PATH` env var → explicit local path (Docker-preloaded weights, air-gapped); (2) local HuggingFace cache if already downloaded; (3) HuggingFace auto-download fallback (only network touch in the whole feature, and only for weights — never page data). Per AC-5 the env var is optional and unset defaults to tier 2/3. For offline Docker the image preloads weights and sets the env var so tier 1 always wins and no network is required at runtime. License is Apache-2.0 (heron-101 + onnxruntime); `ultralytics` (AGPL risk) is explicitly excluded.

## Migration / Rollback Strategy
Forward: additive only — no IR wire-schema change (fields exist from `p2-ir-document-model`), no DB migration, no API change. Detector is gated by `LAYOUT_DETECTOR_ENABLED` (default on) so it can be disabled via config without code change. Golden-sample dual-run (old heuristic vs new detector) gates the reading-order quality target (>95% multi-column) before enabling by default.
Rollback: set `LAYOUT_DETECTOR_ENABLED=0` (or revert the parser injection) to restore the `round(y0,10pt)` path; IR produced under either path is wire-identical and round-trips, so previously-produced IR and any persisted documents remain valid. Removing the dependency requires no data migration.

## Open Risks
- heron-101 DocLayNet mAP is 78.0% (vs DocLayout-YOLO 79.7%); the >95% reading-order target depends on column-ordering logic on top of detection, not raw mAP — must be validated by the golden dual-run, not assumed.
- CPU inference latency per page is unmeasured here; if it dominates job time on large PDFs, batching or a page cap may be needed (follow-up, not blocking).
- Text-line→region assignment for lines spanning/straddling region boundaries needs a defined tie-break (nearest-center vs largest-overlap); left to implementation but must be deterministic for golden stability.
- `.cdd/code-map.yml` was not consulted (not required for this scope); affected-component ranges were grounded by direct reads of the allowed paths.
