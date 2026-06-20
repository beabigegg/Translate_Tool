---
change-id: settings-page-cloud-redesign
last-changed: 2026-06-20
---
# CI Gates

## Required Gates (block merge)

| gate | tier | trigger | command / workflow | blocks |
|---|---:|---|---|---|
| validate-contracts | 1 | push / PR | `cdd-kit validate --contracts` — contract-driven-gates / contract-and-fast-tests | merge |
| change-gate | 1 | push / PR | `cdd-kit gate settings-page-cloud-redesign` — contract-driven-gates / contract-and-fast-tests | merge |
| openapi-sync | 1 | push / PR | `cdd-kit openapi export --check --out contracts/api/openapi.yml` — contract-driven-gates / contract-and-fast-tests | merge |
| secret-scan | 1 | push / PR | grep for literal API keys in source — contract-driven-gates / contract-and-fast-tests | merge |
| targeted-tests | 1 | push / PR | `pytest tests/test_providers_api.py tests/test_provider_fallback.py -x -q --tb=short` — contract-driven-gates / contract-and-fast-tests | merge |
| full-suite | 1 | push / PR | `pytest tests/ -x -q --tb=short --junitxml=test-results/junit.xml` — contract-driven-gates / contract-and-fast-tests | merge |

## Informational Gates (non-blocking)

| gate | tier | command / workflow | when |
|---|---:|---|---|
| key-not-persisted | 2 | `grep -r "deepseek_api_key" app/backend/api/routes.py \| grep -v "deepseek_api_key:" \| grep -v "req.deepseek_api_key" \| grep -v '"deepseek_api_key"' \| grep -v "#"` — expect no output; covered by test-plan.md row AC-7 (key not logged) | PR |
| frontend-e2e | 2 | `pytest app/frontend/src/pages/__tests__/SettingsPage.test.jsx` (or equivalent Jest runner) — covers AC-1, AC-2, AC-4, AC-5 from test-plan.md | PR |
| full-regression | 2 | `pytest tests/ -q --tb=short --junitxml=test-results/full-regression.xml` (contract-driven-gates / full-regression) | PR |

## Workflow Changes Applied

No new workflow file required. `settings-page-cloud-redesign` is Tier 2; the
existing `contract-driven-gates.yml` `contract-and-fast-tests` job runs
`cdd-kit gate <id>`, `openapi export --check`, and `pytest tests/` on every push
and PR. The comment line in the workflow's `Change gate` step must be updated
from `echo "No active change gates"` to:

```
cdd-kit gate settings-page-cloud-redesign
```

After merge and archive, revert that step to the `echo` no-op and add
`settings-page-cloud-redesign` to the `# Active change gates` comment header.

## Promotion Policy

All Tier 1 gates in `contract-and-fast-tests` must pass before the PR is
mergeable. `cdd-kit gate settings-page-cloud-redesign --strict` must report
green (no pending tasks). The `openapi-sync` gate requires that
`contracts/api/openapi.yml` was regenerated after backend route changes via
`cdd-kit openapi export --out contracts/api/openapi.yml` and committed.

## Rollback Policy

Three new endpoints are additive (no DDL, no breaking change to existing routes).
Rollback = revert the backend route/schema additions and the frontend rewrite
commits; existing endpoints and their contract rows are unchanged.

## Merge Eligibility

blocked — pending `cdd-kit gate settings-page-cloud-redesign` step active in
`.github/workflows/contract-driven-gates.yml` and confirmed green test-evidence.

