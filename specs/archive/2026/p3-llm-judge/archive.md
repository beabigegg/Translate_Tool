# Archive: p3-llm-judge

## Change Summary

Added an LLM-as-judge quality review loop and selective re-translation capability to the translation pipeline. A new `QualityJudge` class (`quality_judge.py`) evaluates translated blocks using a local Gemma model, scoring each block and triggering re-translation for low-scoring segments. Results are stored on `JobRecord` as a `JudgeResult`, exposed via `GET /jobs/{id}/judge`, and applied to output files via `POST /jobs/{id}/judge/apply` (async, with deterministic per-block replay re-render using a `block_overrides` seam threaded through all 4 processors). The feature is off by default (`JUDGE_ENABLED=false`) and intended to give translators an optional quality floor.

## Final Behavior

- `JUDGE_ENABLED=true` (env/config flag): after QE scoring and term audit, the judge loop runs over all collected `qe_blocks`; segments below `JUDGE_THRESHOLD` (default 0.65) are re-translated with feedback in the prompt (up to `JUDGE_MAX_ITERATIONS` rounds).
- `GET /api/jobs/{id}/judge` returns `JudgeResult` (overall_score, block scores, re-translation counts, flagged blocks).
- `POST /api/jobs/{id}/judge/apply` dispatches a daemon thread that re-renders output files using the judge-approved translations via `block_overrides`; status transitions: `applying → applied | failed`.
- `job_status` (`GET /api/jobs/{id}`) includes `judge_score` and `judge_apply_status` fields.
- Feature is guarded: unavailable model → `run_judge_loop` returns gracefully with `status: unavailable`.

## Final Contracts Updated

- `contracts/api/api-contract.md` — BR-72..BR-77; `GET /jobs/{id}/judge`, `POST /jobs/{id}/judge/apply`; `JobStatus` judge fields; schema bumped to 0.8.0
- `contracts/data/data-shape-contract.md` — `JudgeResult` shape, `JobRecord.judge/judge_apply_status`; bumped to 0.12.0
- `contracts/business/business-rules.md` — BR-72..BR-77 (judge loop cap, threshold, idempotency, graceful degradation, Ollama-only constraint); bumped to 0.18.0
- `contracts/env/env-contract.md` — `JUDGE_ENABLED`, `JUDGE_MODEL`, `JUDGE_MAX_ITERATIONS`; bumped to 0.10.0
- `contracts/css/css-contract.md` + `design-tokens.md` — judge score color tokens; bumped to 0.3.0
- `contracts/api/openapi.yml` — regenerated

## Final Tests Added / Updated

- `tests/test_quality_judge.py` — 17 unit tests (score parse, loop cap, iteration count, D4 Ollama-only, AC-1..AC-4)
- `tests/test_judge_api.py` — 10 contract tests (`GET /judge` shapes, `POST /apply` preconditions BR-76, idempotency BR-77)
- `tests/test_orchestrator_judge.py` — 6 integration tests (hook fires for docx/pptx/xlsx/pdf, QE coexistence AC-8)
- `tests/test_judge_apply.py` — 4 integration tests (daemon dispatch, applied transition, fail-soft, idempotency)
- `tests/test_job_record_judge.py` — 3 data-boundary tests (JudgeResult fields, defaults, JobRecord fields)
- Regression fixes: `tests/test_jobstatus_download_url.py` (_make_job adds `job.judge=None`, `job.judge_apply_status=None`), `tests/test_orchestrator_phase0.py` (_fake_translate_docx adds `block_overrides=None`)
- Final suite: 872 passed, 4 skipped

## Final CI/CD Gates

Required (Tier 1): `contract-validate`, `change-gate`, `openapi-sync`, `env-schema-sync-judge`, `all-formats-wiring`, `secret-scan`, `targeted-judge-tests` (40 tests), `full-test-suite`
Required (Tier 2): `full-regression`, `layout-detector-dependency`
All pass per qa-reviewer.yml.

## Production Reality Findings

- `test-evidence.yml` initially had `final-status: failed` because the collect phase ran outside the conda env. Re-running under conda env resolved it — no code change required.
- `quality_judge` imports `JudgeResult` lazily from `job_manager` to avoid circular import; backend-engineer noted this is an important constraint.
- `JUDGE_ENABLED` is accessed via `config.JUDGE_ENABLED` in `_run_job` (not bound at import time) — test patches must target `job_manager.config.JUDGE_ENABLED`, not `job_manager.JUDGE_ENABLED`.

## Lessons Promoted to Standards

None. All agent findings are either covered by existing CLAUDE.md entries (patch-target-at-call-time rule) or are one-off implementation details derivable from the code (lazy import for circular-import avoidance, conda env activation, apply_judge file guard). No new cross-change contract rules or workflow invariants identified.

## Follow-up Work

- Pre-existing gaps noted by contract-reviewer: `GET /audit` endpoint row missing from `api-contract.md`; `layout_viz_available` field absent from `JobStatus` contract schema — not blocking p3-llm-judge, deferred to future change.
- Frontend judge panel (AC-6, AC-9) not yet implemented (result display + apply button); deferred per scope decision.

## Cold Data Warning

This archive is historical evidence. Current requirements live in `contracts/` and active project guidance.
