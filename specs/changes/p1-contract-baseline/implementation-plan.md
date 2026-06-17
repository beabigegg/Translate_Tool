---
change-id: p1-contract-baseline
schema-version: 0.1.0
last-changed: 2026-06-17
---

# Implementation Plan: p1-contract-baseline

## Objective
Fill the empty sections of five contract files so they document the CURRENT, already-implemented backend behavior, enabling `cdd-kit validate --contracts` to act as a baseline for four downstream P1 changes. No production code is written; the only write targets are the five `contracts/*.md` files.

## Execution Scope

### In Scope
- Fill empty sections in `contracts/api/api-contract.md` (API Style, Error Format, Compatibility/Inventory/Breaking-Change policies).
- Fill `contracts/api/api-inventory.md` endpoint table (21 routes under `/api` prefix).
- Fill `contracts/api/error-format.md` (real FastAPI error shape + status codes).
- Fill `contracts/business/business-rules.md` (rule inventory + >=2 decision tables).
- Fill `contracts/data/data-shape-contract.md` (`JobStatus.status` enum + multipart upload schema).

### Out of Scope
- Any backend/frontend code change (downstream changes own behavior).
- `contracts/env/env-contract.md` (owned by p1-cloud-providers).
- OpenAPI/JSON-schema automation (owned by p1-observability-metrics).
- Flipping `.cdd/conformance.json` `enabled` flag.
- Inventing behavior not present in the read source files.

## Required Changes
| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | contracts/api/api-contract.md | fill 5 empty trailing sections (style/error/policies) | main-claude |
| IP-2 | contracts/api/api-inventory.md | fill 21-row endpoint inventory | main-claude |
| IP-3 | contracts/api/error-format.md | document FastAPI `{"detail":...}` shape + status table | main-claude |
| IP-4 | contracts/business/business-rules.md | rule inventory + 2 decision tables | main-claude |
| IP-5 | contracts/data/data-shape-contract.md | JobStatus.status enum + multipart `/jobs` schema | main-claude |

## Source Artifact Pointers
| source | relevant pointer | used for |
|---|---|---|
| app/backend/api/routes.py | lines 51-484 (all `@router` defs) | inventory, status codes, validation rules |
| app/backend/api/schemas.py | JobStatus 14-30; request models 58-97 | response/request field shapes |
| app/backend/services/job_manager.py | JobRecord.status 38; transitions 262/332/338 | JobStatus.status enum values |
| app/backend/utils/exceptions.py | lines 10-54 | document-size error semantics |
| app/backend/main.py | line 36 (`prefix="/api"`); 28-34 CORS | API prefix, auth/CORS posture |
| app/backend/config.py | 157-178 (limits, SUPPORTED_EXTENSIONS) | business-rule thresholds |
| test-plan.md | AC-1..AC-8 | verification mapping |
| ci-gates.md | contract gate row | verification command |

## File-Level Plan
| path | action | notes |
|---|---|---|
| contracts/api/api-contract.md | edit | endpoint table + schemas ALREADY present and correct — fill ONLY the 5 empty trailing sections |
| contracts/api/api-inventory.md | edit | fill endpoint table; categories already listed |
| contracts/api/error-format.md | edit | fill Error Codes table; adapt shape note to FastAPI `{"detail":...}` |
| contracts/business/business-rules.md | edit | fill Rule Inventory + Decision Tables |
| contracts/data/data-shape-contract.md | edit | repurpose generic headers for this API (not a tabular dataset) |

## Authoritative facts (from source — do not re-derive)
- API prefix: all routes mount under `/api` (main.py:36). Inventory/contract paths must include `/api`.
- Auth: NONE. No auth dependency on any route; CORS allows configured origins. Record: "API has no authentication; intentional local-tool design decision."
- Error shape: FastAPI default. `raise HTTPException(status_code=S, detail="msg")` -> body `{"detail":"msg"}`. Pydantic/Form/File validation failures -> 422 with `{"detail":[{loc,msg,type}]}` array.
- `JobStatus.status` enum (string): `queued` (init JobRecord:38) -> `running` (262) -> terminal `completed` (332) | `stopped` (332, on cancel) | `failed` (338, on exception). routes.py:209 treats `completed|stopped|failed` as terminal.
- Document size limits effectively disabled: MAX_SEGMENTS=10_000_000, MAX_TEXT_LENGTH=1_000_000_000 (config.py:157-158). `DocumentSizeLimitExceeded` raised inside processing -> job status `failed`, NOT a direct HTTP status.
- SUPPORTED_EXTENSIONS: .docx .doc .pptx .xlsx .xls .pdf (config.py:178).
- Job retention: MAX_JOBS_IN_MEMORY=100, JOB_TTL_HOURS=24, CLEANUP every 30 min (config.py:161-163).

## Status code inventory (verbatim from routes.py)
| endpoint | code | detail | line |
|---|---|---|---|
| POST /api/jobs | 400 | "No files uploaded" / "No target languages provided" | 115,119 |
| POST /api/jobs | 422 | "num_ctx must be a positive integer" / range message | 147,149 |
| GET /api/jobs/{id} | 404 | "Job not found" | 186 |
| POST /api/jobs/{id}/cancel | 404 | "Job not found" | 247 |
| GET /api/jobs/{id}/download | 404 | "Job not found" / "Output not ready" | 255,261 |
| GET /api/terms/export | 400 | "format must be json, csv, or xlsx" | 310 |
| GET /api/terms/export | 500 | str(exc) on export failure | 336 |
| POST /api/terms/import | 400 | strategy / file-type validation | 350,354 |
| POST /api/terms/import | 422 | str(exc) on import parse failure | 364 |
| POST /api/terms/approve | 404 | "Term not found" | 406 |
| PATCH /api/terms/edit | 404 | "Term not found" | 444 |

## CONTENT TO WRITE

### IP-1 — contracts/api/api-contract.md (fill ONLY the 5 empty trailing sections)
`## API Style`
- response style: JSON (Pydantic response models); binary endpoints return file streams (FileResponse).
- error style: FastAPI default — `{"detail": <string|array>}`; see error-format.md.
- auth style: none — API has no authentication; intentional local-tool design decision (no public network exposure expected).
- pagination style: none — list endpoints return full arrays (terms/profiles/models).
- date/time style: numeric epoch seconds / float durations in JobStatus; no ISO strings on the surface.

`## Error Format` — "See `contracts/api/error-format.md`. Handled errors use `raise HTTPException(status_code, detail)` -> `{\"detail\":\"...\"}`. Request-validation (Pydantic/`Form`/`File`) failures return 422 with FastAPI's structured `{\"detail\":[{loc,msg,type}]}`."

`## Compatibility Policy` — "All paths are prefixed `/api`. Endpoints, methods, and response schemas above are the compatibility surface. Removing/renaming a path or removing a required response field is breaking. Adding optional response fields or new endpoints is non-breaking."

`## Endpoint Inventory Policy` — "The endpoint table above plus `contracts/api/api-inventory.md` must list every route defined in `app/backend/api/routes.py`. Conformance (`.cdd/conformance.json`, currently `enabled:false`) can mechanically enforce this once enabled."

`## Breaking Change Policy` — "Per frontmatter `breaking-change-policy: deprecate-2-minors`. Breaking changes require updating this contract in the same change or the gate fails on drift."

### IP-2 — contracts/api/api-inventory.md (fill table; one row per route, prefix `/api`)
Owner = application-team, contract test = (none) for all. Rows (method | path | category | notes):
- GET /api/health | health-exception | liveness probe
- GET /api/models | standard-json | Ollama model list
- GET /api/profiles | standard-json | translation profiles
- GET /api/model-config | standard-json | per-model VRAM/ctx config
- GET /api/route-info | standard-json | query `targets` (csv)
- POST /api/jobs | file-upload-exception | multipart; creates job; 400/422
- GET /api/jobs/{job_id} | standard-json | job status; 404
- POST /api/jobs/{job_id}/cancel | standard-json | 404
- GET /api/jobs/{job_id}/download | stream-download-exception | zip; 404
- GET /api/stats | standard-json | job stats
- GET /api/cache/stats | standard-json | translation cache stats
- DELETE /api/cache | standard-json | query `model`
- GET /api/terms/stats | standard-json | term db stats
- GET /api/terms/export | stream-download-exception | query `format`,`status`; 400/500
- POST /api/terms/import | file-upload-exception | multipart; query `strategy`; 400/422
- GET /api/terms/unverified | standard-json | query `target_lang`,`domain`
- POST /api/terms/approve | standard-json | 404
- GET /api/terms/approved | standard-json | query `target_lang`,`domain`
- PATCH /api/terms/edit | standard-json | 404
- POST /api/terms/wikidata/search | standard-json | external Wikidata lookup
- POST /api/terms/wikidata/import | standard-json | insert lookup result (confidence 0.9, unverified)

### IP-3 — contracts/api/error-format.md (fill)
Replace the generic `{error:{...}}` shape note with the ACTUAL FastAPI shape:
- Handled errors: `{"detail": "<human message>"}` (HTTP status from `HTTPException`).
- Request validation errors: `{"detail": [{"loc":[...],"msg":"...","type":"..."}]}` at HTTP 422.
- No custom error envelope, no symbolic error `code`, no retry hints are emitted.
Error Codes table (status is the key; no symbolic codes exist):
| code | status | user-facing message | retryable | owner |
| (n/a) | 400 | "No files uploaded" / "No target languages provided" / "format must be json, csv, or xlsx" / "strategy must be skip, overwrite, merge, or force" / "Only .json and .csv files are supported" | no | application-team |
| (n/a) | 404 | "Job not found" / "Output not ready" / "Term not found" | no | application-team |
| (n/a) | 422 | "num_ctx must be a positive integer" / "num_ctx must be between {min} and {max}..." / import-parse error str / Pydantic validation array | no | application-team |
| (n/a) | 500 | term export failure str(exc) | no | application-team |
Note: in-job processing failures (incl. `DocumentSizeLimitExceeded`) are NOT HTTP errors — they surface via `GET /api/jobs/{id}` as `status:"failed"` with the `error` field set.

### IP-4 — contracts/business/business-rules.md (fill)
Rule Inventory (rule id | name | owner=application-team | current behavior | tests=(none)):
- BR-1 | auth-policy | No authentication on any endpoint; intentional local-tool design
- BR-2 | num_ctx-validation | If provided, must be >0 and within [min_num_ctx, max_num_ctx] of resolved model_type (VRAM_METADATA); else 422
- BR-3 | target-language-required | POST /jobs requires >=1 non-empty target after csv split; else 400
- BR-4 | model-auto-routing | targets grouped to benchmark-optimal model via resolve_route_groups; manual `profile` overrides to single group
- BR-5 | term-import-strategy | strategy in {skip, overwrite, merge, force}; force overwrites approved, others protect approved
- BR-6 | term-export-format | format in {json, csv, xlsx}; status filter in {approved, unverified, all/None}
- BR-7 | job-lifecycle | status queued->running->{completed|stopped|failed}; cancel sets stop_flag -> stopped
- BR-8 | job-retention | <=MAX_JOBS_IN_MEMORY(100) jobs; expire after JOB_TTL_HOURS(24); cleanup every 30 min
- BR-9 | supported-formats | .docx .doc .pptx .xlsx .xls .pdf; legacy .doc/.xls via LibreOffice/COM
- BR-10 | document-size-limits | MAX_SEGMENTS=10M, MAX_TEXT_LENGTH=1B (effectively disabled); breach -> job failed, not HTTP error
- BR-11 | wikidata-import-confidence | wikidata import inserts term with confidence=0.9, status="unverified", strategy="merge"
Decision Table A — num_ctx validation (condition | behavior | test id=(none)):
- num_ctx omitted (None) | accepted; model default used
- num_ctx <= 0 | 422 "num_ctx must be a positive integer"
- num_ctx outside [min,max] | 422 range message
- min <= num_ctx <= max | accepted
Decision Table B — term import strategy (condition | behavior | test id=(none)):
- strategy not in {skip,overwrite,merge,force} | 400
- strategy=skip | existing rows kept, only new inserted
- strategy=overwrite/merge | updates but protects already-approved rows
- strategy=force | overwrites everything incl. approved

### IP-5 — contracts/data/data-shape-contract.md (fill)
This API has no tabular dataset; repurpose generic headers for the two requested shapes.
`## Required Columns` — document `JobStatus.status` as an enum field:
| column | type | nullable | allowed values | fallback | validation |
| JobStatus.status | string | no | queued, running, completed, stopped, failed | queued (initial) | set only by JobManager state machine |
`## Optional Columns` — multipart upload request schema (POST /api/jobs, `multipart/form-data`):
| field | type | default | notes |
| files | file[] | (required) | one or more upload files; 400 if empty |
| targets | string | (required) | comma-separated target languages; 400 if none parse |
| src_lang | string | None | optional source language |
| include_headers | bool | false | |
| profile | string | None | manual model/profile override |
| num_ctx | int | None | validated per BR-2 |
| pdf_output_format | string | "docx" | "docx" or "pdf" |
| pdf_layout_mode | string | "overlay" | "overlay" or "side_by_side" |
| mode | string | "translation" | "translation" or "extraction_only" |
`## Invalid Data Behavior` — fill applicable rows:
- missing required column (files/targets) | reject | 400 "No files uploaded" / "No target languages provided" | (none)
- wrong type (num_ctx non-int) | reject | 422 Pydantic validation | (none)
- empty dataset (no files) | reject | 400 | (none)
- over max row limit | n/a — limits effectively disabled (BR-10); breach -> job status failed | (none)
- unexpected enum (status) | n/a — status is server-set only, never client input | (none)
`## Export / Import Format` — term DB export via GET /api/terms/export (json|csv|xlsx); import via POST /api/terms/import (.json|.csv). File jobs produce a zip archive downloaded via GET /api/jobs/{id}/download.
`## Row Limit / Truncation Policy` — Job memory capped at MAX_JOBS_IN_MEMORY=100 (capacity-based eviction); jobs expire after JOB_TTL_HOURS=24.

## Contract Updates
- API: api-contract.md (style/error/policy sections), api-inventory.md (21 routes), error-format.md (FastAPI shape + status table).
- CSS/UI: none.
- Env: none (non-goal).
- Data shape: data-shape-contract.md (JobStatus.status enum + multipart `/jobs` schema).
- Business logic: business-rules.md (11 rules, 2 decision tables) — documenting existing behavior only.
- CI/CD: none.

## Test Execution Plan
| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1..AC-6 (contract content correctness) | cdd-kit validate --contracts | passes, zero drift |
| AC-7 (validate passes) | cdd-kit validate --contracts | exit 0 |
| AC-8 (scope) | git status / cdd-kit gate p1-contract-baseline | only contracts/*.md changed |

Required test floor for this Tier-4 docs-only change: collect/targeted/changed-area produce no code tests; the only meaningful family is contract conformance. See test-plan.md.

## Handoff Constraints
- Implementation agents (main-claude) must not infer requirements from chat history; all content is inline above.
- Do not re-copy source code into contracts; record behavior only.
- `.cdd/conformance.json` is currently `enabled:false`; do NOT flip it in this change (out of declared scope). contract-reviewer may note whether enabling is warranted as a follow-up.
- Keep edits within the five listed files; any new file/path needs a Context Expansion Request.
- If a contract section cannot be filled from the read source, stop and report `blocked` rather than inventing.

## Known Risks
- `contracts/api/api-contract.md` endpoint table + schemas are ALREADY pre-filled and verified against routes.py/schemas.py; do NOT rewrite them — only fill the 5 trailing empty sections. Risk of duplication if treated as fully empty.
- Conformance gate is `enabled:false`, so `cdd-kit validate --contracts` will not mechanically diff routes vs contract; AC-7 verifies contract-file structural validity, not live route conformance. Route accuracy was verified manually against routes.py this change.
- Document-size limits are effectively disabled in config; contract must state this rather than imply enforcement.
