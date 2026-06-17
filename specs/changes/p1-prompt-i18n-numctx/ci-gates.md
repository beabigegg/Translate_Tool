---
change-id: p1-prompt-i18n-numctx
schema-version: 0.1.0
last-changed: 2026-06-17
tier: 3
---

# CI/CD Gate Plan — p1-prompt-i18n-numctx

## Required Gates for This Change

| gate | tier | required | trigger | command / workflow | artifact |
|---|---:|---:|---|---|---|
| contract-validate | 1 | yes | PR / push | `cdd-kit validate --contracts` (job: `contract-and-fast-tests`) | junit.xml (14 days) |
| pytest full suite | 1 | yes | PR / push | `pytest tests/ -x -q --tb=short` (job: `contract-and-fast-tests`) | junit.xml (14 days) |
| full regression | 2 | yes (PR only) | pull_request | `pytest tests/ -q --tb=short` (job: `full-regression`) | full-regression.xml (14 days) |
| test-evidence presence | 1 | yes (pre-merge) | local | `ls specs/changes/p1-prompt-i18n-numctx/test-evidence.yml` | test-evidence.yml |

## New Workflow Changes

None. Existing `.github/workflows/contract-driven-gates.yml` covers all required gates via the `contract-and-fast-tests` job (Tier 1) and the `full-regression` job (Tier 2). No new job or step is needed.

## What Is Not Required

- **openapi.yml regeneration** — no API route or response schema changes.
- **Migration** — no DB schema changes.
- **Tier 0/1 new target** — existing `pytest` invocation covers new tests in `tests/test_context_prompt_i18n.py`.

## Promotion Policy

- All 7 unit tests in `tests/test_context_prompt_i18n.py` must pass (AC-1..AC-7).
- `cdd-kit validate --contracts` must exit 0 with the updated `env.schema.json` (AC-8).
- `pytest --tb=short -q` must report **396+ passed** (396-test baseline) before merge.
- `test-evidence.yml` must exist with all phases (collect, targeted, changed-area, contract, full) marked passed.

## Rollback Policy

Revert the backend-engineer commit touching `orchestrator.py`, `translation_service.py`, `config.py`, and env contract files. No migration to undo. No new env var is required (GENERAL_NUM_CTX / TRANSLATION_NUM_CTX are optional overrides).

## Merge Eligibility

**blocked** until:
1. `contract-and-fast-tests` job passes on the PR branch.
2. `full-regression` job passes on the PR.
3. `test-evidence.yml` present with all required phases passed.
4. 396+ test baseline confirmed in `full-regression` output.
