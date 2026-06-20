---
change-id: download-url-in-jobstatus
schema-version: 0.1.0
last-changed: 2026-06-20
---

# Implementation Plan: download-url-in-jobstatus

## Objective
After a translation job completes, `GET /jobs/{job_id}` must return a populated `download_url` so the already-correct frontend download button (`TranslatePage.jsx:173`) renders. Deliver this by (1) adding `download_url: Optional[str] = None` to the `JobStatus` response schema and (2) deriving the URL in the job-status response path when the job is completed and an output zip exists.

## Execution Scope

### In Scope
- Add `download_url` field to `JobStatus` (`app/backend/api/schemas.py`).
- Populate `download_url` in the `job_status` response builder (`app/backend/api/routes.py`) using the URL pattern `/api/jobs/{job_id}/download`.
- Add regression coverage (unit + contract/integration) per `test-plan.md`.
- Update `contracts/api/api-contract.md` JobStatus response schema and regenerate `contracts/api/openapi.yml` (and `openapi.json` if maintained).

### Out of Scope (non-goals — do not touch)
- Download endpoint `routes.py:339-350` (`GET /jobs/{job_id}/download`) — unchanged (AC-7).
- `app/frontend/src/pages/TranslatePage.jsx` — download logic already correct, no change (classification "Tasks Not Applicable" 4.2).
- Any other `JobStatus` field, progress math, QE/audit logic, or `JobRecord` dataclass shape (AC-5).
- No refactors of `job_manager.py` lifecycle, archiving, or threading.

## Required Changes
| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | backend schema | Add `download_url: Optional[str] = None` to `JobStatus` in `schemas.py` (place after `audit_hit_rate`; do not reorder existing fields) | bug-fix-engineer |
| IP-2 | backend route | In `routes.py::job_status`, derive `download_url` and pass it to the `JobStatus(...)` constructor | bug-fix-engineer |
| IP-3 | tests | Add unit test for derivation rule + contract/integration assertion that the field is present and correct | bug-fix-engineer |
| IP-4 | contract | Update `api-contract.md` JobStatus schema; regenerate `openapi.yml` | contract-reviewer (pre-impl) / bug-fix-engineer (regenerate after IP-1/IP-2) |

### Derivation rule (authoritative — AC-2, AC-3)
The change-request specifies setting the URL "when `output_zip` is set". The existing `job_status` builder already computes `output_ready = output_zip is not None and output_zip.exists()` (`routes.py:228`). Derive the URL from that signal so it stays consistent with `output_ready`:

```
download_url = f"/api/jobs/{job_id}/download" if (status == "completed" and output_ready) else None
```

Notes:
- Gate on `status == "completed"` AND `output_ready` (zip present on disk). Satisfies AC-2 (completed + output present → URL) and AC-3 (otherwise None).
- Build the URL in `routes.py` (response path), not in `job_manager.py`: the route already holds `job_id`, `status`, and `output_ready`, and the `/api/...` path prefix is an HTTP concern. This keeps `JobRecord` unchanged (AC-5) and avoids request-context coupling.

## Source Artifact Pointers
| source | relevant pointer | used for |
|---|---|---|
| change-classification.md | AC-1..AC-7; Required Tests (unit/contract/integration) | scope, acceptance, owner map |
| change-request.md | "修法" steps 1-2; Non-goals | exact fix + non-goals |
| context-manifest.md | Allowed Paths; CER-001 (response-samples.json) | read boundary; contract-sample risk |
| test-plan.md | Acceptance Criteria → Test Mapping; Test Execution Ladder | tests to run/write |
| ci-gates.md | Required Gates (lint, build, unit, contract) | verification gates |
| contracts/api/api-contract.md | JobStatus response schema | field addition + openapi regen |

## File-Level Plan
| path or glob | action | notes |
|---|---|---|
| app/backend/api/schemas.py | edit | Add `download_url: Optional[str] = None` to `JobStatus` (after `audit_hit_rate`, ~line 33). No other field changes. |
| app/backend/api/routes.py | edit | In `job_status` (204-281): after `output_ready` (line 228) compute `download_url` per derivation rule; add `download_url=download_url` to the `JobStatus(...)` return (261-281). Do NOT modify the `/download` endpoint (339-350). |
| tests/test_provider_fallback.py::TestJobStatusShape (extend) and/or tests/test_jobstatus_download_url.py (new) | add | Regression tests for IP-3; follow the existing `JobStatus(...)` construction pattern at tests/test_provider_fallback.py:251-273. |
| contracts/api/api-contract.md | edit | Add `download_url` (optional string) to JobStatus response schema. |
| contracts/api/openapi.yml | regenerate | Run `cdd-kit openapi export --out contracts/api/openapi.yml` after IP-1/IP-2. |
| tests/contract/response-samples.json | conditional | Only if CER-001 confirms a JobStatus sample exists that must carry the new field; otherwise leave unchanged. |

## Contract Updates
- API: `JobStatus` response gains optional `download_url: string|null`. Update `contracts/api/api-contract.md`, then regenerate `contracts/api/openapi.yml` (and `openapi.json` if maintained) via `cdd-kit openapi export`. Endpoint set/paths otherwise unchanged.
- CSS/UI: none.
- Env: none.
- Data shape: none (`JobRecord` unchanged; field is response-only).
- Business logic: derivation rule captured above (AC-2/AC-3); no separate business-logic contract file required (classification marks it optional).
- CI/CD: none (no gate changes).

## Test Execution Plan
| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 (field declared) | tests/test_provider_fallback.py::TestJobStatusShape | `JobStatus(download_url=...)` constructs; default None |
| AC-2 (completed + zip → URL) | tests/test_jobstatus_download_url.py | response `download_url == "/api/jobs/{job_id}/download"` for a completed job with an existing zip |
| AC-3 (otherwise None) | tests/test_jobstatus_download_url.py | `download_url is None` when status != completed or zip absent |
| AC-4 (GET payload correct) | tests/test_jobstatus_download_url.py | payload from `GET /jobs/{id}` carries correct `download_url` for completed job |
| AC-5 (no field dropped) | tests/test_provider_fallback.py | existing JobStatus/job-status tests stay green |
| AC-6 (contract in sync) | cdd-kit validate | openapi matches api-contract; no drift |
| AC-7 (download endpoint unchanged) | tests/test_provider_fallback.py | no edits to routes.py:339-350 (diff review) |

(The selector reads the `test file / command` column. The targets above are bare node-id/file paths or directories; required floor: collect, targeted, changed-area — full ladder in test-plan.md / references/sdd-tdd-policy.md.)

Execution ladder (run via `cdd-kit test select` then `cdd-kit test run`):
- Required floor: `collect`, `targeted`, `changed-area`.
- `contract`: required here — API contract changed; run `cdd-kit validate` and confirm openapi is regenerated and in sync.
- `full`: final/CI per `test-plan.md`.

Post-implementation step (do not skip): regenerate the OpenAPI artifact —
`cdd-kit openapi export --out contracts/api/openapi.yml` — and commit it; the CI `openapi export --check` gate fails on a stale file.

## Handoff Constraints
- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved.
- CER-001 (response-samples.json) is still `pending`. If a JobStatus response sample exists and must be updated, do not edit it until the CER is approved; otherwise leave the sample untouched and proceed.

## Known Risks
- Placing derivation in `routes.py` keeps `download_url` consistent with `output_ready`. If a reviewer insists the URL be stored on `JobRecord` in `job_manager.py` (literal reading of the request text), that requires a `JobRecord` field add — flag it before doing so since it adds lifecycle state; the current plan intentionally avoids it.
- The derived URL must be the literal `/api/jobs/{job_id}/download` to match the frontend `href`. Confirm the router mount prefix (`/api`) is in effect before finalizing the literal string; if the app mounts the router at a different prefix, align the literal accordingly.
- `test-plan.md` and `ci-gates.md` are still scaffolds at plan time; their concrete rows are owned by `test-strategist` / `ci-cd-gatekeeper` and must be filled before the gate runs.
- `.cdd/code-map.yml` was not consulted (small, fully line-scoped change with exact pointers already supplied); if a precise symbol index is needed later, run `cdd-kit code-map`.
