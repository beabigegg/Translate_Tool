# Change Request

## Original Request

Expose the `output_mode` parameter in the frontend UI so users can choose between append (原文在下) and replace (原地取代/覆蓋原文) translation modes. This is item 0.4 of the improvement plan.

## Business / User Goal

Users translating Office documents always receive the "append" output mode — translated text appended below the original. They cannot choose "replace" mode (in-place overwrite). The backend already accepts `output_mode: "append" | "replace"` in `TranslationRequest` but the frontend never sends it, so the capability is invisible to users.

## Non-goals

- No backend changes — `app/backend/api/schemas.py` already supports `output_mode`.
- No support for per-segment or per-paragraph mode selection.
- No persistence of the selection across sessions (localStorage is optional, not required).

## Constraints

- Output mode selector must be visible on the TranslatePage before the user starts a translation job.
- The selected value must appear in the translation API call payload as `output_mode`.
- Choices: `append` labeled "原文在下方" and `replace` labeled "原地取代/覆蓋原文".

## Known Context

- Backend: `app/backend/api/schemas.py` lines 11-13 — `TranslationRequest.output_mode` field, default `"append"`, valid values `"append"` / `"replace"`.
- Frontend: `app/frontend/src/pages/TranslatePage.jsx` lines 117-126 — starts translation API call, never sends `output_mode`.
- `grep "output_mode" app/frontend/src` returns 0 hits — field is completely absent from frontend.

## Observable Success Criterion

When a user selects "原地取代/覆蓋原文" and starts a translation, the network request payload contains `output_mode: "replace"`. When "原文在下方" is selected (or by default), the payload contains `output_mode: "append"`.

## Requested Delivery Date / Priority

High — part of Track A improvement plan.
