# CI/CD Gate Plan: p3-llm-judge

## Change ID
p3-llm-judge

# CI/CD Gate Review

## Required Gates for This Change

| gate | tier | required | trigger | command / workflow | artifact |
|---|---:|:---:|---|---|---|
| contract-validate | 1 | yes | push / pull_request | `cdd-kit validate --contracts` in `contract-and-fast-tests` job | none |
| change-gate | 1 | yes | push / pull_request | `cdd-kit gate p3-llm-judge` in `contract-and-fast-tests` job | none |
| openapi-sync | 1 | yes | push / pull_request | `cdd-kit openapi export --check` in `contract-and-fast-tests` job | none |
| env-schema-sync-judge | 1 | yes | push / pull_request | `grep` JUDGE_ENABLED / JUDGE_MODEL / JUDGE_MAX_ITERATIONS in `.env.example.template` and `env.schema.json` | none |
| all-formats-wiring | 1 | yes | push / pull_request | `grep -l "quality_judge\|run_judge"` in each of the 4 processor files (AC-7) | none |
| secret-scan | 1 | yes | push / pull_request | existing literal-key grep scan in `contract-and-fast-tests` job | none |
| targeted-judge-tests | 1 | yes | push / pull_request | `pytest tests/test_quality_judge.py tests/test_judge_api.py tests/test_orchestrator_judge.py tests/test_judge_apply.py tests/test_job_record_judge.py -x -q --tb=short` | none |
| full-test-suite | 1 | yes | push / pull_request | `pytest tests/ -x -q --tb=short` in `contract-and-fast-tests` job | `test-results/junit.xml` (14 days) |
| full-regression | 2 | yes | pull_request | `pytest tests/ -q --tb=short` in `full-regression` job | `test-results/full-regression.xml` (14 days) |
| layout-detector-dependency | 2 | yes | pull_request | `! grep -E "(ultralytics\|onnxruntime-gpu)"` in `layout-detector-dependency-gate` job | none |

## Gates Not Required for This Change

| gate | reason |
|---|---|
| e2e / real-infra (Tier 3) | Tier 2 change; judge is feature-flagged off by default; no live-Ollama gate required |
| stress / soak (Tier 4/5) | Not applicable per `change-classification.md §Tasks Not Applicable 3.5` |
| fuzz / monkey (Tier 3/4) | Not applicable per `change-classification.md §Tasks Not Applicable 3.4` |
| UI / visual (Tier 2 informational) | AC-6 / AC-9 frontend panel is out of scope for test gate; logged in agent-log/visual-reviewer.yml |
| nightly / weekly / manual dispatch | No real-infra or soak targets defined for this change |

## Workflow Changes Applied

### `.github/workflows/contract-driven-gates.yml`

**1. Active change gates comment (line 3)** — added `p3-llm-judge` to the active list.

**2. Change gate step** — replaced `echo "No active change gates..."` no-op with:
```
cdd-kit gate p3-llm-judge
```

**3. Env schema sync — JUDGE vars step** — added after the existing DEEPSEEK/TERM env-sync step:
```
grep -q "JUDGE_ENABLED" .env.example.template && env.schema.json
grep -q "JUDGE_MODEL" ...
grep -q "JUDGE_MAX_ITERATIONS" ...
```
Mirrors the DEEPSEEK_ENABLED / TERM_EMBEDDING_* pattern already in the job.

**4. Targeted judge tests step** — inserted before the full `pytest tests/` step, after the existing `targeted-table-recognizer` step. Covers all test-plan.md families: unit (AC-1..AC-4), contract (AC-5), integration (AC-7, AC-8, AC-10), data-boundary (AC-5, AC-10). See `test-plan.md §Acceptance Criteria → Test Mapping`.

No new CI jobs; all modifications are within the existing `contract-and-fast-tests` job.

## Promotion Policy

- All Tier 1 gates (`contract-and-fast-tests` job) must be green before merge.
- `targeted-judge-tests` fast-fail step must pass before the full suite step.
- The `full-regression` and `layout-detector-dependency-gate` Tier 2 jobs run on `pull_request` only and block merge on new failures.
- No Tier 3/4/5 gates are required for this change.

## Rollback Policy

- `quality_judge.py` is a new module behind `JUDGE_ENABLED=false` (default). Setting the flag to false or removing the hook call in `job_manager._run_job` restores prior behavior with no migration.
- No DDL migration, no new API key, no new external dependency — rollback is a file-level revert with no follow-on operational steps.
- If a post-merge regression is detected in `full-regression`: revert the commit, confirm `contract-and-fast-tests` is clean, then open a follow-up change.

## Merge Eligibility

**mergeable** once all Tier 1 gates pass and Tier 2 gates on the PR show no new failures.

Tier 1 required checks (must appear green in branch protection):
- `contract-and-fast-tests`

Tier 2 informational-risk checks (new failures escalate to blocker):
- `full-regression`
- `golden-sample-regression`
- `layout-detector-dependency-gate`
