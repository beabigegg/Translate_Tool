---
change-id: p1-contract-baseline
schema-version: 0.1.0
last-changed: 2026-06-17
risk: low
tier: 4
---

# Test Plan: p1-contract-baseline

This is a contracts-only documentation change. No production code and no new
test code are added. The only meaningful verification is contract conformance.

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 (inventory lists every route) | contract | cdd-kit validate --contracts | 4 |
| AC-2 (auth policy recorded) | contract | cdd-kit validate --contracts | 4 |
| AC-3 (JobStatus.status enum) | contract | cdd-kit validate --contracts | 4 |
| AC-4 (error payload + status codes) | contract | cdd-kit validate --contracts | 4 |
| AC-5 (multipart upload schema) | contract | cdd-kit validate --contracts | 4 |
| AC-6 (rule inventory + decision table) | contract | cdd-kit validate --contracts | 4 |
| AC-7 (validate passes, zero drift) | contract | cdd-kit validate --contracts | 4 |
| AC-8 (no out-of-scope file changed) | contract | cdd-kit gate p1-contract-baseline | 4 |

## Test Families Required

- contract: REQUIRED — `cdd-kit validate --contracts` must pass after the five contracts are filled.
- unit / integration / e2e / data-boundary / resilience / monkey / stress / soak: OUT OF SCOPE (see Out of Scope).

## Test Execution Ladder

| phase | required | command source | max failures | result artifact |
|---|---:|---|---:|---|
| collect | yes | cdd-kit test select | 1 | test-runs/<run-id>/summary.json |
| targeted | yes | cdd-kit test select | 1 | test-evidence.yml |
| changed-area | yes | cdd-kit test select | 1 | test-evidence.yml |
| contract | yes | cdd-kit validate --contracts | 1 | test-evidence.yml |
| quality | n/a | — | — | — |
| full | n/a (no code) | — | — | — |

## Test Update Contract

The approved place to record that an existing test must change because the
accepted spec or contract changed. This is not a waiver: a still-valid test that
fails must be fixed, not relisted here.

| existing test | action | reason |
|---|---|---|
| (none) | — | no existing test changes behavior in this docs-only change |

## Stop Rules

- Do not run broad pytest before targeted and changed-area phases pass.
- Do not investigate more than the first failure per phase.
- Do not classify any failure as known, pre-existing, waived, or allowed.
- If full suite fails, record the first failure and block the gate.

## Out of Scope

- unit: no code written.
- integration: no service interaction changed.
- e2e: no user-facing flow changed.
- data-boundary: no runtime data path changed (size limits documented, not modified).
- resilience / monkey: no interactive or failure surface changed.
- stress / soak: no load or long-running surface changed.

## Notes

- `.cdd/conformance.json` is currently `enabled:false`, so `cdd-kit validate --contracts` checks contract-file structure, not live route-vs-contract drift. Route accuracy was verified manually against `app/backend/api/routes.py` during planning.
