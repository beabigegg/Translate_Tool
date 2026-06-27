---
change-id: expose-output-mode-ui
schema-version: 0.1.0
last-changed: 2026-06-27
risk: low
tier: 0
---

# Test Plan: expose-output-mode-ui

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | unit | app/frontend/src/pages/TranslatePage.test.jsx | 0 |
| AC-2 | unit | app/frontend/src/pages/TranslatePage.test.jsx | 0 |
| AC-3 | unit | app/frontend/src/pages/TranslatePage.test.jsx | 0 |
| AC-4 | visual/manual | agent-log/visual-reviewer.yml (no automated assertion) | manual |
| AC-5 | contract | tests/test_output_mode_api.py | 0 |

### Test function names in `TranslatePage.test.jsx`

- `test_output_mode_selector_renders_both_labeled_options` — asserts exactly two options with values `append`/`replace` and correct Chinese labels appear in step 2 (AC-1)
- `test_output_mode_default_value_is_append` — asserts selector initial value is `"append"` before any user interaction (AC-2)
- `test_output_mode_replace_appends_field_to_form_data` — simulates selecting `replace`, submits, asserts mocked `createJob` received `FormData` with `output_mode === "replace"` (AC-3)

## Test Families Required

| family | tier | notes |
|---|---|---|
| unit | 0 | vitest + @testing-library/react; no test runner exists yet — implementation must add it |
| contract | 0 | existing `tests/test_output_mode_api.py` re-run as regression guard only; no new tests |
| visual/manual | manual | visual-reviewer + ui-ux-reviewer confirm CSS token compliance via agent-log evidence |

## Test Execution Ladder

| phase | required | command source | max failures | result artifact |
|---|---:|---|---:|---|
| collect | yes | `cd app/frontend && npx vitest run src/pages/TranslatePage.test.jsx` | 1 | test-runs/<run-id>/summary.json |
| targeted | yes | `cd app/frontend && npx vitest run src/pages/TranslatePage.test.jsx` | 1 | test-evidence.yml |
| changed-area | yes | `cd app/frontend && npx vitest run src/pages/TranslatePage.test.jsx` | 1 | test-evidence.yml |
| contract | if affected | `pytest tests/test_output_mode_api.py` | 1 | test-evidence.yml |
| quality | if configured | ci-gates.md | 1 | test-evidence.yml |
| full | final/CI | `pytest && cd app/frontend && npx vitest run` | 1 | test-evidence.yml |

## Test Update Contract

No existing tests require modification. `tests/test_output_mode_api.py` covers the backend field and is run only as a regression guard.

| existing test | action | reason |
|---|---|---|
| tests/test_output_mode_api.py | no change | backend `output_mode` field and defaults are unchanged per AC-5 |

## Stop Rules

- Do not run broad pytest before targeted and changed-area phases pass.
- Do not investigate more than the first failure per phase.
- Do not classify any failure as known, pre-existing, waived, or allowed.
- If full suite fails, record the first failure and block the gate.

## Out of Scope

- Backend tests — `tests/test_output_mode_api.py` already proves `OutputMode` enum and `POST /api/jobs` field acceptance.
- LocalStorage persistence of selected output mode (non-goal per change-classification.md).
- E2E / browser automation (no harness exists; low-risk UI-only change).
- Soak, stress, resilience, monkey tests.
- Per-segment or per-paragraph mode selection.

## Notes

No frontend test runner exists today (`package.json` has no vitest/jest). Implementation must add `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/user-event` as devDependencies and a `"test"` script before tests can be collected. Mock `createJob` at the module boundary (`vi.mock('../api/jobs.js')`); do not mock `fetch`. Wrap renders in `SettingsContext` provider to avoid context errors. AC-4 is verified by reviewer agent-logs, not by automated assertions. AC-5 is a no-op: the unchanged `tests/test_output_mode_api.py` baseline run serves as the guard.
