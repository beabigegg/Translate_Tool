# CI/CD Gate Plan

## Change ID
p1-provider-routing

## Required Gates for This Change
| gate | tier | required | trigger | command/workflow | artifact |
|---|---:|:---:|---|---|---|
| contract-validate | 1 | yes | pull_request, push | `cdd-kit validate --contracts` (job: `contract-and-fast-tests`) | none |
| secret-scan | 1 | yes | pull_request, push | `grep -rn -E "(PANJIT_API\|DEEPSEEK_API)\s*[:=]\s*[A-Za-z0-9+/]{20,}" --include="*.yml" ...` (job: `contract-and-fast-tests`) | none |
| routing-unit-tests | 1 | yes | pull_request, push | `pytest tests/test_model_router.py -x -q --tb=short` (job: `contract-and-fast-tests`) | `test-results/junit.xml` (14 days) |
| full-test-suite | 1 | yes | pull_request, push | `pytest tests/ -x -q --tb=short --junitxml=test-results/junit.xml` (job: `contract-and-fast-tests`) | `test-results/junit.xml` (14 days) |
| full-regression | 2 | informational | pull_request | `pytest tests/ -q --tb=short --junitxml=test-results/full-regression.xml` (job: `full-regression`) | `test-results/full-regression.xml` (14 days) |
| stress-soak | 4 | no | schedule (weekly), workflow_dispatch | job: `scheduled-stress-soak` — no targets configured for this change | none |

**Gates explicitly not required:**
- E2E browser tests: no UI surface (change-classification.md §Required Tests: E2E: none).
- Cloud provider smoke test: routing resolution is pure local config; no live API call is exercised by `resolve_route_groups()`.
- OpenAPI sync gate: no API endpoint additions or changes.

## Workflow Changes Applied

No new workflow file is required. The existing `.github/workflows/contract-driven-gates.yml` already covers all required gates for this change via the `contract-and-fast-tests` (Tier 1, blocks merge) and `full-regression` (Tier 2, informational) jobs.

One targeted update is required: the `cdd-kit gate` step in `contract-and-fast-tests` currently pins `p1-cloud-providers` as the change gate. It must be updated to include `p1-provider-routing`.

### Diff applied to `.github/workflows/contract-driven-gates.yml`

```yaml
# line 47 — was:
      - name: Change gate (Tier 1 — blocks merge)
        run: cdd-kit gate p1-cloud-providers

# replace with:
      - name: Change gate (Tier 1 — blocks merge)
        run: |
          cdd-kit gate p1-cloud-providers
          cdd-kit gate p1-provider-routing
```

The secret-scan pattern already covers `*.yml` files (which includes `config/providers.yml`) via the `--include="*.yml"` flag; no change to the scan step is needed.

## Required Check Policy

Branch-protection required status checks (must be listed by job `name`, not job id):

- `contract-and-fast-tests` — blocks merge; covers contract-validate, secret-scan, routing-unit-tests, and full-test-suite gates.

The `full-regression` job is informational (Tier 2); it must not be added to required status checks. A new failure in `full-regression` that is not present in `contract-and-fast-tests` must be investigated before merge and either fixed or recorded as a pre-existing baseline in `agent-log/qa-reviewer.yml` per CLAUDE.md qa-report policy.

## Promotion Policy

This change ships when:

1. `contract-and-fast-tests` passes on the PR branch (all Tier 1 gates green).
2. `full-regression` produces 0 new failures relative to `main` (Tier 2 informational check passes or any new failure is dispositioned).
3. `contracts/business/business-rules.md` schema-version is 0.3.0 and `cdd-kit validate --contracts` exits 0.
4. The `p1-provider-routing` gate (`cdd-kit gate p1-provider-routing`) exits 0.
5. PR is approved by at least one reviewer.

No deployment pipeline step is required; this is a local-tool backend change with no production cloud target.

## Rollback Policy

- Forward-fix preferred: the change is confined to `model_router.py` and `config/providers.yml`. A one-commit revert of those two files restores the prior hardcoded routing table.
- Automated rollback trigger: if `contract-and-fast-tests` fails on `main` after merge, revert the merge commit immediately; do not hotfix on `main`.
- `config/providers.yml` is application config (not a migration or schema DDL); no data-layer rollback is needed.
- The legacy `_OLLAMA_ROUTING_TABLE` path (BR-4, Table D row 4: `provider_config is None`) is preserved as a backward-compatible fallback, so partial rollback (config only) is also viable.

## Artifact Retention

| artifact | job | retention |
|---|---|---|
| `test-results/junit.xml` | `contract-and-fast-tests` | 14 days |
| `test-results/full-regression.xml` | `full-regression` | 14 days |

## Merge Eligibility

**mergeable** — all Tier 1 gates are covered by the existing `contract-and-fast-tests` job. No new required checks are introduced. The `full-regression` Tier 2 job is informational and does not block merge unless a new failure is found and undispositioned.

## Notes

- AC coverage reference: AC-1 through AC-7 are all exercised by `pytest tests/test_model_router.py`; see `test-plan.md` AC-to-test mapping.
- BR-18, BR-19, and Table D in `contracts/business/business-rules.md` (schema-version 0.3.0) are the contract artifacts validated by `cdd-kit validate --contracts`.
- The secret-scan gate satisfies BR-17 for `config/providers.yml` without a dedicated step change.
- Stress/soak (Tier 4) is not applicable per change-classification.md §Tasks Not Applicable 3.5.
