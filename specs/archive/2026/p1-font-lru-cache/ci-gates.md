# CI/CD Gate Review — p1-font-lru-cache

## Required Gates for This Change

| gate | tier | required | trigger | command / workflow | artifact |
|---|---:|:---:|---|---|---|
| contract-and-fast-tests | 1 | yes | push / PR | `cdd-kit validate --contracts` + `pytest tests/ -x -q` | `test-results/junit.xml` (14 days) |
| change-gate p1-font-lru-cache | 1 | yes | push / PR | `cdd-kit gate p1-font-lru-cache` (inside `contract-and-fast-tests` job) | exit code |
| full-regression | 2 | informational | PR only | `pytest tests/ -q` | `test-results/full-regression.xml` (14 days) |
| scheduled-stress-soak | 4 | informational | weekly schedule / manual dispatch | no-op echo (no stress targets for this change — see change-classification.md §Tasks Not Applicable) | n/a |

No new workflow file is needed. No secret-scan surface change (no new `.yml` config with credentials).

## Workflow Changes Applied

Added `cdd-kit gate p1-font-lru-cache` to the **Change gate** step in
`.github/workflows/contract-driven-gates.yml` alongside the existing entries:

```yaml
- name: Change gate (Tier 1 — blocks merge)
  run: |
    cdd-kit gate p1-cloud-providers
    cdd-kit gate p1-provider-routing
    cdd-kit gate p1-font-lru-cache
```

No other workflow jobs, triggers, secrets, or artifact retention settings were modified.

## Required Check Policy

Branch protection must list **`contract-and-fast-tests`** as a required status
check (matches the job `name:` field exactly). `full-regression` is informational;
a new failure in that job on this PR escalates to a merge blocker.

## Promotion Policy

Change is mergeable when:
1. `contract-and-fast-tests` is green (includes `cdd-kit gate p1-font-lru-cache`).
2. Unit tests for AC-1 through AC-4 pass (see `test-plan.md` rows: no-second-disk-read, buffer equality, distinct-path isolation, error-path unchanged).
3. `full-regression` shows no new failures relative to `main`.

## Rollback Policy

Revert the single commit that adds the LRU cache to `app/backend/renderers/pdf_generator.py`.
The cache is module-local with no persistent state; no data migration or cache-flush step is
required. Revert is safe at any time with no downstream side effects.

## Merge Eligibility

**mergeable** — low-risk, module-local, no contract or API surface changes.
All required gates are covered by the existing workflow with one additive line.
