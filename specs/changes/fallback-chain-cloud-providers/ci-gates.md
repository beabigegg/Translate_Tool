---
change-id: fallback-chain-cloud-providers
schema-version: 0.1.0
tier: 2
last-changed: 2026-06-20
---

# CI/CD Gate Review — fallback-chain-cloud-providers

## Required Gates for This Change

| gate name | tier | type | trigger | command / workflow |
|---|---:|---|---|---|
| contract-validation | 1 | required | push, pull_request | `cdd-kit validate --contracts` |
| env-schema-sync | 1 | required | push, pull_request | verify `DEEPSEEK_ENABLED` in `.env.example.template` + `env.schema.json` |
| targeted-tests | 1 | required | push, pull_request | `pytest tests/test_provider_fallback.py tests/test_env_contract.py -x -q --tb=short` |
| full-test-suite | 1 | required | push, pull_request | `pytest tests/ -x -q --tb=short --junitxml=test-results/junit.xml` |
| change-gate | 1 | required | local pre-PR; push, pull_request | `cdd-kit gate fallback-chain-cloud-providers` |

## Gate Rationale

**contract-validation** — `env-contract.md` gains `DEEPSEEK_ENABLED`; `business-rules.md` updates the fallback-chain rule. Both must pass `cdd-kit validate --contracts` before any other gate runs.

**env-schema-sync** — The Deployment Sync Policy (`env-contract.md §Deployment Sync Policy`) requires any new env var be added to `.env.example.template` and `env.schema.json` in the same change. This gate mechanically verifies `DEEPSEEK_ENABLED` is present in both files, catching drift before deploy. References: AC-4 in `change-classification.md`.

**targeted-tests** — Fast-fail gate covering AC-1, AC-3, AC-5, AC-6, AC-7, AC-8 at the orchestrator consumer seam:
- `tests/test_provider_fallback.py` — selection-style assertions: `ollama-local` never selected; DeepSeek excluded when `DEEPSEEK_ENABLED=false`; graceful failure when PANJIT fails and DeepSeek disabled.
- `tests/test_env_contract.py` — confirms `DEEPSEEK_ENABLED` schema entry; confirms `ollama-local` branch absent from orchestrator traversal.
Runs before the full suite to surface targeted failures fast. See `test-plan.md` AC rows.

**full-test-suite** — Non-regression across layout detection, renderer, chunking, QE, and terminology audit paths (AC-7 and global non-regression). Mirrors the existing `contract-and-fast-tests` pytest step.

**change-gate** — `cdd-kit gate` enforces tier-floor policy, contract completeness, and task-checklist state for this change. Must be green before PR is opened.

## Workflow Changes Applied

Modified `.github/workflows/contract-driven-gates.yml` — `contract-and-fast-tests` job:

1. **env-schema-sync step** (new, before full pytest): verifies `DEEPSEEK_ENABLED` appears in both `contracts/env/.env.example.template` and `contracts/env/env.schema.json`.
2. **targeted-tests step** (new, before full pytest): runs `tests/test_provider_fallback.py` and `tests/test_env_contract.py` with `-x` so targeted failures surface before the full suite runs.
3. **Change gate step** (updated): replaced `echo "No active change gates"` with `cdd-kit gate fallback-chain-cloud-providers`.

No new jobs, runners, or secrets are required. All new steps are inside the existing `contract-and-fast-tests` job. Artifact retention and concurrency settings are unchanged.

## Required Check Policy

The following job names bind to branch protection required-status-checks:

- `contract-and-fast-tests` (existing Tier 1 — blocks merge on all pushes and PRs)

No new job names are introduced; all new steps are inside the existing job.

## Informational Gate Promotion Policy

Existing Tier 2 informational jobs (`full-regression`, `golden-sample-regression`, `renderer-equivalence`, `text-expansion-benchmark`) run on PR and are unchanged. New failures in those jobs escalate to blocker per their existing workflow comments.

## Rollback Policy

`DEEPSEEK_ENABLED` defaults to `false`. Disabling DeepSeek post-deploy requires no code change — set `DEEPSEEK_ENABLED=false` and restart the backend. If an orchestrator regression is detected post-merge, revert the commit touching `orchestrator.py` and `config/providers.yml`; the `ollama-local` branch is restored. No DDL, no migration, no data-at-rest change — rollback is a deploy-only operation.

## Artifact Retention

Existing `test-results` artifact: 14-day retention (unchanged). No new artifact jobs introduced.

## Merge Eligibility Decision

**blocked** until all five required gates are green (`contract-validation`, `env-schema-sync`, `targeted-tests`, `full-test-suite`, `change-gate`).

## Notes

Reference `test-plan.md` AC rows and `change-classification.md §Inferred Acceptance Criteria` for full test scope. This file records gate policy only.
