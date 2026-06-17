---
contract: data
summary: Data schema, invalid-data handling, and row-level compatibility rules.
owner: application-team
surface: data
schema-version: 0.2.0
last-changed: 2026-06-17
breaking-change-policy: deprecate-2-minors
---

# Data Shape Contract

## Required Columns

### JobStatus.status (server-set enum)
| column | type | nullable | allowed values | fallback | validation |
|---|---|---:|---|---|---|
| JobStatus.status | string | no | `queued`, `running`, `completed`, `stopped`, `failed` | `queued` (initial create) | Set only by JobManager state machine; never supplied by clients. |

### POST /api/jobs — multipart/form-data required fields
| column | type | nullable | allowed values | fallback | validation |
|---|---|---:|---|---|---|
| files | file[] | no | any supported extension | — | HTTP 400 if empty; accepted extensions: `.docx .doc .pptx .xlsx .xls .pdf` |
| targets | string | no | comma-separated language codes | — | HTTP 400 if none parse to non-empty after split |

## Optional Columns

### JobStatus / JobRecord — provider field (added in p1-cloud-providers)
| column | type | nullable | allowed values | fallback | validation |
|---|---|---:|---|---|---|
| provider | string | yes | any provider ID from `config/providers.yml` (e.g. `panjit`, `deepseek`, `ollama-local`) | null | Set by orchestrator only at point of successful provider call; never supplied by clients. Null for pre-existing jobs and Ollama-only jobs. Additive optional field — backward-compatible. |

See `contracts/api/api-contract.md > ## Schemas > JobStatus` for the authoritative full field table.

### POST /api/jobs — multipart/form-data optional fields
| column | type | default | notes |
|---|---|---|---|
| src_lang | string | None | source language; auto-detected if omitted |
| include_headers | bool | false | include document headers in translation |
| profile | string | None | manual model/profile override; bypasses auto-routing |
| num_ctx | int | None | LLM context window size; validated per BR-2 |
| pdf_output_format | string | "docx" | output format for PDF jobs: `"docx"` or `"pdf"` |
| pdf_layout_mode | string | "overlay" | PDF rendering mode: `"overlay"` or `"side_by_side"` |
| mode | string | "translation" | job mode: `"translation"` or `"extraction_only"` |

## Invalid Data Behavior
| condition | expected behavior | error code / UI state | test |
|---|---|---|---|
| missing required `files` | reject | HTTP 400 "No files uploaded" | — |
| missing required `targets` | reject | HTTP 400 "No target languages provided" | — |
| wrong type for `num_ctx` (non-int) | reject | HTTP 422 Pydantic validation | — |
| empty `files` list | reject | HTTP 400 "No files uploaded" | — |
| `num_ctx` out of range | reject | HTTP 422 range message (BR-2) | — |
| over max segment/text limit | not rejected at upload; job transitions to `status: "failed"` | job error field | — |
| unexpected `JobStatus.status` | n/a — status is server-set only, never client input | — | — |
| `provider` field set by client | ignored — field is server-set only; not in POST /api/jobs input schema | — | — |

## Export / Import Format

- **Job output**: zip archive downloaded via `GET /api/jobs/{id}/download`.
- **Term export**: `GET /api/terms/export?format={json|csv|xlsx}` — full term db or filtered by status.
- **Term import**: `POST /api/terms/import` — multipart file upload (`.json` or `.csv`); strategy controls merge behavior (BR-5).

## Row Limit / Truncation Policy

- In-memory job store capped at `MAX_JOBS_IN_MEMORY=100` (BR-8). When at capacity, oldest completed/failed jobs are evicted.
- Jobs expire after `JOB_TTL_HOURS=24` hours; cleanup runs every 30 minutes.
- Document segment/text size limits are effectively disabled (`MAX_SEGMENTS=10_000_000`, `MAX_TEXT_LENGTH=1_000_000_000`). See BR-10.
