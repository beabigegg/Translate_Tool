# CI/CD Gate Plan: p3-table-structure

## Change ID
p3-table-structure

# CI/CD Gate Review

## Required Gates for This Change

| gate | tier | required | trigger | command / workflow | artifact |
|---|---:|:---:|---|---|---|
| contract-validate | 1 | yes | push / pull_request | `cdd-kit validate --contracts` in `contract-and-fast-tests` job | none |
| change-gate | 1 | yes | push / pull_request | `cdd-kit gate p3-table-structure` in `contract-and-fast-tests` job | none |
| openapi-sync | 1 | yes | push / pull_request | `cdd-kit openapi export --check` in `contract-and-fast-tests` job | none |
| env-schema-sync | 1 | yes | push / pull_request | `grep` checks in `contract-and-fast-tests` job | none |
| secret-scan | 1 | yes | push / pull_request | `grep -rn` literal-key scan in `contract-and-fast-tests` job | none |
| targeted-table-recognizer | 1 | yes | push / pull_request | `pytest tests/test_table_recognizer.py -x -q --tb=short` in `contract-and-fast-tests` job | none |
| full-test-suite | 1 | yes | push / pull_request | `pytest tests/ -x -q --tb=short` in `contract-and-fast-tests` job | `test-results/junit.xml` (14 days) |
| full-regression | 2 | yes | pull_request | `pytest tests/ -q --tb=short` in `full-regression` job | `test-results/full-regression.xml` (14 days) |
| layout-detector-dependency | 2 | yes | pull_request | `! grep -E "(ultralytics\|onnxruntime-gpu)"` in `layout-detector-dependency-gate` job | none |

## Gates Not Required for This Change

| gate | reason |
|---|---|
| e2e / real-infra (Tier 3) | Tier 2 change; ML model mocked at ONNX boundary; no live-endpoint gate needed |
| stress / soak (Tier 4/5) | Cell-batch coalesces to one LLM call per table — reduces load (see `change-classification.md §Tasks Not Applicable 3.5`) |
| UI / visual (Tier 2 informational) | No UI surface touched |
| new dependency gate | `onnxruntime`, `transformers`, and `torch` already in `requirements.txt`; TATR requires no new packages |
| nightly / weekly / manual dispatch | Tier 2; no real-infra or soak targets defined for this change |

## Workflow Changes Applied

### `.github/workflows/contract-driven-gates.yml`

**1. Active change gates comment (line 3)** — updated from `none (archived: ...)` to `p3-table-structure (archived: ...)`.

**2. Change gate step** — replaced the `echo "No active change gates..."` no-op with:
```
cdd-kit gate p3-table-structure
```

**3. Targeted table-recognizer step** — inserted before the full `pytest tests/` step:
```
pytest tests/test_table_recognizer.py -x -q --tb=short
```
This mirrors the `Targeted tests — term_extractor + term_db + env_contract` pattern already in the job and provides a fast-fail signal before the full suite runs. Covers all test families in `test-plan.md`: unit (AC-1, AC-3), contract (AC-1), integration (AC-2, AC-3, AC-4), data-boundary (AC-5, AC-6).

No new jobs or job-level changes were made; all three modifications are within the existing `contract-and-fast-tests` job.

## Promotion Policy

- All Tier 1 gates (`contract-and-fast-tests` job) must be green before merge.
- The `full-regression` and `layout-detector-dependency-gate` Tier 2 jobs run on `pull_request` only and block merge on new failures.
- `targeted-table-recognizer` fast-fail step must pass before the full suite step runs.
- No Tier 3/4/5 gates are required for this change.

## Rollback Policy

- `table_recognizer.py` is a new module with no callers outside `pdf_processor.py`; removing the import or reverting to the passthrough path restores prior behavior without migration.
- No database schema change, no API contract change, no env-key addition — rollback is a file-level revert with no follow-on operational steps.
- If a post-merge regression is detected in `full-regression` or `golden-sample-regression`: revert the commit, re-run `contract-and-fast-tests` to confirm clean, then open a follow-up change.

## Merge Eligibility

**mergeable** once all Tier 1 gates pass and Tier 2 gates on the PR show no new failures.

Tier 1 required checks (must appear green in branch protection):
- `contract-and-fast-tests`

Tier 2 informational-risk checks (new failures escalate to blocker):
- `full-regression`
- `golden-sample-regression`
- `layout-detector-dependency-gate`
