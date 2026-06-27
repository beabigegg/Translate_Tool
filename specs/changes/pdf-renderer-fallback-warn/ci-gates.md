---
change-id: pdf-renderer-fallback-warn
schema-version: 0.1.0
last-changed: 2026-06-27
---

# CI/CD Gate Review

## Required Gates for This Change

| gate | tier | required | trigger | command / workflow | artifact |
|---|---:|---:|---|---|---|
| contract-validation | 1 | yes | push / pull_request | `cdd-kit validate --contracts` in `contract-and-fast-tests` | none |
| openapi-sync | 1 | yes | push / pull_request | `cdd-kit openapi export --check --out contracts/api/openapi.yml` in `contract-and-fast-tests` | none |
| change-gate | 1 | yes | push / pull_request | `cdd-kit gate pdf-renderer-fallback-warn` in `contract-and-fast-tests` | none |
| targeted-warnings-tests | 1 | yes | push / pull_request | `pytest tests/test_pdf_render_warnings.py -x -q --tb=short` in `contract-and-fast-tests` | test-results/junit.xml |
| full-test-suite | 1 | yes | push / pull_request | `pytest tests/ -x -q --tb=short` in `contract-and-fast-tests` | test-results/junit.xml |
| full-regression | 2 | informational | pull_request | `pytest tests/ -q --tb=short` in `full-regression` | full-regression-results/full-regression.xml |
| renderer-equivalence | 2 | informational | pull_request | `pytest tests/test_ir_pipeline_decoupling.py tests/test_renderer_convergence.py -k equivalence` in `renderer-equivalence` | renderer-equivalence-results/renderer-equivalence.xml |

**Tier 3, 4, 5 gates**: not applicable. This change has no real-infra dependency (all paths are exercised with mocks), no load surface, and no manual production scenario required.

### Acceptance criteria covered by gates

| gate | AC covered | test-plan.md rows |
|---|---|---|
| targeted-warnings-tests | AC-1, AC-2, AC-3, AC-4, AC-5, AC-6 | all rows in test-plan.md §Acceptance Criteria → Test Mapping |
| openapi-sync | AC-5 | `cdd-kit openapi export --check` verifies openapi.yml is regenerated after api-contract bump 0.8.0→0.9.0 |
| contract-validation | AC-5 | validates bumped `contracts/api/api-contract.md` (0.9.0) and `contracts/data/data-shape-contract.md` (0.13.0) |

### Pre-commit prerequisite (Tier 0 — local fast gate)

Run before pushing:

```bash
# 1. Regenerate OpenAPI spec after bumping api-contract to 0.9.0
cdd-kit openapi export --out contracts/api/openapi.yml

# 2. Fast targeted tests (unit + data-boundary families from test-plan.md Tier 0 rows)
pytest tests/test_pdf_render_warnings.py -x -q

# 3. Contract validation
cdd-kit validate --contracts
```

## Workflow Changes Applied

Two edits to `.github/workflows/contract-driven-gates.yml`:

1. **Change gate step** — replaced `echo "No active change gates."` with `cdd-kit gate pdf-renderer-fallback-warn` and updated the active-change header comment.

2. **Targeted warnings tests step** — added a new step after the `quality_judge` targeted step and before the full suite, running `pytest tests/test_pdf_render_warnings.py -x -q --tb=short`. Fast-fails on AC-1..AC-6 before the full-suite step absorbs the same tests at higher latency.

No new jobs, no new secrets, no OIDC changes required.

## Promotion Policy

`full-regression` and `renderer-equivalence` are Tier 2 (informational). They are already established gates and pass reliably. No promotion action required for this change.

If `targeted-warnings-tests` fails on a transient runner issue (not a code defect), quarantine via a separate informational job with an owner and exit date per `ci/required-check-policy.md §Promotion criteria`.

## Rollback Policy

This change is purely additive (new optional `warnings` field on `GET /api/jobs/{id}`). If a regression is detected post-merge:

1. Revert the commit that bumped `api-contract.md` and `data-shape-contract.md`.
2. Regenerate `openapi.yml` from the reverted contract (`cdd-kit openapi export --out contracts/api/openapi.yml`).
3. Existing API consumers are unaffected because `warnings` is optional and defaults to `None`/absent.

No DB migration, no config change, no feature flag — rollback is a single revert commit.

At `/cdd-close`: remove the `cdd-kit gate pdf-renderer-fallback-warn` line from `.github/workflows/contract-driven-gates.yml` (CLAUDE.md promoted learning — archived dirs no longer exist under `specs/changes/` and CI fails with "change not found").

## Merge Eligibility

**mergeable** when:
- `contract-and-fast-tests` passes (includes `change-gate`, `openapi-sync`, `contract-validation`, `targeted-warnings-tests`, and `full-test-suite`)
- `contracts/api/openapi.yml` regenerated and committed in the same PR branch

Informational gates (`full-regression`, `renderer-equivalence`) do not block merge but new failures must be triaged before closing the change.
