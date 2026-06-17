---
change-id: <id>
schema-version: 0.1.0
last-changed: <date>
risk: low | medium | high
tier: 0 | 1 | 2 | 3 | 4 | 5
---

# Test Plan: <change-id>

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | unit | tests/unit/test_xxx.py | 0 |

## Test Families Required

Mark all that apply: unit / contract / integration / e2e / data-boundary / resilience / monkey / stress / soak

## Test Execution Ladder

| phase | required | command source | max failures | result artifact |
|---|---:|---|---:|---|
| collect | yes | cdd-kit test select | 1 | test-runs/<run-id>/summary.json |
| targeted | yes | cdd-kit test select | 1 | test-evidence.yml |
| changed-area | yes | cdd-kit test select | 1 | test-evidence.yml |
| contract | if affected | cdd-kit validate | 1 | test-evidence.yml |
| quality | if configured | ci-gates.md | 1 | test-evidence.yml |
| full | final/CI | cdd-kit test run --phase full | 1 | test-evidence.yml |

## Test Update Contract

The approved place to record that an existing test must change because the
accepted spec or contract changed. This is not a waiver: a still-valid test that
fails must be fixed, not relisted here.

| existing test | action | reason |
|---|---|---|
| tests/example/test_old_behavior.py::test_legacy_case | update | expected behavior changed by AC-2 |
| tests/example/test_removed_behavior.py::test_removed_case | delete | behavior removed by accepted contract/spec change |

## Stop Rules

- Do not run broad pytest before targeted and changed-area phases pass.
- Do not investigate more than the first failure per phase.
- Do not classify any failure as known, pre-existing, waived, or allowed.
- If full suite fails, record the first failure and block the gate.

## Out of Scope

## Notes

(Keep this section under 10 lines. Implementation detail belongs in the test files themselves. Do not repeat full implementation-plan or CI-gate content here.)
