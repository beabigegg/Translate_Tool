---
contract: api
summary: API behavior, compatibility rules, and endpoint contract requirements.
owner: application-team
surface: api
schema-version: 0.6.0
last-changed: 2026-06-20
breaking-change-policy: deprecate-2-minors
---

# API Contract

## API Style
- response style: JSON (Pydantic response models); binary endpoints return file streams (FileResponse / StreamingResponse).
- error style: FastAPI default — `{"detail": "<string>"}` for handled errors; `{"detail": [{loc, msg, type}]}` for request-validation (422). See `contracts/api/error-format.md`.
- auth style: none — API has no authentication; intentional local-tool design decision (no public network exposure expected).
- pagination style: none — list endpoints return full arrays (terms, profiles, models).
- date/time style: numeric float seconds (`elapsed_seconds`, `eta_seconds`) and float progress ratios in JobStatus; no ISO date strings on the public surface.

## Endpoint Requirements
| method | path | auth | request schema | response schema | errors | tests |
|---|---|---|---|---|---|---|
| GET | /health | none | - | HealthResponse | - | tests/contract/ |
| GET | /models | none | - | ModelsResponse | - | tests/contract/ |
| GET | /profiles | none | - | ProfileItem[] | - | tests/contract/ |
| GET | /model-config | none | - | ModelConfigItem[] | - | tests/contract/ |
| GET | /route-info | none | - | RouteInfoResponse | - | tests/contract/ |
| POST | /jobs | none | multipart/form-data | JobCreateResponse | 400, 422 | tests/contract/ |
| GET | /jobs/{job_id} | none | - | JobStatus | 404 | tests/contract/ |
| POST | /jobs/{job_id}/cancel | none | - | - | 404 | tests/contract/ |
| GET | /jobs/{job_id}/download | none | - | file stream | 404 | tests/contract/ |
| GET | /stats | none | - | - | - | tests/contract/ |
| GET | /cache/stats | none | - | - | - | tests/contract/ |
| DELETE | /cache | none | - | - | - | tests/contract/ |
| GET | /terms/stats | none | - | TermStatsResponse | - | tests/contract/ |
| GET | /terms/export | none | - | file stream | - | tests/contract/ |
| POST | /terms/import | none | multipart/form-data | TermImportResult | 400, 422 | tests/contract/ |
| GET | /terms/unverified | none | - | TermItem[] | - | tests/contract/ |
| POST | /terms/approve | none | TermApproveRequest | - | 404 | tests/contract/ |
| POST | /terms/reject | none | TermRejectRequest | - | 404 | tests/contract/ |
| POST | /terms/flag-needs-review | none | TermRejectRequest | - | 404 | tests/contract/ |
| GET | /terms/approved | none | - | TermItem[] | - | tests/contract/ |
| PATCH | /terms/edit | none | TermEditRequest | - | 404 | tests/contract/ |
| POST | /terms/wikidata/search | none | WikidataSearchRequest | WikidataSearchResponse | 422 | tests/contract/ |
| POST | /terms/wikidata/import | none | WikidataImportRequest | - | 422 | tests/contract/ |
| GET | /api/metrics | none | - | MetricsResponse | - | tests/contract/ |
| GET | /jobs/{job_id}/quality | none | - | JobQualityResponse | 200 (status: available/pending/disabled/unavailable); 404 job not found | tests/contract/ |

## Schemas

<!--
Optional. Add named schemas here when request/response bodies should become
machine-typed in `cdd-kit openapi export`. Reference a schema by name in the
endpoint table's "request schema" / "response schema" cell (use `Name[]` for an
array). A schema is defined ONE of two ways — never both:

Tier A — a field table (preferred; readable, diffable):

### ExampleRequest
| field | type | required | format | notes |
|---|---|---|---|---|
| email | string | yes | email | login identity |
| status | enum(active, disabled) | no | | lifecycle state |
| owner | ExampleUser | no | | reference another schema by name |

Tier B — a raw JSON Schema, for shapes Tier A can't express (oneOf, etc.).
The fence MUST be tagged `json-schema` (NOT `json`) or export fails fast:

### ExampleEvent
```json-schema
{ "type": "object", "oneOf": [ { "required": ["createdAt"] }, { "required": ["deletedAt"] } ] }
```

Map/dict fields MUST use type `string` (not `object`) with a notes cell value of
"serialized as JSON map of <key> -> <value>". `cdd-kit openapi export` rejects
`object` with "unknown type" and fails the gate. See existing examples:
`by_target_lang`, `by_domain`, `by_status` in TermStatsResponse.
-->

### HealthResponse
| field | type | required | format | notes |
|---|---|---|---|---|
| status | string | yes |  | always 'ok' |

### ModelsResponse
| field | type | required | format | notes |
|---|---|---|---|---|
| models | string[] | yes |  | list of available Ollama model names |

### ProfileItem
| field | type | required | format | notes |
|---|---|---|---|---|
| id | string | yes |  |  |
| name | string | yes |  |  |
| description | string | yes |  |  |
| model_type | string | yes |  |  |

### ModelConfigItem
| field | type | required | format | notes |
|---|---|---|---|---|
| model_type | string | yes |  |  |
| model_size_gb | number | yes |  |  |
| kv_per_1k_ctx_gb | number | yes |  |  |
| default_num_ctx | integer | yes |  |  |
| min_num_ctx | integer | yes |  |  |
| max_num_ctx | integer | yes |  |  |

### RouteInfoEntry
| field | type | required | format | notes |
|---|---|---|---|---|
| target | string | yes |  | : |
| model | string | yes |  | : |
| profile_id | string | yes |  | : |
| model_type | string | yes |  | : |
| is_primary | boolean | yes |  | : |
| provider | string | no |  | provider ID used for this route group (e.g. panjit, deepseek, ollama-local); null if providers.yml absent or Ollama-only path |

### RouteInfoResponse
| field | type | required | format | notes |
|---|---|---|---|---|
| routes | RouteInfoEntry[] | yes |  |  |

### JobCreateResponse
| field | type | required | format | notes |
|---|---|---|---|---|
| job_id | string | yes |  |  |

### JobStatus
| field | type | required | format | notes |
|---|---|---|---|---|
| job_id | string | yes |  |  |
| status | string | yes |  |  |
| processed_files | integer | yes |  |  |
| total_files | integer | yes |  |  |
| error | string | no |  |  |
| output_ready | boolean | yes |  |  |
| current_file | string | no |  |  |
| segments_done | integer | no |  |  |
| segments_total | integer | no |  |  |
| file_segments_done | integer | no |  |  |
| file_segments_total | integer | no |  |  |
| elapsed_seconds | number | yes |  |  |
| overall_progress | number | yes |  |  |
| segments_per_second | number | yes |  |  |
| eta_seconds | number | no |  |  |
| term_summary | string | no |  | per-language/domain term extraction counts as JSON-serialized map; null when mode != extraction_only |
| provider | string | no |  | provider ID that successfully processed this job (e.g. panjit, deepseek); null if not yet determined |
| quality_score_avg | number | no |  | average COMET/xCOMET quality score across all blocks; null when QE disabled or job not complete; see BR-54 |
| audit_hit_rate | number | no |  | terminology audit hit rate 0.0-1.0; null when audit did not run or mode==extraction_only; see BR-59 |
| download_url | string | no |  | URL to download translated zip; set to /api/jobs/{job_id}/download only when status==completed AND output_zip exists on disk; null otherwise |

### TermStatsResponse
| field | type | required | format | notes |
|---|---|---|---|---|
| total | integer | yes |  |  |
| unverified | integer | yes |  |  |
| by_target_lang | string | yes |  | serialized as JSON map of lang -> count |
| by_domain | string | yes |  | serialized as JSON map of domain -> count |
| needs_review | integer | no |  | count of terms with status=needs_review; default 0 |
| approved | integer | no |  | count of terms with status=approved; default 0 |
| rejected | integer | no |  | count of terms with status=rejected; default 0 |
| by_status | string | no |  | serialized as JSON map of status -> count for all four statuses; default {} |

### TermItem
| field | type | required | format | notes |
|---|---|---|---|---|
| source_text | string | yes |  |  |
| target_text | string | yes |  |  |
| source_lang | string | yes |  |  |
| target_lang | string | yes |  |  |
| domain | string | yes |  |  |
| context_snippet | string | yes |  |  |
| confidence | number | yes |  |  |
| usage_count | integer | yes |  |  |
| status | string | yes |  |  |

### TermImportResult
| field | type | required | format | notes |
|---|---|---|---|---|
| inserted | integer | yes |  |  |
| skipped | integer | yes |  |  |
| overwritten | integer | yes |  |  |

### TermApproveRequest
| field | type | required | format | notes |
|---|---|---|---|---|
| source_text | string | yes |  |  |
| target_lang | string | yes |  |  |
| domain | string | yes |  |  |

### TermRejectRequest
| field | type | required | format | notes |
|---|---|---|---|---|
| source_text | string | yes |  |  |
| target_lang | string | yes |  |  |
| domain | string | yes |  |  |

### TermEditRequest
| field | type | required | format | notes |
|---|---|---|---|---|
| source_text | string | yes |  |  |
| target_lang | string | yes |  |  |
| domain | string | yes |  |  |
| target_text | string | yes |  |  |
| confidence | number | no |  |  |

### WikidataSearchRequest
| field | type | required | format | notes |
|---|---|---|---|---|
| term | string | yes |  |  |
| source_lang | string | no |  | default Chinese |
| target_langs | string[] | no |  | default English |
| domain | string | no |  | default general |

### WikidataCandidate
| field | type | required | format | notes |
|---|---|---|---|---|
| entity_id | string | yes |  |  |
| source_label | string | yes |  |  |
| description | string | yes |  |  |
| labels | string | yes |  | serialized as JSON map of lang -> label |

### WikidataSearchResponse
| field | type | required | format | notes |
|---|---|---|---|---|
| term | string | yes |  |  |
| candidates | WikidataCandidate[] | yes |  |  |

### WikidataImportRequest
| field | type | required | format | notes |
|---|---|---|---|---|
| source_text | string | yes |  |  |
| target_text | string | yes |  |  |
| source_lang | string | yes |  |  |
| target_lang | string | yes |  |  |
| domain | string | no |  | default general |
| entity_id | string | no |  |  |

### MetricsResponse
| field | type | required | format | notes |
|---|---|---|---|---|
| translation_count | integer | yes |  | total translation calls since process start; initializes to 0 |
| translation_latency_mean_ms | number | yes |  | running arithmetic mean of per-call latency in ms; 0.0 when translation_count is 0; always serialized as float |
| provider_failure_count | integer | yes |  | total provider call failures since process start; initializes to 0; see BR-23 |
| font_cache_hits | integer | yes |  | total font buffer cache hits since process start; initializes to 0 |
| font_cache_misses | integer | yes |  | total font buffer cache misses since process start; initializes to 0 |
| critique_loop_invocations | integer | no |  | total critique-loop invocations since process start; initializes to 0; see BR-46 |
| critique_iterations_total | integer | no |  | cumulative critique iterations across all requests since process start; initializes to 0; see BR-46 |
| glossary_match_rate | number | no |  | glossary term match rate (0.0–1.0 float); definition per design.md; 0.0 when no terms evaluated; see BR-46 |

### BlockQualityScore
| field | type | required | format | notes |
|---|---|---|---|---|
| block_id | string | yes |  | element_id of the TranslatableElement this score belongs to |
| score | number | yes |  | COMET/xCOMET quality score; float; range is model-dependent (see BR-54) |
| model | string | yes |  | name/version of the QE model that produced the score (e.g. Unbabel/wmt22-cometkiwi-da) |

### JobQualityResponse
| field | type | required | format | notes |
|---|---|---|---|---|
| job_id | string | yes |  | job identifier |
| status | enum(available, pending, disabled, unavailable) | yes |  | available — scores ready; pending — translation not yet complete or scoring still running; disabled — QE_ENABLED=false; unavailable — model load failed or scoring failed for this job |
| scores | BlockQualityScore[] | no |  | present and non-empty when status = available; omitted or empty array when status is any other value |

## Endpoint Notes

**GET /terms/export** — the `status` query parameter accepts `approved`, `unverified`, `needs_review`, and `rejected`. When omitted, all terms are exported. See BR-6 (extended by BR-28) and Table G in `contracts/business/business-rules.md`.

**POST /terms/reject** — transitions a term to `rejected` status. Rejected terms are never injected into translation prompts regardless of the loose gate flag (BR-29). Returns HTTP 200 `{"status": "rejected"}` on success; HTTP 404 `{"detail": "Term not found"}` when the term does not exist.

**POST /terms/flag-needs-review** — flags a term for human review by transitioning it to `needs_review` status. Terms in `needs_review` are not injected until approved (BR-29). Returns HTTP 200 `{"status": "needs_review"}` on success; HTTP 404 `{"detail": "Term not found"}` when the term does not exist.

**GET /jobs/{job_id}** — `download_url` is set to `/api/jobs/{job_id}/download` only when `status == "completed"` AND the output archive exists on disk; it is `null` in all other states (running, failed, stopped, or completed with missing archive). The download endpoint itself (`GET /jobs/{job_id}/download`) is a separate route and is not changed by this field addition.

**GET /jobs/{job_id}/quality** — returns quality evaluation scores produced by the COMET/xCOMET model after job completion. Returns HTTP 200 with `status: "available"` and a populated `scores` array when scores are ready. Returns HTTP 200 with `status: "pending"` when the job exists but has not yet completed or scores are not yet attached. Returns HTTP 200 with `status: "disabled"` when `QE_ENABLED=false`. Returns HTTP 200 with `status: "unavailable"` when the QE model failed to load or scoring failed for this job. Returns HTTP 404 `{"detail": "Job not found"}` for an unknown `job_id`. See BR-54, BR-55, BR-56, BR-57. QE scoring never blocks translation job completion (BR-56).

## Error Format

See `contracts/api/error-format.md`. Handled errors use `raise HTTPException(status_code, detail)` which produces `{"detail": "<human message>"}`. Request-validation failures (Pydantic / Form / File) produce HTTP 422 with `{"detail": [{loc, msg, type}]}`. No custom error envelope, no symbolic error code, no retry hints are emitted.

## Compatibility Policy

All paths are served under the `/api` prefix (mounted in `app/backend/main.py`). The endpoint table above is the compatibility surface. Removing or renaming a path, changing a required method, or removing a required response field is a **breaking change**. Adding optional response fields or new endpoints is non-breaking.

## Endpoint Inventory Policy

The endpoint table above plus `contracts/api/api-inventory.md` must list every route defined in `app/backend/api/routes.py`. Conformance (`.cdd/conformance.json`, currently `enabled: false`) can mechanically enforce this once enabled. Until then, route accuracy is verified manually during change classification.

## Breaking Change Policy

Per frontmatter `breaking-change-policy: deprecate-2-minors`. Breaking changes require updating this contract in the same change, or the gate will fail on drift. A deprecation notice must precede removal by at least two minor releases.
