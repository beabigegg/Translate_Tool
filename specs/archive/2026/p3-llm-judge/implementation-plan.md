---
change-id: p3-llm-judge
schema-version: 0.1.0
last-changed: 2026-06-22
---

# Implementation Plan: p3-llm-judge

## Objective
Ship an optional, feature-flagged Gemma LLM-as-judge quality pass that runs after a translation job completes: score the collected source/translated block pairs on the 低/中/高 tier, re-translate with judge feedback on 中/低 (cap 3, stop at 高), attach the result to `JobRecord`, expose it read-only via `GET /api/jobs/{id}/judge`, let the user apply the re-translated text via `POST /api/jobs/{id}/judge/apply` (async re-render + output swap), and render a judge panel + apply dialog in the job-detail UI. Default `JUDGE_ENABLED=false` makes the whole feature a no-op.

## Execution Scope

### In Scope
- Backend: config flags, new `quality_judge.py` service, judge hook in `job_manager._run_job`, `JudgeResult` dataclass + two new `JobRecord` fields, `apply_judge` worker, two new endpoints, two new + amended Pydantic schemas, a per-block replacement seam through `process_files` reaching all 4 processors.
- Frontend: two `api/jobs.js` functions, `JudgePanel.jsx`, `JudgeApplyDialog.jsx`, wiring into `TranslatePage.jsx` step-3 completed view.
- Tests: 5 new test files per `test-plan.md`.

### Out of Scope
- AC-6 / AC-9 visual conformance (ui-ux-reviewer / visual-reviewer own these; no backend test surface).
- Per-block/cell-level judging granularity (design.md D3 non-goal).
- Routing the judge through `model_router` (forbidden by D4).
- VRAM/model-unload tuning beyond an optional `release_resources` call (open risk; not a blocking deliverable).
- Any change to `quality`/`audit`/`CRITIQUE_LOOP` behavior, existing endpoints, or the `post_translate_hook` accumulator contract.
- E2E / monkey / stress tests (not-applicable per change-classification.md §Tasks Not Applicable).

## Required Changes
| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | config | Add `JUDGE_ENABLED` (default False), `JUDGE_MODEL` (default `gemma3`), `JUDGE_MAX_ITERATIONS` (default 3) to `app/backend/config.py` | backend-engineer |
| IP-2 | service (new) | Create `app/backend/services/quality_judge.py`: `QualityJudge` building its own `OllamaClient(JUDGE_MODEL)` (D4), `evaluate(...)→JudgeResult`, JSON-then-CJK-token score parse (D6), `run_judge_loop(...)` with feedback reflection + iteration cap, graceful degradation (D5). Mock seam mirrors `quality_evaluator.load_model` | backend-engineer |
| IP-3 | data shape | Add `JudgeResult` dataclass + `JobRecord.judge: Optional[JudgeResult]` + `JobRecord.judge_apply_status: Optional[str]` to `job_manager.py` (D3) | backend-engineer |
| IP-4 | job lifecycle | Call judge loop in `_run_job` after QE+audit, before completion (D1); add `apply_judge(job_id)` daemon-thread worker (D7) | backend-engineer |
| IP-5 | re-render seam | Add a per-block replacement param to `process_files` + thread it to all 4 processors so a `{block_id: text}` map short-circuits the LLM call (D7). Verify by grep (AC-7) | backend-engineer |
| IP-6 | schemas | Add `JobJudgeResponse`, `JobJudgeApplyResponse`; add `judge_score`, `judge_apply_status` to `JobStatus` | backend-engineer |
| IP-7 | API | Add `GET /jobs/{job_id}/judge` and `POST /jobs/{job_id}/judge/apply` to `routes.py`; surface `judge_score`/`judge_apply_status` in `job_status` (D8, BR-76/77) | backend-engineer |
| IP-8 | openapi | Run `cdd-kit openapi export --out contracts/api/openapi.yml` after schema/endpoint changes | backend-engineer |
| IP-9 | frontend api | Add `getJudge(jobId)` + `applyJudge(jobId)` to `app/frontend/src/api/jobs.js` | frontend-engineer |
| IP-10 | frontend components | Create `JudgePanel.jsx` + `JudgeApplyDialog.jsx` under `components/domain/` per css-contract rows | frontend-engineer |
| IP-11 | frontend page | Render `JudgePanel` in `TranslatePage.jsx` step-3 completed view | frontend-engineer |
| IP-12 | tests | Write the 5 test files (backend-engineer owns all; AC-6/AC-9 excluded) | backend-engineer |

## Source Artifact Pointers
| source | relevant pointer | used for |
|---|---|---|
| design.md | D1 (hook point), D3 (data shape), D4 (Gemma routing), D5 (degradation), D6 (score parse), D7 (apply/re-render seam), D8 (apply endpoint) | implementation constraints |
| contracts/data/data-shape-contract.md | §LLM Judge Result Representation (JudgeResult fields, JobRecord.judge / judge_apply_status, invalid-data rules, known consumers) | dataclass fields + null rules |
| contracts/api/api-contract.md | endpoints table rows for `/judge` + `/judge/apply`; §Schemas JobJudgeResponse / JobJudgeApplyResponse; §Endpoint Notes for both | endpoint contracts + response models |
| contracts/business/business-rules.md | BR-72..BR-77; Table U | loop behavior + precondition status codes |
| contracts/css/css-contract.md | JudgePanel / JudgeBadge / JudgeApplyButton / JudgeApplyDialog rows + visibility rule + color tokens | component states + token names |
| contracts/env/env-contract.md, .env.example.template, env.schema.json | JUDGE_ENABLED / JUDGE_MODEL / JUDGE_MAX_ITERATIONS | config flag names (already synced by contract-reviewer) |
| test-plan.md | §Acceptance Criteria → Test Mapping; §Notes (anti-tautology) | test files + assertions |
| ci-gates.md | required-gates table (env-schema-sync-judge, all-formats-wiring, targeted-judge-tests, openapi-sync) | verification commands |

## File-Level Plan
| path or glob | action | notes |
|---|---|---|
| `app/backend/config.py` | edit | Add 3 constants near other feature flags (`QE_ENABLED` etc.); read flags from env using the existing pattern in this module |
| `app/backend/services/quality_judge.py` | create | `QualityJudge.__init__` builds `OllamaClient(model=JUDGE_MODEL)` against `OLLAMA_BASE_URL` — never `model_router` (D4). `evaluate(source_text, translated_text)→JudgeResult`. Score parse: `json.loads` first, else scan for first of 高/中/低 (exact token, no synonyms), else `judge_status="unavailable"` (D6). `run_judge_loop(job_id, blocks, translate_fn)`: loop ≤ `JUDGE_MAX_ITERATIONS`; stop at 高; on 中/低 call `translate_fn` with feedback string in the prompt (BR-75); accumulate `retranslated_blocks={block_id: text}`; set `attempts`; return one `JudgeResult`. Wrap the whole pass so any exception → WARNING log + `unavailable` (D5/BR-74) |
| `app/backend/services/job_manager.py` | edit | (a) Add `@dataclass JudgeResult` (fields per data-shape-contract: job_id, judge_status, score, source_text, translated_text, feedback, attempts, model, retranslated_blocks) near `JobQualityRecord` (~line 47). (b) Add `judge: Optional[JudgeResult] = None` and `judge_apply_status: Optional[str] = None` to `JobRecord` (after line 86). (c) In the nested `_run_job` closure, insert the judge step after the term-audit block (~line 422) and before the `with job.lock:` completion block (line 424): if `JUDGE_ENABLED` and `mode != "extraction_only"` run `run_judge_loop` over `qe_blocks` (the `(block_id, src, mt)` accumulator already filled by `post_translate_hook`), set `job.judge`; if `not JUDGE_ENABLED` leave `job.judge=None`. (d) Add `apply_judge(job_id)` worker (mirror the `_run_job` daemon-thread + `job.lock` + `_archive_outputs` pattern): set `judge_apply_status="applying"`, call `process_files` on `job.input_dir` files writing to `job.output_dir`, passing the `retranslated_blocks` map via the new seam; rebuild zip into a temp path, swap `job.output_zip` only on success → `applied`; on any exception → WARNING + `failed`, original zip untouched (D7) |
| `app/backend/processors/orchestrator.py` | edit | Add an optional param (e.g. `block_overrides: Optional[Dict[str,str]] = None`) to `process_files` (signature at line 339) and thread it to the 5 internal processor calls (lines ~693, 725, 745, 760, 777, alongside `post_translate_hook`). Before each LLM batch call, the processor consults the map: `block_id` present → use stored text, skip the model call. Assert id-set equality between map and emitted block ids; on mismatch fail (caller fail-softs). Keep the existing `post_translate_hook` signature unchanged |
| `app/backend/processors/{docx,pptx,xlsx,pdf}_processor.py` | edit | Each must honor `block_overrides` at its translate seam so AC-7 holds for all 4 formats. Read the processor's own translate-batch call site; reuse the same `block_id` key the `post_translate_hook` accumulator emits (D7 constraint) |
| `app/backend/api/schemas.py` | edit | Add `JobJudgeResponse` (job_id, judge_status, score?, source_text?, translated_text?, feedback?, attempts?, model?) and `JobJudgeApplyResponse` (status) after `JobAuditResponse` (~line 191). Add `judge_score: Optional[str] = None` and `judge_apply_status: Optional[str] = None` to `JobStatus` (after line 39) |
| `app/backend/api/routes.py` | edit | Add `GET /jobs/{job_id}/judge` mirroring `job_quality` (line 345): 404 unknown job; `disabled` when `not JUDGE_ENABLED`; else map `job.judge`→`JobJudgeResponse`. Add `POST /jobs/{job_id}/judge/apply`: 404 unknown; 409 on any failed precondition (BR-76: status≠completed, judge_status≠available, empty `retranslated_blocks`, `input_dir` missing); idempotent 202 when already `applying` (BR-77); else dispatch `apply_judge` on a daemon thread, return 202 `{"status":"applying"}`. Add `JUDGE_ENABLED` + judge schemas to imports at lines 19/53. In `job_status` (line 246) populate `judge_score` (from `job.judge.score`) and `judge_apply_status` within the existing lock block |
| `contracts/api/openapi.yml` | regenerate | `cdd-kit openapi export` only — not hand-edited |
| `app/frontend/src/api/jobs.js` | edit | Add `getJudge = (jobId) => get(\`/api/jobs/${jobId}/judge\`)` and `applyJudge = (jobId) => post(\`/api/jobs/${jobId}/judge/apply\`)` |
| `app/frontend/src/components/domain/JudgePanel.jsx` | create | Render nothing unless `judge_status==="available"` (css-contract visibility rule). Show JudgeBadge (高→`--color-quality-high`, 中→`--color-quality-mid`, 低→`--color-quality-low`; no hardcoded hex), source_text, translated_text, feedback, attempts. JudgeApplyButton visible only when score ∈ {中,低} and `judge_apply_status ∉ {applying,applied}`; opens JudgeApplyDialog |
| `app/frontend/src/components/domain/JudgeApplyDialog.jsx` | create | Modal: re-translated text preview + destructive-overwrite warning (no backup). On confirm → `applyJudge(jobId)`; rely on existing `useJobPolling` (already polling `GET /jobs/{id}`) to read `judge_apply_status` to applied/failed. On cancel close with no side effect |
| `app/frontend/src/pages/TranslatePage.jsx` | edit | Fetch judge via `getJudge` when `jobStatus.status==="completed"`; render `<JudgePanel>` in the step-3 completed block (near the download link, ~lines 256-261). No change to upload/settings steps |
| `tests/test_quality_judge.py` | create | unit — see Test Execution Plan |
| `tests/test_judge_api.py` | create | contract |
| `tests/test_orchestrator_judge.py` | create | integration (all 4 formats + QE coexistence) |
| `tests/test_judge_apply.py` | create | integration (apply preconditions, idempotency, temp-swap, block-id mismatch) |
| `tests/test_job_record_judge.py` | create | data-boundary |

## Contract Updates
- API: no contract edit needed — api-contract.md already defines both endpoints + schemas; regenerate `openapi.yml` after code lands (IP-8, openapi-sync gate).
- CSS/UI: no contract edit — css-contract.md + design-tokens.md already define the components and `--color-quality-{high,mid,low}` tokens; implementation must use those tokens.
- Env: no contract edit — JUDGE_* vars already in env-contract.md / .env.example.template / env.schema.json (done by contract-reviewer). Implementation must use the exact names.
- Data shape: no contract edit — data-shape-contract.md §LLM Judge Result Representation is authoritative; dataclass fields must match it exactly.
- Business logic: no contract edit — BR-72..BR-77 + Table U authoritative; implement to them.
- CI/CD: no workflow edit by implementation — ci-gates.md changes already applied to `contract-driven-gates.yml`.

## Test Execution Plan
| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 | tests/test_quality_judge.py::test_judge_records_result_on_job_record | JudgeResult attached with score/feedback/attempts |
| AC-1 | tests/test_quality_judge.py::test_judge_score_high_terminates_loop | loop exits at 高, attempts==1 |
| AC-2 | tests/test_quality_judge.py::test_judge_score_mid_triggers_retranslation | translate_fn invoked on 中 |
| AC-2 | tests/test_quality_judge.py::test_judge_score_high_no_retranslation | translate_fn not invoked on 高 |
| AC-2 | tests/test_quality_judge.py::test_feedback_fed_back_to_translation_model | feedback string present in re-translation prompt arg (BR-75) |
| AC-3 | tests/test_quality_judge.py::test_judge_iteration_cap_enforced | loop stops at cap |
| AC-3 | tests/test_quality_judge.py::test_attempts_field_equals_iteration_count | `attempts == JUDGE_MAX_ITERATIONS` when cap fires (not just "loop ended") |
| AC-4 | tests/test_quality_judge.py::test_judge_disabled_flag_skips_judge | judge skipped, job completes |
| AC-4 | tests/test_quality_judge.py::test_judge_exception_degrades_gracefully | exception→unavailable, no raise |
| AC-4 | tests/test_quality_judge.py::test_judge_parse_failure_degrades_gracefully | parse fail→unavailable |
| BR-72 | tests/test_quality_judge.py | JSON-first then CJK-token scan; synonyms rejected; no token→unavailable |
| D4 | tests/test_quality_judge.py::test_judge_client_is_ollama_not_model_router | `model_router.resolve_route_groups` NOT called during judge |
| AC-5 | tests/test_judge_api.py | GET available/disabled/unavailable/404; POST 202; POST 409 ×4; idempotent-while-applying |
| AC-7 | tests/test_orchestrator_judge.py | judge invoked via real `_run_job` for docx/pptx/xlsx/pdf (not a bare unit mock) |
| AC-8 | tests/test_orchestrator_judge.py | QE scores + critique path unchanged with judge present/off |
| AC-10 | tests/test_judge_apply.py | output swap on success; original preserved on failure; block-id mismatch fail-soft |
| BR-77 | tests/test_judge_apply.py::test_apply_uses_stored_block_map_not_llm | apply uses stored map, no LLM call |
| AC-5/AC-10 | tests/test_job_record_judge.py | judge_score summary + judge_apply_status transitions + backward-compat without judge field |

Required test phases: `collect`, `targeted`, `changed-area` (this is the floor; full ladder in test-plan.md / references/sdd-tdd-policy.md). Run in order:
1. `cdd-kit test run p3-llm-judge --phase collect`
2. `cdd-kit test run p3-llm-judge --phase targeted --command "pytest tests/test_quality_judge.py tests/test_judge_api.py tests/test_orchestrator_judge.py tests/test_judge_apply.py tests/test_job_record_judge.py -x -q --tb=short"`
3. `cdd-kit test run p3-llm-judge --phase changed-area --command "pytest tests/ -x -q --tb=short"`

## Handoff Constraints
- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved.
- After IP-5 lands, run the AC-7 wiring grep (`grep -l "block_overrides\|run_judge\|quality_judge"` across the 4 processor files) — do NOT rely on unit mocks alone to claim all-formats coverage (orphaned-wiring learning).
- After schema/endpoint changes, regenerate `openapi.yml` (openapi-sync gate fails on stale).

## Known Risks
- Re-render block mismatch (design.md Open Risks): the apply seam keys on `block_id`; a processor that regenerates ids on re-parse silently mis-maps text. Mitigation: assert id-set equality before substituting; fail-soft to original (covered by `test_apply_block_id_mismatch_fails_soft`).
- All-formats wiring (AC-7): the judge runs over the job-level `qe_blocks` aggregate via `_run_job`, but the apply re-render seam must reach every processor's translate call — verify with grep, not mocks (wrong-entry-point + orphaned-wiring learnings).
- Tautological iteration tests: assert `attempts == JUDGE_MAX_ITERATIONS` on cap, not merely that the loop exited (test-plan.md §Notes / CLAUDE.md tautology learning).
- VRAM contention with Gemma + translation model on 8GB (open risk); flag stays off by default; optional `release_resources` before judging is allowed but not a blocking deliverable.
- 50-job-cap eviction / 24h TTL can remove `input_dir` before a late apply — apply must 409 when source is gone (data-shape-contract invalid-data rule), not re-render against missing input.
- `_run_job` is a nested closure inside `create_job` (not a method) — the judge step and the new `apply_judge` worker live in different scopes; share the `JudgeResult` / `process_files` plumbing carefully and reuse `_archive_outputs`.
