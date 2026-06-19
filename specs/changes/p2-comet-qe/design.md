# Design: p2-comet-qe

## Summary
Adds an opt-in neural quality-evaluation (QE) step that scores each translated
block with a reference-free COMET/xCOMET model (default `Unbabel/wmt22-cometkiwi-da`).
Scoring runs synchronously as a post-translation step inside the existing job
worker thread, immediately after a job reaches `completed`. Scores are held in a
new in-process `JobQualityRecord` in the job store (never serialized into the IR)
and exposed read-only via `GET /jobs/{id}/quality`. A new in-process service
module `quality_evaluator.py` owns the model lifecycle and inference. The whole
subsystem is gated by `QE_ENABLED` (default `false`); when disabled, no model is
loaded and the endpoint returns `status: "disabled"`. QE failure is always
caught and degrades to `qe_status: "unavailable"` — it can never fail or block a
translation job (BR-56).

## Affected Components
| component | file path(s) | nature of change |
|---|---|---|
| QE service (new) | `app/backend/services/quality_evaluator.py` | new module: lazy model load, reference-free batch scoring, exception isolation, device fallback |
| Job worker | `app/backend/services/job_manager.py` | own per-job block accumulator; invoke QE hook before `status="completed"` (BR-55); attach `JobQualityRecord`; getter for endpoint |
| Orchestrator + processors | `app/backend/processors/orchestrator.py`, `pdf_processor.py`, `docx_processor.py`, `pptx_processor.py`, `xlsx_processor.py` | add `post_translate_hook` param; emit `(block_id, src, mt)` after translation (DR-1) |
| Translation entry | `app/backend/services/translation_service.py` | no behavior change to `translate_texts`/`translate_document` (BR-53); `translate_document` stays unwired |
| API routes/schemas | `app/backend/api/routes.py`, `schemas.py` | new `GET /jobs/{id}/quality`; `JobQualityResponse`, `BlockQualityScore` schemas |
| Config | `app/backend/config.py` | resolve `QE_ENABLED`, `QE_MODEL_NAME`, `QE_DEVICE` |
| Startup | `app/backend/main.py` | no eager load; lifespan unchanged when QE disabled (BR-57) |
| Deps | `app/backend/requirements.txt`, `environment.yml` | add `unbabel-comet` (and transitive torch) |

## Key Decisions

**D-1: Synchronous QE inside the job worker thread, fed by a per-job block
sink threaded through the processors.** QE scoring runs in the same `_run_job`
thread that performed the translation, after the translation loop and right
before the job transitions to `completed`. `_run_job` owns a job-scoped
accumulator that the format processors append `(block_id, src, mt)` tuples to as
they translate (see DR-1 Resolution); the actual COMET inference runs once at job
end over the accumulated tuples. This satisfies BR-55 (same task context) and
keeps the change Tier 2: no new queue, executor, or worker. The score step is
wrapped so any exception/timeout records `unavailable` and never delays delivery
of already-archived translation outputs (BR-56). The QE hook lives *inside* the
processor callback boundary (not after `translate_document()`), because the
existing tmap/IR already surfaces translated block content with no IR rewrite.

**D-2: Scores stored in the existing in-memory job store as `JobQualityRecord`.**
A `JobQualityRecord` (job_id, scores[], qe_status, model) is attached to the job
record in `JobManager.jobs`. It is non-serialized and not part of the IR wire
schema (data-shape-contract §QE Score Representation). This reuses the existing
job lifecycle, TTL cleanup, and capacity eviction — no new store, no persistence,
no migration surface. `qe_status` mirrors the HTTP `status` enum exactly.

**D-3: Dedicated in-process service module `quality_evaluator.py`.** QE is an
in-process library call to `unbabel-comet`, not a separate client/service. A
distinct module isolates the heavy ML dependency behind a narrow interface
(`load_model`, `score_blocks`), gives tests a single mock seam
(`app.backend.services.quality_evaluator.load_model`), and keeps
`translation_service.py` free of model/runtime concerns. It is a pure IR
*consumer*: it reads `element_id`, `content`, `translated_content` and never
mutates the IR (data-shape-contract Known-consumers row).

**D-4: Reference-free input shape `(source=content, hypothesis=translated_content)`.**
CometKiwi-style models are reference-free for MT output, so each scored block is
`{"src": element.content, "mt": element.translated_content}`. Only blocks with
`should_translate=True` (and non-empty translated content) are scored.
`BlockQualityScore.block_id` is the PDF-IR `element_id` or, for non-IR formats, a
synthetic positional id — see DR-1 Resolution for the per-format semantic. Zero
translatable blocks yields an empty `scores` array with `qe_status="available"`.

**D-5: Lazy, cached model load on first scoring call.** The model is loaded on the
first job that needs scoring (when `QE_ENABLED=true`) and cached for the process
lifetime, not eagerly in `main.py` lifespan. This honors BR-57 (no model loaded
when disabled — the default), keeps startup latency unchanged for the common
disabled case, and bounds cold-load cost to one job. A load failure is caught and
sets `qe_status="unavailable"` (BR-56); subsequent jobs may retry the load.

## Rejected Alternatives
- **D-1 async/background worker (separate executor/queue):** would force re-
  classification to Tier 1 (per classification assumption) and add lifecycle and
  ordering complexity for no user benefit at current scale; rejected.
- **D-2 separate persistent store / serializing scores into the IR:** adds a
  persistence and migration surface and violates the decoupling guarantee that
  scores are not part of `TranslatableDocument`; rejected.
- **D-3 inline scoring in `translation_service.py`:** couples the heavy ML import
  to the hot translation path, risks BR-53 backward-compat regressions, and gives
  no clean mock seam; rejected.
- **D-4 reference-based COMET (src, mt, ref):** no human reference exists in this
  pipeline; reference-free is the only viable mode; rejected.
- **D-5 eager startup load in lifespan:** loads a multi-hundred-MB model and torch
  even when `QE_ENABLED=false` (the default), violating BR-57 and taxing every
  startup; rejected.

## DR-1 Resolution

**Chosen: post-translate observer callback (candidate (a)).** Add an optional
`post_translate_hook: Optional[Callable[[List[Tuple[str,str,str]]], None]]`
parameter to each format processor and to `process_files`, mirroring the existing
`pre_translate_hook` plumbing. `_run_job` owns a job-scoped accumulator and passes
a sink into `process_files`; each processor calls the hook once after translation
with its `(block_id, src, mt)` tuples. Rationale: zero return-type changes,
reuses an already-proven hook pattern, no IR rewrite of DOCX/PPTX/XLSX.

**Scope correction on "Option C".** Wiring `translate_document()` into the
non-PDF processors is *not* required and is explicitly avoided. The QE hook only
*observes* the translation result; DOCX/PPTX/XLSX already expose every
`(src, mt)` pair via the `tmap` keyed `(tgt, src_text) -> translated` returned by
`translate_texts`, and PDF already exposes `element_id` on its IR `translatable`
elements. Surfacing that existing data through a callback meets AC-1 without the
forbidden full-IR rewrite. `translate_document()` stays unwired by this change.

### Affected Components (DR-1)
| component | file | change nature |
|---|---|---|
| Job worker | `services/job_manager.py` | create per-job `qe_blocks` accumulator; pass a sink into `process_files`; after the group loop, hand accumulated tuples to the QE hook (D-1) |
| Orchestrator | `processors/orchestrator.py` | add `post_translate_hook` param to `process_files`; thread it into each `translate_*` call (parallel to `pre_translate_hook`) |
| PDF processor | `processors/pdf_processor.py` | after `tmap`/`translations_by_target` built, emit `(element.element_id, content, translated)` per translatable element via hook |
| DOCX processor | `processors/docx_processor.py` | after `tmap` built, emit `(block_id, src_text, tmap[(tgt,src_text)])` per uniq text |
| PPTX processor | `processors/pptx_processor.py` | same tmap-based emission as DOCX |
| XLSX processor | `processors/xlsx_processor.py` | same tmap-based emission as DOCX |
| QE service | `services/quality_evaluator.py` | unchanged interface; now scores the accumulated tuple list (no IR dependency) |

### block_id semantic per format
- **PDF (IR path):** `block_id = element.element_id` — stable IR identifier (D-3/D-4 unchanged).
- **DOCX / PPTX / XLSX (tmap path):** no IR `element_id` exists. Use a synthetic
  positional id `"{ext}:{file_stem}:{index}"` where `index` is the position of the
  source text in the processor's `uniq`/`uniq_texts` list. Positional > hash because
  it is stable within a run and human-traceable; `should_translate`-filtered so only
  translated blocks are scored. When multiple targets exist, emit one tuple per
  `(block, tgt)` using `tmap[(tgt, src_text)]` so each target's MT is scored.
- **PDF PyPDF2 fallback:** no `element_id`; use the same synthetic positional id as
  the tmap formats (page-text index).

### Multi-file / multi-group accumulation
The accumulator lives in `_run_job` (one list per job), not in `process_files`
(called once per route group). Each processor call *appends*; the list survives
across files within a group and across groups within the job. block_id includes
`file_stem` (and, for multi-group jobs, the group's target suffix is already in
the output naming) so synthetic ids do not collide across files. The accumulator
is a plain list mutated only by the single `_run_job` thread, so it is
thread-safe without a lock (one job = one worker thread; the cross-job
`JobManager.jobs` dict is untouched by this path).

### Contract deltas (note only — do NOT edit contracts here)
- **data-shape-contract.md §QE Score Representation / Known-consumers:** add a
  clarification that `BlockQualityScore.block_id` is `element_id` for PDF-IR blocks
  and a synthetic positional id (`"{ext}:{file_stem}:{index}"`) for DOCX/PPTX/XLSX
  and PDF-PyPDF2-fallback blocks; ids are run-stable, not globally durable.
- **business-rules.md:** add one BR (e.g. BR-58) stating: QE block identity is
  best-effort positional for non-IR formats; a missing/duplicate synthetic id must
  degrade to scoring-without-stable-id, never fail the job (subordinate to BR-56).
  No change needed to BR-53/55/56/57.

## Migration / Rollback
No schema or data migration: `JobQualityRecord` is in-memory only and additive;
the endpoint and env vars are purely additive. Rollback is the default state:
`QE_ENABLED=false`. With the flag off, the QE hook is skipped entirely, no model
or torch is loaded, the new endpoint returns HTTP 200 `status: "disabled"`, and
the translation pipeline is byte-for-byte unchanged (BR-53/BR-57). Disabling the
flag and restarting fully reverts behavior without code removal. Because scoring
is best-effort and isolated (BR-56), even a broken QE deployment cannot regress
translation delivery, so no emergency code rollback is required — flipping the
flag suffices.

## Open Risks
- `unbabel-comet` pulls a large `torch` dependency; image size / install time and
  dependency-security review are deferred to the dependency-security-reviewer and
  ci-cd-gatekeeper packets (not blocking this design).
- `.cdd/code-map.yml` was not consulted (MCP/code-map not used here); affected
  components were grounded directly via targeted reads of the in-scope source.
- DR-1 (resolved): per-block translated content is surfaced via a
  `post_translate_hook` from each processor into a `_run_job` accumulator — no IR
  rewrite, no return-type change. Residual: D-4's input shape is now
  `(block_id, src, mt)` tuples rather than live IR elements, so for non-PDF formats
  `block_id` is synthetic positional (see DR-1 Resolution); QE scoring quality is
  unaffected (it only reads src+mt), but block_id is run-stable, not durable.
