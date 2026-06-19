---
change-id: p2-comet-qe
schema-version: 0.1.0
last-changed: 2026-06-19
---

# Implementation Plan: p2-comet-qe

> STATUS: ready. DR-1 is RESOLVED (candidate (a), design.md §DR-1 Resolution):
> per-block translated content reaches the job worker via an optional
> `post_translate_hook` threaded through `process_files` and each format
> processor, mirroring the existing `pre_translate_hook`. No IR rewrite, no
> return-type change. Implementation agents follow the IP sequence below and
> report `blocked` rather than inferring missing scope from chat history.

## Objective
Deliver an opt-in, reference-free neural quality-evaluation (QE) step that scores
every translated block of a completed job with COMET (`Unbabel/wmt22-cometkiwi-da`
by default), holds per-block scores in an in-memory `JobQualityRecord` in the job
store, and exposes them read-only via `GET /api/jobs/{job_id}/quality`. QE is gated
by `QE_ENABLED` (default `false`), degrades safely to `unavailable`/`disabled` on
any failure, and never blocks or alters translation output (design D-1..D-5,
DR-1 Resolution; BR-54..BR-58; Table P).

## Execution Scope

### In Scope
- New module `app/backend/services/quality_evaluator.py` (D-3): lazy/cached model
  load (D-5), reference-free batch scoring (D-4), full exception isolation (BR-56),
  device fallback to CPU on invalid `QE_DEVICE`.
- `app/backend/config.py`: resolve `QE_ENABLED`, `QE_MODEL_NAME`, `QE_DEVICE`.
- `post_translate_hook` parameter threaded through `process_files`
  (`orchestrator.py`) and all five format processors, mirroring `pre_translate_hook`
  (DR-1 Resolution). Each processor emits `(block_id, src, mt)` tuples after translation.
- `app/backend/services/job_manager.py`: per-job `qe_blocks` accumulator + sink
  passed as `post_translate_hook`; QE scoring + `JobQualityRecord` attach at job
  completion; getter for the route.
- `app/backend/api/schemas.py`: `BlockQualityScore`, `JobQualityResponse`.
- `app/backend/api/routes.py`: `GET /jobs/{job_id}/quality` (router has no prefix;
  `/api` is added in `main.py`), all `status` variants + 404.
- `app/backend/requirements.txt` (+ `environment.yml`): add `unbabel-comet`,
  CPU-only (no `onnxruntime-gpu`).
- `contracts/api/openapi.yml`: regenerate after api changes.
- Tests: new `tests/test_quality_evaluation.py`; add 3 funcs to
  `tests/test_env_contract.py`; add 3 funcs to `tests/test_translation_strategy.py`.

### Out of Scope (non-goals — do not do)
- Wiring `translate_document()` into the format processors / orchestrator.
  Explicitly avoided per DR-1 Resolution §"Scope correction on Option C";
  `translate_document()` stays unwired. The QE hook only *observes* the existing
  tmap/IR translation result — no IR rewrite of DOCX/PPTX/XLSX.
- Any change to `translate_texts()` / `translate_document()` behavior (BR-53).
- Persisting scores, serializing them into the IR / `TranslatableDocument`, or
  any migration surface (D-2).
- Eager model load at startup / `main.py` lifespan changes (D-5; BR-57).
- GPU benchmarking, model-download network behavior, COMET numeric-accuracy
  validation, frontend exposure of scores (test-plan §Out of Scope).
- Editing already-written contracts (api, data-shape 0.7.0, env, business-rules
  0.11.0), `ci-gates.md`, `.env.example.template`, the gate workflow — all done.
  Only `openapi.yml` is regenerated mechanically (IP-11).

## Required Changes
| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | tests | Scaffold `tests/test_quality_evaluation.py` (all stubs, no bodies) per test-plan mapping, TDD-first. Mock seam `app.backend.services.quality_evaluator.load_model`. | backend-engineer |
| IP-2 | QE service | Create `quality_evaluator.py` per D-3/D-4/D-5: module-level `load_model(model_name, device)` (mock seam, lazy/cached, invalid device → cpu + WARNING), `score_blocks(model, blocks)` reference-free over `List[(src, mt)]`, any exception → empty list. | backend-engineer |
| IP-3 | config | Add `QE_ENABLED` (default false), `QE_MODEL_NAME` (default `Unbabel/wmt22-cometkiwi-da`), `QE_DEVICE` (default `cpu`) to `config.py`, matching env-contract defaults. | backend-engineer |
| IP-4 | processors | Thread `post_translate_hook` through `process_files` + all 5 `translate_*`; emit `(block_id, src, mt)` after translation. **Most invasive — dedicated commit after IP-2/IP-3.** | backend-engineer |
| IP-5 | job worker | Per-job `qe_blocks` accumulator; pass sink as `post_translate_hook`; score before `status="completed"`; attach `JobQualityRecord`; degrade to `unavailable` on exception (BR-56); add getter. | backend-engineer |
| IP-6 | schemas | Add `BlockQualityScore` (block_id, score, model) and `JobQualityResponse` (job_id, status enum, scores[]) to `schemas.py`, matching api-contract §BlockQualityScore / §JobQualityResponse. | backend-engineer |
| IP-7 | route | Register `GET /jobs/{job_id}/quality` in `routes.py`; mirror `job_status` 404 pattern; map disabled/pending/unavailable/available → 200, unknown job → 404. | backend-engineer |
| IP-8 | deps | Add `unbabel-comet` to `requirements.txt` (+ `environment.yml`); CPU-only pin to avoid `onnxruntime-gpu` transitive; defer exact pins to dependency-security-reviewer. | backend-engineer |
| IP-9 | tests | +3 funcs in `test_env_contract.py`, +3 funcs in `test_translation_strategy.py` per test-plan mapping (mock at quality_evaluator boundary; assert call_count). | backend-engineer |
| IP-10 | evidence | Run test ladder (collect → targeted → changed-area), record `test-evidence.yml` via `cdd-kit test run`; full suite as final smoke. | backend-engineer |
| IP-11 | openapi | Run `cdd-kit openapi export --out contracts/api/openapi.yml` after IP-6/IP-7 and commit. | backend-engineer |

## Ordering Dependencies
- **IP-1 first** (TDD): write all stubs failing before any implementation (test-plan §TDD Sequence).
- IP-2 and IP-3 are independent; land them together in an early clean commit.
- **IP-4 is the most invasive step (6 files) — land it in a DEDICATED commit after
  IP-2/IP-3 are green.** It depends on nothing but touches orchestrator + 5 processors.
- IP-5 depends on IP-4 (consumes the hook) and IP-2 (calls `score_blocks`).
- IP-6 before IP-7 (route returns the schema). IP-7 depends on IP-5 (reads the record).
- IP-11 runs LAST, after every route/schema change is final. IP-8 may land any time
  but gates `layout-detector-dependency-gate`; resolve the CPU-only pin before committing.

## Source Artifact Pointers
| source | relevant pointer | used for |
|---|---|---|
| design.md | D-1..D-5; DR-1 Resolution; §block_id semantic per format; §Multi-file/multi-group accumulation | architecture + hook design |
| business-rules.md (0.11.0) | BR-54..BR-58; Table P | QE behavior + status semantics + block-identity rule |
| data-shape-contract.md (0.7.0) | §BlockQualityScore; §JobQualityRecord; block_id semantics; Known-consumers row | store + score shapes; consumer discipline |
| api-contract.md | endpoint row (line 47); §BlockQualityScore (248); §JobQualityResponse (255-260); §Endpoint Notes (270) | endpoint + response schemas + status mapping |
| env-contract.md | QE_ENABLED / QE_MODEL_NAME / QE_DEVICE rows | config defaults |
| test-plan.md | AC→test mapping (15-36); §Mock Discipline (49-52); §TDD Sequence | tests to write/run |
| ci-gates.md | §Required Gates; §Dependency Gate Note (29-35); §OpenAPI Sync (37-42) | verification commands |

## File-Level Plan
| path or glob | action | notes |
|---|---|---|
| `tests/test_quality_evaluation.py` | create | All stubs (IP-1), no bodies; mock seam `quality_evaluator.load_model`. |
| `app/backend/services/quality_evaluator.py` | create | D-3/D-4/D-5; `load_model()`/`score_blocks()`; lazy `comet` import inside `load_model` (BR-57). |
| `app/backend/config.py` | modify | Add 3 QE constants in the flat `os.getenv` block (after ~line 261). |
| `app/backend/processors/orchestrator.py` | modify | Add `post_translate_hook` to `process_files` sig (340-363); pass into 5 dispatch calls alongside `pre_translate_hook=_phase0_hook` (docx 695, doc-branch 725, pptx 743, xlsx 756, pdf 771). |
| `app/backend/processors/pdf_processor.py` | modify | Add param to `translate_pdf` (74), `_translate_pdf_with_pymupdf` (185), `_translate_pdf_with_pypdf2` (321), `_translate_pdf_to_pdf` (418); emit per IP-4. |
| `app/backend/processors/docx_processor.py` | modify | Add param to `translate_docx` (482); emit after `tmap` built (post line 527). |
| `app/backend/processors/pptx_processor.py` | modify | Add param to `translate_pptx` (194); emit after `tmap` built (post line 271). |
| `app/backend/processors/xlsx_processor.py` | modify | Add param to `translate_xlsx_xls` (53); emit after `tmap` built (post line 145). |
| `app/backend/services/job_manager.py` | modify | `JobQualityRecord` dataclass near `JobRecord` (34); `qe_blocks` accumulator + sink + scoring + attach in `_run_job` (261-356, score before line 343); getter on `JobManager`. |
| `app/backend/api/schemas.py` | modify | Append two Pydantic models (file ends ~line 129). |
| `app/backend/api/routes.py` | modify | Add route after `job_status` (ends 241); import new schemas + `QE_ENABLED`. |
| `app/backend/requirements.txt` | modify | Add `unbabel-comet`; CPU-only ONNX/torch pin. |
| `app/backend/environment.yml` | modify | Mirror dep addition in pip section if present. |
| `contracts/api/openapi.yml` | regenerate | via `cdd-kit openapi export` (IP-11) — do not hand-edit. |
| `tests/test_env_contract.py` | modify | +`test_qe_enabled_declared`, `test_qe_model_name_declared`, `test_qe_device_declared`. |
| `tests/test_translation_strategy.py` | modify | +`test_qe_hook_called_after_translate_document`, `test_qe_hook_not_called_when_disabled`, `test_translate_texts_unaffected_by_qe_change`. |

## Contract Updates
- API: none (api-contract.md already declares the endpoint + schemas). Only `openapi.yml` is regenerated (IP-11).
- CSS/UI: none.
- Env: none (env-contract.md + `.env.example.template` already declare the 3 vars). Tests assert presence (IP-9).
- Data shape: none (data-shape-contract.md 0.7.0 already declares BlockQualityScore / JobQualityRecord + block_id semantics).
- Business logic: none (business-rules.md 0.11.0 already declares BR-54..BR-58 + Table P).
- CI/CD: none (ci-gates.md + gate workflow already wired; `layout-detector-dependency-gate` covers the CPU-only dep constraint).

---

## IP-2 — `quality_evaluator.py` (interface detail)
- `load_model(model_name: str, device: str) -> model` — lazy, process-cached (one
  load per process; subsequent calls return cache). Invalid `device` value → fall back
  to `"cpu"` with a WARNING log. A load failure propagates so the caller (IP-5) records
  `unavailable`; the cache is not poisoned, so a later job may retry (D-5). Import
  `comet` lazily INSIDE `load_model`, never at module top, or the disabled default
  would still load torch and violate BR-57.
- `score_blocks(model, blocks: List[Tuple[str, str]]) -> List[float]` — `blocks` is
  `List[(src, mt)]` with NO block_id (block_id is owned by the caller in IP-5).
  Reference-free input shape `(source=src, hypothesis=mt)` (D-4). Any exception inside
  scoring returns an empty list (QE failure path → caller maps to `unavailable`).
- Mock seam is the module-level `load_model` name (test-plan §Mock Discipline).

## IP-4 — `post_translate_hook` wiring (most invasive; dedicated commit)
**Confirmed**: the `pre_translate_hook: Optional[Callable[[List[str]], None]]` pattern
is already threaded end-to-end — orchestrator dispatch lines 695/725/743/756/771;
processor signatures pdf 74/185/321/418, docx 482, pptx 194, xlsx 53. Mirror it with a
new param `post_translate_hook: Optional[Callable[[List[Tuple[str, str, str]]], None]] = None`
(note: tuple-of-3 payload, unlike the pre-hook's `List[str]`).

Threading: add the param to `process_files` (orchestrator.py 340-363) and pass
`post_translate_hook=post_translate_hook` into each of the 5 `translate_*` dispatch
calls beside the existing `pre_translate_hook=_phase0_hook`. Each `translate_*` accepts
the param and calls it once after translation, before `return`.

Emission contract (each processor emits `List[(block_id, src, mt)]`; call hook once):
- **DOCX** (`translate_docx`, after `tmap` built, post line 527): for each
  `index, src_text` in `enumerate(uniq_texts)`, for each `tgt` in `targets`, if
  `(tgt, src_text) in tmap`, emit `("docx:{file_stem}:{index}", src_text, tmap[(tgt, src_text)])`.
  `file_stem` from `in_path`.
- **PPTX** (`translate_pptx`, post line 271): same pattern over `enumerate(uniq)`, id prefix `"pptx:{file_stem}:{index}"`.
- **XLSX** (`translate_xlsx_xls`, post line 145): same pattern over `enumerate(uniq)`, id prefix `"{ext}:{file_stem}:{index}"` (xls/xlsx per actual ext).
- **PDF-to-PDF** (`_translate_pdf_to_pdf`): `translatable` (line 461) carries IR `element_id`.
  For each translatable element, for each `tgt`, emit
  `(element.element_id, element.content.strip(), translations[element.content.strip()])`
  using the per-target `translations` dict (line 520). Emit only real translations
  (skip failure-placeholder entries).
- **PDF fallback** (`_translate_pdf_with_pymupdf` / `_translate_pdf_with_pypdf2`): no IR
  `element_id` — synthetic positional id `"pdf:{file_stem}:{index}"` over the
  unique-texts list, same `(tgt, src_text)`-in-tmap guard as the tmap formats.

block_id semantics, multi-file/multi-target accumulation, and run-stable-not-durable
guarantees are governed by design.md §"block_id semantic per format", §"Multi-file /
multi-group accumulation", and BR-58 — follow those; do not redesign the id scheme.

## IP-5 — `job_manager.py` (job worker detail)
In `_run_job` (lines 261-356):
- Before the `route_groups` loop, create `qe_blocks: List[Tuple[str, str, str]] = []`.
- Build a sink (e.g. `qe_blocks.extend`) and pass it as `post_translate_hook=` into the
  `process_files` call (lines 292-314). The accumulator lives here (one list per job),
  mutated only by this single worker thread — no lock needed (design.md §Multi-file/multi-group).
- After the group loop, at/before `job.status = "completed"` (line 343), if `QE_ENABLED`:
  `load_model(QE_MODEL_NAME, QE_DEVICE)`, then `score_blocks([(src, mt) for (_id, src, mt) in qe_blocks])`,
  zip floats back with block_ids + `QE_MODEL_NAME` into `BlockQualityScore`-shaped entries,
  and attach a `JobQualityRecord` (job_id, scores[], qe_status, model). Wrap the whole QE
  block in try/except: any failure (load failure, or empty-list-from-score) sets
  `qe_status="unavailable"` and must NOT change `job.status` away from `completed` and
  must NOT raise (BR-56). If `QE_ENABLED=false`, skip entirely. extraction_only mode produces
  no translations — leave QE skipped there.
- Add `JobQualityRecord` dataclass near `JobRecord` (line 34) — in-memory only, not serialized (D-2).
- Add a getter on `JobManager` (e.g. `get_quality(job_id)`) for the route, mirroring `get_job`.
- `qe_status` enum mirrors the HTTP `status` enum exactly: available/pending/disabled/unavailable (D-2).

## IP-7 — route detail (`routes.py`)
`@router.get("/jobs/{job_id}/quality", response_model=JobQualityResponse)` after
`job_status` (ends 241). Mirror its 404 pattern; resolve status:
- `QE_ENABLED=false` → `disabled`, empty scores.
- job not completed OR no record attached → `pending`, empty scores.
- record with `qe_status="unavailable"` → `unavailable`, empty scores.
- record available → `available`, populated scores.
HTTP 200 in all non-404 cases; unknown job → 404 `{"detail": "Job not found"}`
(api-contract.md §Endpoint Notes).

## IP-8 — deps detail
Add `unbabel-comet`. WARNING (ci-gates.md §Dependency Gate Note): install may pull
`onnxruntime-gpu` transitively, which fails `layout-detector-dependency-gate`
(`! grep -E "(ultralytics|onnxruntime-gpu)" requirements.txt environment.yml`). Pin
CPU-only torch/onnxruntime (check the existing `--extra-index-url`/pin pattern first).
**Exact pin set deferred to dependency-security-reviewer** — do not finalize pins without
that review. Verify with `pip show onnxruntime-gpu` (must be absent) after install. Mirror
into `environment.yml` pip section if present.

## Test Execution Plan
| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 | tests/test_quality_evaluation.py | one score per should_translate block; block_id==element_id |
| AC-1 (int) | tests/test_translation_strategy.py::test_qe_hook_called_after_translate_document | QE hook called (call_count asserted) |
| AC-2 | tests/test_quality_evaluation.py::test_quality_endpoint_returns_200_available_with_scores | 200 + populated scores |
| AC-3 | tests/test_quality_evaluation.py (pending/disabled/unavailable/404) | defined responses; 404 unknown job |
| AC-5 | tests/test_quality_evaluation.py::test_score_block_id_matches_element_id | block_id matches element_id |
| AC-6 | tests/test_env_contract.py::TestEnvContractDeclared (3 new) | env vars declared in env-contract.md + .env.example.template |
| AC-7 | tests/test_quality_evaluation.py (disabled/load-fail/score-fail/invalid-device) + tests/test_translation_strategy.py::test_qe_hook_not_called_when_disabled | job stays completed; safe degradation |
| AC-8 | tests/test_quality_evaluation.py (model-name/zero-block) + pytest tests/ | score includes model; empty scores on zero blocks; full suite green |
| AC-4 | `cdd-kit openapi export --check --out contracts/api/openapi.yml` | exit 0 (CI gate, not pytest) |

Phases (floor): `collect`, `targeted` (the three test files above), `changed-area`
(`tests/`), then `full` smoke before gate (IP-10). Generate evidence with
`cdd-kit test run`; the change-gate validates `test-evidence.yml`. Selector fallback:
the `test file / command` column above supplies bare targets when test-plan.md mapping is unused.

## Handoff Constraints
- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above.
- IP-4 is the most invasive step — land it in a dedicated commit after IP-2/IP-3 are clean (see Ordering Dependencies).
- Re-verify the `pre_translate_hook` line numbers before wiring `post_translate_hook` (confirmed present; code-map may be slightly stale — see Known Risks).
- Patch the COMET model at `app.backend.services.quality_evaluator.load_model` (consumer-bound name), never at the `comet` package source path (test-plan §Mock Discipline; CLAUDE.md mock-binding lesson).
- Integration tests must assert `mock.call_count`/`assert_called_once_with` on the QE hook, not just the job result (test-plan §Mock Discipline; CLAUDE.md tautological-test lesson).
- After api changes, regenerate `openapi.yml` (IP-11) or the openapi-sync gate fails.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved.

## Known Risks
- `unbabel-comet` pulls a large `torch`/possibly `onnxruntime` tree; CI
  `layout-detector-dependency-gate` fails on `onnxruntime-gpu`/`ultralytics`
  (ci-gates.md 29-35). CPU-only pinning required; verify with `pip show onnxruntime-gpu` post-install (IP-8).
- Lazy `comet` import: ensure no top-level `import comet` in `quality_evaluator.py`,
  or the disabled default path would still load torch and violate BR-57.
- Lazy load (D-5) means the first enabled job pays cold-load cost inside the worker
  thread; the QE step is best-effort/isolated so it cannot delay delivery of
  already-archived outputs (BR-56).
- `.cdd/code-map.yml` (generated 2026-06-17) shows `process_files` ending at line 705,
  but the actual dispatch calls run to ~771 — the map is slightly stale for orchestrator.py.
  All IP-4 line numbers were re-verified by direct read; re-confirm before editing.
- Synthetic block_id collisions across files are mitigated by `file_stem` in the id;
  cross-group runs rely on output naming suffix (design.md §Multi-file/multi-group, BR-58) —
  do not change the scheme.
