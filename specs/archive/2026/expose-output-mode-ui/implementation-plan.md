---
change-id: expose-output-mode-ui
schema-version: 0.1.0
last-changed: 2026-06-27
---

# Implementation Plan: expose-output-mode-ui

## Objective

Add a user-visible output-mode selector to `TranslatePage` step 2 with exactly two
choices — `append` ("原文在下方") and `replace` ("原地取代/覆蓋原文") — defaulting to
`append`, and append the chosen value to the translation-start `FormData` as the
field `output_mode`. Stand up a frontend test runner (vitest) and ship the
component test file proving AC-1..AC-3. No backend, contract, or API-client
signature changes.

## Execution Scope

### In Scope
- Add `outputMode` state (default `'append'`) + `SET_OUTPUT_MODE` reducer case to `TranslatePage.jsx`.
- Render a two-option selector in step 2 (`step === 2`), gated on `jobMode === 'translate'`.
- In `handleSubmit`, `form.append('output_mode', outputMode)` before `createJob(form)`.
- Add vitest + Testing Library devDependencies and a `"test"` script to `app/frontend/package.json`.
- Add the vitest jsdom config (`test` block in `app/frontend/vite.config.js`) and a setup file if needed.
- Author `app/frontend/src/pages/TranslatePage.test.jsx` (three tests named in test-plan.md).

### Out of Scope
- Any backend change. `app/backend/api/schemas.py` `OutputMode` enum (`append`/`replace`) and the route's `output_mode` Form param/default are unchanged (AC-5).
- Any edit to `contracts/` — all referenced contracts are verify-only (see Contract Updates).
- LocalStorage persistence of the selection (non-goal).
- Per-segment / per-paragraph mode selection (non-goal).
- Changing the `createJob` signature — it already forwards arbitrary `FormData` fields (`app/frontend/src/api/jobs.js:2`); do not modify it.
- E2E/browser harness, visual/regression automation.

## Required Changes

| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | frontend state | Add `outputMode: 'append'` to `initialState`; add `SET_OUTPUT_MODE` reducer case; destructure `outputMode` from state. | frontend-engineer |
| IP-2 | frontend UI | Render a two-option selector ("原文在下方"→`append`, "原地取代/覆蓋原文"→`replace`) in step 2 right column, shown only when `jobMode === 'translate'`. | frontend-engineer |
| IP-3 | frontend wiring | In `handleSubmit`, add `form.append('output_mode', outputMode)`. | frontend-engineer |
| IP-4 | test infra | Add vitest/jsdom/Testing Library devDeps + `"test"` script to `package.json`; add vitest jsdom config. | frontend-engineer |
| IP-5 | test file | Write `TranslatePage.test.jsx` with the three named tests (AC-1..AC-3). | frontend-engineer (owns; see Ordering) |

## Source Artifact Pointers

| source | relevant pointer | used for |
|---|---|---|
| change-classification.md | § Inferred Acceptance Criteria (AC-1..AC-5) | scope + behavior |
| change-classification.md | § Required Contracts (all verify-only) | confirms no contract edits |
| test-plan.md | § Acceptance Criteria → Test Mapping; § "Test function names" | test file path + required test names |
| test-plan.md | § Notes | runner deps, mock boundary, SettingsContext wrap |
| test-plan.md | § Test Execution Ladder | phase commands |
| ci-gates.md | § Required Gates for This Change | verification gates/commands |
| contracts/css/css-contract.md | TranslatePage row + Forbidden Practices | token-only styling rule |
| app/backend/api/schemas.py | `OutputMode` enum lines 11-13 | exact values `append`/`replace` (read-only) |

## File-Level Plan

| path or glob | action | notes |
|---|---|---|
| `app/frontend/src/pages/TranslatePage.jsx` | edit | (1) Add `outputMode: 'append'` to `initialState` (~line 26-39). (2) Add `case 'SET_OUTPUT_MODE': return { ...state, outputMode: action.payload };` to reducer (~line 55-78). (3) Add `outputMode` to the destructure at line 88. (4) Render selector in `step-2-right` (after the profile `Select`, ~line 198), gated on `jobMode === 'translate'`. (5) In `handleSubmit` (~line 116-128), add `form.append('output_mode', outputMode);` before `await createJob(form)`. |
| `app/frontend/src/api/jobs.js` | no change | `createJob` already forwards arbitrary FormData; verify only. |
| `app/frontend/package.json` | edit | Add devDeps + `"test"` script (see Test Infrastructure). Path is OUTSIDE current Allowed Paths — see Known Risks / CER-001. |
| `app/frontend/vite.config.js` | edit | Add a `test` block (jsdom env) so vitest reuses the existing `@vitejs/plugin-react`. Path is OUTSIDE current Allowed Paths — see Known Risks. |
| `app/frontend/src/pages/TranslatePage.test.jsx` | create | Three tests named in test-plan.md § "Test function names". |
| `app/backend/api/schemas.py` | read-only | Confirm `OutputMode` values `append`/`replace`; do not edit. |

### Selector implementation note (IP-2)
Recommended: reuse the already-imported `Select` component (`app/frontend/src/components/ui/Select.jsx`, used at lines 197-198) with
`label="輸出方式"`, `value={outputMode}`, `onChange={e => dispatch({ type: 'SET_OUTPUT_MODE', payload: e.target.value })}`,
and `options={[{ value: 'append', label: '原文在下方' }, { value: 'replace', label: '原地取代/覆蓋原文' }]}`.
A token-styled radio group (matching the existing PDF-output group at lines 210-235) is an acceptable alternative.
Either way: exactly two options, values exactly `append`/`replace`, labels exactly the two Chinese strings above. Labels are hardcoded Chinese consistent with the rest of this page (no i18n indirection — the page uses inline Chinese strings throughout).

## Contract Updates

- API: none — `output_mode` (append/replace, default append) already exists at the route; verify-only per change-classification.md § Required Contracts. Do not touch `contracts/api/api-contract.md` or `openapi.yml`.
- CSS/UI: none — comply with `contracts/css/css-contract.md` (TranslatePage row: layout via CSS vars only; Forbidden Practices: no hardcoded hex/px when a token exists). Use `var(--...)` tokens, matching existing inline-style usage on this page.
- Env: none.
- Data shape: none.
- Business logic: none — append/replace behavior already in `contracts/business/business-rules.md`; verify-only.
- CI/CD: gates already authored in ci-gates.md; no new workflow authoring by implementation agents.

## Test Infrastructure (IP-4)

`app/frontend/package.json` — add to `devDependencies` (test-strategist confirmed none present today):
- `vitest`
- `jsdom`
- `@testing-library/react`
- `@testing-library/user-event`

Add script: `"test": "vitest run"` (so `npm test` runs once and exits — matches the ci-gates.md `cd app/frontend && npm test` gate).

vitest config — add a `test` block to the existing `app/frontend/vite.config.js` (reuses `@vitejs/plugin-react`):
- `environment: 'jsdom'`
- `globals: true`
- optional `setupFiles` only if `@testing-library/jest-dom` matchers are used (jest-dom is optional and not in the test-plan dep floor; plain vitest `expect` + Testing Library queries are sufficient).

## Test Execution Plan

Follow test-plan.md § Test Execution Ladder (collect → targeted → changed-area required floor; contract = backend regression guard; full = final). Implementation agents generate evidence with `cdd-kit test run`; the gate validates `test-evidence.yml`. Do not restate the full ladder here.

| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 | app/frontend/src/pages/TranslatePage.test.jsx | `test_output_mode_selector_renders_both_labeled_options`: exactly two options, values `append`/`replace`, labels "原文在下方"/"原地取代/覆蓋原文" present in step 2 |
| AC-2 | app/frontend/src/pages/TranslatePage.test.jsx | `test_output_mode_default_value_is_append`: selector initial value `"append"` with no interaction |
| AC-3 | app/frontend/src/pages/TranslatePage.test.jsx | `test_output_mode_replace_appends_field_to_form_data`: after selecting `replace` and submitting, mocked `createJob` received `FormData` whose `.get('output_mode') === 'replace'` |
| AC-4 | agent-log/visual-reviewer.yml; agent-log/ui-ux-reviewer.yml | manual: control visible before job start, CSS token compliance — no automated assertion |
| AC-5 | tests/test_output_mode_api.py | backend regression guard re-run green; field/default unchanged |

## Constraints

- Styling: CSS contract tokens only (`var(--...)`); no hardcoded hex/px when a token exists (`contracts/css/css-contract.md` Forbidden Practices). Match existing inline-style token usage on the page.
- Mock boundary: `vi.mock('../api/jobs.js')` to stub `createJob` at the module boundary; do NOT mock `fetch`.
- Render wrap: wrap the component under test in the `SettingsContext` provider (`app/frontend/src/contexts/SettingsContext.jsx`) so `useSettings()` does not throw; supply a minimal `profiles` value so the profile `Select` renders.
- Assertion pattern: assert on the `FormData` argument passed to the mocked `createJob` via `formData.get('output_mode')` (do not stringify the whole body).
- Exact strings: field name exactly `output_mode`; values exactly `append`/`replace`; labels exactly the two Chinese strings in IP-2.
- Do not change `createJob`'s signature or `app/frontend/src/api/jobs.js`.

## Ordering

1. frontend-engineer implements IP-1..IP-5 **and writes the test file** (`TranslatePage.test.jsx`). Because the assertions depend on component internals (the chosen selector control, the `output_mode` FormData wiring, and the `SettingsContext` render wrap), the test file is part of frontend-engineer's scope, not a separate authoring pass. test-strategist already defined the AC→test mapping and the three test names in test-plan.md; frontend-engineer implements those exact names.
2. test-strategist verifies the delivered tests match the AC→test mapping and mock boundary (review, not re-author).
3. ui-ux-reviewer → visual-reviewer → contract-reviewer (read-only confirm `output_mode` in API + business contracts) → qa-reviewer, per change-classification.md § Required Agents.

## Handoff Constraints

- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved.

## Known Risks

- **CER-001 pending / read-scope gap (blocking for frontend-engineer).** `app/frontend/package.json` and `app/frontend/vite.config.js` (the vitest config target) are NOT in context-manifest.md § Allowed Paths, and CER-001 (which requests `app/frontend/package.json` and `app/frontend/src/**/__tests__/`) is still `status: pending`. frontend-engineer cannot add the test runner without these. Action: approve/extend the manifest to include `app/frontend/package.json` and `app/frontend/vite.config.js` (run `cdd-kit context approve expose-output-mode-ui CER-001` and add `vite.config.js`) BEFORE frontend-engineer starts. The test file lives at `app/frontend/src/pages/TranslatePage.test.jsx`, which is already within the allowed `app/frontend/src/` packet.
- `output_mode` is consumed by the backend as a route Form param (confirmed by tests/test_output_mode_api.py), not a Pydantic field in schemas.py — so only the FormData key name matters; the frontend change is sufficient and no schema edit is needed.
- Selector must be reachable only in the translate flow: gate on `jobMode === 'translate'` so it does not appear (or submit) in `extraction_only` mode.
- Code-map note: `.cdd/code-map.yml` is current (generated 2026-06-27, cdd-kit 3.6.0); line ranges above were taken from it and the live file and may shift by a few lines after edits.
