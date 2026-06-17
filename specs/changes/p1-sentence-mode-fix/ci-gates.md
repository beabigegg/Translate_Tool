---
change-id: p1-sentence-mode-fix
schema-version: 0.1.0
last-changed: 2026-06-17
tier: 2
---

# CI/CD Gate Review — p1-sentence-mode-fix

## Required Gates for This Change

| gate | tier | required | trigger | command / workflow | artifact |
|---|---:|---:|---|---|---|
| contract-validate | 1 | yes | PR / push | `cdd-kit validate --contracts` (job: `contract-and-fast-tests`) | junit.xml (14 days) |
| pytest full suite | 1 | yes | PR / push | `pytest tests/ -x -q --tb=short` (job: `contract-and-fast-tests`) | junit.xml (14 days) |
| full regression | 2 | yes (PR only) | pull_request | `pytest tests/ -q --tb=short` (job: `full-regression`) | full-regression.xml (14 days) |
| test-evidence presence | 1 | yes (pre-merge) | local | `ls specs/changes/p1-sentence-mode-fix/test-evidence.yml` | test-evidence.yml |

## Workflow Changes Applied

None. The existing `.github/workflows/contract-driven-gates.yml` already covers
all required gates via the `contract-and-fast-tests` job (Tier 1) and the
`full-regression` job (Tier 2). No new job, step, or workflow file is needed
for this change.

## What Is Not Required

- **openapi.yml regeneration** — no API route or response schema changes (AC-7).
- **Migration** — no DB schema changes.
- **Env var changes** — `SENTENCE_MODE` already exists in `app/backend/config.py`; no new var.
- **Tier 0 (local) new target** — existing `pytest` invocation covers all new
  tests in `tests/test_sentence_mode_consistency.py`.

## Promotion Policy

- All tests in `tests/test_sentence_mode_consistency.py` must pass (AC-1 through AC-6).
- `pytest --tb=short -q` must report **389+ passed** (baseline AC-7) before merge.
- `test-evidence.yml` must exist with all phases listed in `test-plan.md §Test Execution Ladder` marked passed.
- `cdd-kit validate --contracts` must exit 0 (includes `contracts/business/business-rules.md` alignment).

## Rollback Policy

Revert the backend-engineer commit touching `translation_service.py`,
`translation_helpers.py`, and `translation_verification.py`. No migration
to undo. No env var to remove.

## Merge Eligibility

**blocked** until:
1. `contract-and-fast-tests` job passes on the PR branch.
2. `full-regression` job passes on the PR.
3. `test-evidence.yml` present with all required phases passed.
4. AC-7 baseline (389+ tests) confirmed in `full-regression` output.
