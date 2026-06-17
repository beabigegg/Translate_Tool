# Gate Policy

## Tier 0 — Local Fast Gate

Run before PR where practical.

- lint
- typecheck
- targeted unit tests
- contract validation
- changed-area tests

## Tier 1 — PR Required Gate

Blocks merge.

- build
- unit tests
- API/CSS/env/data contract checks when affected
- critical integration tests
- critical E2E tests for user-visible flows
- data-boundary or fuzz tests for changed input surfaces

## Tier 2 — PR Informational Gate

Runs on PR but does not block until stable.

- visual regression
- real-infra smoke
- extended E2E
- flaky candidate hardening tests

## Tier 3 — Nightly Real-Infra Gate

- real DB/cache/storage/queue integration
- driver timeout and failover
- race condition tests
- production-like env validation

## Tier 4 — Weekly Soak / Stress Gate

- long-running auto-refresh
- report concurrency
- cache TTL stability
- pool stability
- memory/temp growth

## Tier 5 — Manual Production-like Dispatch Gate

- release candidate verification
- large data or special operational scenarios
