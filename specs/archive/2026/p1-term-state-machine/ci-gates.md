---
change-id: p1-term-state-machine
schema-version: 0.1.0
last-changed: 2026-06-18
tier: 2
---

# CI/CD Gate Review — p1-term-state-machine

## Required Gates for This Change

| gate | tier | required | trigger | command / workflow | artifact |
|---|---:|---:|---|---|---|
| contract-validate | 1 | yes | PR / push | `cdd-kit validate --contracts` (job: `contract-and-fast-tests`) | junit.xml (14 days) |
| pytest full suite | 1 | yes | PR / push | `pytest tests/ -x -q --tb=short` (job: `contract-and-fast-tests`) | junit.xml (14 days) |
| full regression | 2 | yes (PR only) | pull_request | `pytest tests/ -q --tb=short` (job: `full-regression`) | full-regression.xml (14 days) |
| openapi export check | 1 | yes | PR / push | `cdd-kit openapi export --check` (job: `contract-and-fast-tests`) | — |
| test-evidence presence | 1 | yes (pre-merge) | local | `ls specs/changes/p1-term-state-machine/test-evidence.yml` | test-evidence.yml |

## Workflow Changes Applied

None. The existing `.github/workflows/contract-driven-gates.yml` already covers all required gates via `contract-and-fast-tests` (Tier 1) and `full-regression` (Tier 2). No new job, step, or workflow file is needed.

> Note: the `openapi export --check` gate is already in CI via the `contract-and-fast-tests` job. Adding `POST /terms/reject` and `POST /terms/flag-needs-review` to `contracts/api/api-contract.md` requires regenerating `contracts/api/openapi.yml` via `cdd-kit openapi export --out contracts/api/openapi.yml` — commit the updated `openapi.yml` or the check gate will fail.

## What Is Not Required

- **New migration step** — `Term.status` column is already `TEXT`; only status values expand. No `ALTER TABLE` needed.
- **Nightly / weekly gates** — no load or soak coverage at Tier 2.
- **E2E gate** — no frontend surface; API-level integration test in `test_term_state_machine.py::test_reject_and_flag_api_endpoints` covers the round-trip.

## Promotion Policy

- All 8 tests in `tests/test_term_state_machine.py` must pass (AC-1..AC-8).
- `pytest -q --tb=short` must report **389+ passed** (baseline AC-8) before merge.
- `cdd-kit validate --contracts` must exit 0 (includes business-rules, env, api, data-shape contracts updated in IP-11).
- `cdd-kit openapi export --check` must exit 0 (requires `openapi.yml` committed with new endpoints).
- `test-evidence.yml` must exist with all phases in `test-plan.md §Test Execution Ladder` marked passed.

## Rollback Policy

Revert the backend-engineer commit(s) touching `term_db.py`, `term_extractor.py`, `config.py`, `schemas.py`, `routes.py`, and `models/term.py`. Rollback the contract commits for business-rules, env, api, data-shape. No DB migration to undo (SQLite `status` column unchanged; existing data retains current string values). No env vars to remove (both new vars have safe defaults).

## Merge Eligibility

**blocked** until:
1. `contract-and-fast-tests` job passes on the PR branch (contract-validate + pytest + openapi check).
2. `full-regression` job passes on the PR (389+ tests, 0 failures).
3. `test-evidence.yml` present with all phases passed.
4. `contracts/api/openapi.yml` committed and `openapi export --check` clean.
