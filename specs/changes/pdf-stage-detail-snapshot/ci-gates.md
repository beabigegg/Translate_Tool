# CI/CD Gate Plan

## Change ID
pdf-stage-detail-snapshot (bug-fix lane, backend-only, change-classification.md
Tier 3 = risk/process tier, not a CI-gate tier — see Notes).

## Required Gates for This Change
| gate | tier | required | trigger | command/workflow | expected artifact |
|---|---:|---|---|---|---|
| lint/build/unit (combined, blanket suite) | 1 | yes | push / pull_request | `pytest tests/ -x -q --tb=short --junitxml=test-results/junit.xml` — job `contract-and-fast-tests` (`.github/workflows/contract-driven-gates.yml` L133-134) | `test-results/junit.xml` (14d retention) |
| contract-validate | 1 | yes | push / pull_request | `cdd-kit validate --contracts` — job `contract-and-fast-tests` (L43-44) | exit code 0 |
| change-gate (local, unchanged) | 1 | yes | pre-commit | `cdd-kit gate pdf-stage-detail-snapshot --strict` — auto-invoked by `.git/hooks/pre-commit` on any staged `specs/changes/pdf-stage-detail-snapshot/*` path (no workflow-file entry exists or is needed) | exit code 0 |
| full-regression (existing, unchanged) | 2 | informational | pull_request | `pytest tests/ -q --tb=short --junitxml=test-results/full-regression.xml` — job `full-regression` | `full-regression.xml` (14d retention) |

Not applicable: e2e, visual, data-boundary-as-a-separate-gate (exercised inside
the blanket unit run, not a distinct CI job), resilience, fuzz/monkey, stress,
soak, Tier 3 nightly real-infra, Tier 4 weekly soak, Tier 5 manual dispatch —
this change introduces no real-infra, load, or production-like surface (see
`change-classification.md` § Required Tests and § Tasks Not Applicable).

### Acceptance criteria covered by gates
`lint/build/unit` and `contract-validate` together cover AC-1 through AC-8
(`change-classification.md` § Inferred Acceptance Criteria) via
`tests/test_pdf_stage_snapshot.py` (new), `tests/test_job_manager_current_segment.py`,
and `tests/test_jobstatus_stage_detail.py` — see `test-plan.md` § Acceptance
Criteria → Test Mapping for the finalized row-level mapping once test-strategist
completes it.

## New Workflow Changes
None. The existing blanket `pytest tests/ -x -q` step in `contract-and-fast-tests`
globs `tests/` recursively with no path/name filter, so the new
`tests/test_pdf_stage_snapshot.py` and the edits to
`tests/test_job_manager_current_segment.py` / `tests/test_jobstatus_stage_detail.py`
are picked up automatically the moment they are committed — identical precedent to
`layout-fidelity-metrics` and `tatr-parse-outputs`. `cdd-kit validate --contracts`
likewise already covers the additive `contracts/data/data-shape-contract.md` note
with no script change (shallow existence/non-stub check, not per-row semantic
validation — semantic correctness is contract-reviewer's job). No new job, no new
secret, no OIDC change, no artifact-retention change.

## Required Check Policy
Per `contracts/ci/ci-gate-contract.md` § Required Check Policy: branch protection
must list `contract-and-fast-tests` (job `name:` field) as a required status
check — unchanged by this change. `full-regression` remains informational; a new
failure there on this PR still escalates to a merge blocker before close.

## Informational Gate Promotion Policy
No gate is being promoted or demoted between tiers by this change. If either new
test proves flaky across runners, quarantine per
`contracts/ci/ci-gate-contract.md` § Informational Gate Promotion Policy
(owner + exit date) rather than weakening the blanket suite.

## Rollback Policy
Purely additive/observational: threads an existing `status_callback` kwarg into
the PDF path and reuses the #7 `CurrentSegmentSnapshot` pattern already shipped
for Office. No schema/env/API change, no persisted-state format change (snapshot
lives only in the in-memory `JobRecord`). Rollback is a single `git revert` of the
implementation commit; already-running jobs are unaffected.

## Artifact Retention
Unchanged: `test-results/junit.xml` and `full-regression.xml` retain 14 days per
existing `contract-and-fast-tests` / `full-regression` job configuration.

## Merge Eligibility Decision
mergeable — once `contract-and-fast-tests` is green (blanket suite includes the
new/edited test files with zero workflow edits) and `cdd-kit validate --contracts`
passes on the additive data-shape note. No new required check is introduced; no
Tier 2+ gate in the existing inventory is affected by this change's file scope.

## Notes
`change-classification.md` § Tier records `3` as this change's own risk/process
tier (per the generic 0-5 change-tier field), not a CI gate tier — it does not
imply a Tier 3 nightly real-infra CI gate is required. This change carries no
real-infra dependency, so no Tier 3/4/5 gate applies. Reference test-plan.md
rows/AC ids instead of duplicating the full test strategy here.
