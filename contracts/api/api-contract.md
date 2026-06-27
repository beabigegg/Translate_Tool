---
contract: api
summary: API behavior, compatibility rules, and endpoint contract requirements.
owner: application-team
surface: api
schema-version: 0.9.0
last-changed: 2026-06-27
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
| POST | /jobs | none | JobCreateRequest | JobCreateResponse | 400, 422 | tests/contract/ |
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
| GET | /providers/health | none | - | ProviderHealthItem[] | - | tests/test_providers_api.py |
| GET | /providers/models | none | - | ProviderModelEntry[] | - | tests/test_providers_api.py |
| POST | /providers/test-translation | none | TestTranslationRequest | TestTranslationResult[] | 400, 422 | tests/test_providers_api.py |
| GET | /jobs/{job_id}/judge | none | - | JobJudgeResponse | 200 (judge_status: available/disabled/unavailable); 404 job not found | tests/contract/ |
| POST | /jobs/{job_id}/judge/apply | none | - | JobJudgeApplyResponse | 202 applying; 404 job not found; 409 preconditions not met | tests/contract/ |

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
| judge_score | enum(低, 中, 高) | no |  | latest judge score tier; null when judge has not run, is disabled, or is unavailable; for list/summary views; see BR-72 |
| judge_apply_status | string | no |  | apply operation lifecycle: applying, applied, failed, or null when apply not yet triggered; see BR-76, BR-77 |
| download_url | string | no |  | URL to download translated zip; set to /api/jobs/{job_id}/download only when status==completed AND output_zip exists on disk; null otherwise |
| warnings | string[] | no |  | degradation notices; null or empty list when no degradation occurred; populated by PDF processor when fitz falls back to ReportLab; also populated when a format-specific output_mode is requested for an incompatible file type (bilingual on non-DOCX, adjacent/annotation on non-XLSX) — one entry per affected file; type is always string[] or null, never a bare string; additive optional field — backward-compatible; see AC-1, AC-2, AC-3 |

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

### ProviderHealthItem
| field | type | required | format | notes |
|---|---|---|---|---|
| provider | string | yes |  |  |
| status | string | yes |  |  |
| latency_ms | number | no |  |  |

### TestTranslationRequest
| field | type | required | format | notes |
|---|---|---|---|---|
| text | string | yes |  |  |
| src_lang | string | yes |  |  |
| targets | string[] | yes |  |  |
| profile | string | no |  |  |
| models | string[] | no |  |  |
| deepseek_api_key | string | no |  |  |

### TestTranslationResult
| field | type | required | format | notes |
|---|---|---|---|---|
| model_id | string | yes |  |  |
| provider | string | yes |  |  |
| translation | string | no |  |  |
| duration_ms | number | yes |  |  |
| comet_score | number | no |  |  |
| error | string | no |  |  |

### ProviderModelEntry
| field | type | required | format | notes |
|---|---|---|---|---|
| provider | string | yes |  |  |
| translate_model | string | no |  |  |
| long_doc_model | string | no |  |  |

### JobCreateRequest
| field | type | required | format | notes |
|---|---|---|---|---|
| file | string | yes | binary | one or more document files (DOCX, PPTX, XLSX, PDF); multipart upload |
| target_language | string | yes |  | comma-separated target language codes; ≥1 non-empty value required (BR-3) |
| source_language | string | no |  | source language code; auto-detected when omitted |
| model | string | no |  | model override; defaults to provider routing config (BR-4) |
| profile | string | no |  | profile id; overrides routing group |
| num_ctx | integer | no |  | context window override; must satisfy BR-2 |
| output_mode | enum(append,replace,bilingual,adjacent,annotation) | no |  | output mode for translation; default append; bilingual (DOCX only) two-column source/translation table; adjacent/annotation (XLSX only) write beside or as comment; replace overwrites source; all format-specific modes degrade to append for other formats with job.warnings notice; ignored (clamped to append) when len(targets)>1 (BR-66, BR-67); invalid values rejected with HTTP 422 |

### JobJudgeResponse
| field | type | required | format | notes |
|---|---|---|---|---|
| job_id | string | yes |  | :job identifier |
| judge_status | enum(available,disabled,unavailable) | yes |  | :available — judge ran and results ready; disabled — JUDGE_ENABLED=false; unavailable — Gemma unreachable or exception |
| score | enum(低,中,高) | no |  | :quality score tier; null unless judge_status=available |
| source_text | string | no |  | :representative joined source text scored by judge; null unless judge_status=available |
| translated_text | string | no |  | :final translated text after all judge iterations; display-only joined view (see BR-75); null unless judge_status=available |
| feedback | string | no |  | :judge natural-language quality feedback; null unless judge_status=available |
| attempts | integer | no |  | :number of judge-loop iterations (1–JUDGE_MAX_ITERATIONS); null unless judge_status=available |
| model | string | no |  | :Ollama model name used for judging (JUDGE_MODEL value); null unless judge_status=available |

### JobJudgeApplyResponse
| field | type | required | format | notes |
|---|---|---|---|---|
| status | string | yes |  | :always 'applying' on HTTP 202 |

## Endpoint Notes

**GET /terms/export** — the `status` query parameter accepts `approved`, `unverified`, `needs_review`, and `rejected`. When omitted, all terms are exported. See BR-6 (extended by BR-28) and Table G in `contracts/business/business-rules.md`.

**POST /terms/reject** — transitions a term to `rejected` status. Rejected terms are never injected into translation prompts regardless of the loose gate flag (BR-29). Returns HTTP 200 `{"status": "rejected"}` on success; HTTP 404 `{"detail": "Term not found"}` when the term does not exist.

**POST /terms/flag-needs-review** — flags a term for human review by transitioning it to `needs_review` status. Terms in `needs_review` are not injected until approved (BR-29). Returns HTTP 200 `{"status": "needs_review"}` on success; HTTP 404 `{"detail": "Term not found"}` when the term does not exist.

**GET /jobs/{job_id}** — `download_url` is set to `/api/jobs/{job_id}/download` only when `status == "completed"` AND the output archive exists on disk; it is `null` in all other states (running, failed, stopped, or completed with missing archive). The download endpoint itself (`GET /jobs/{job_id}/download`) is a separate route and is not changed by this field addition. `warnings` is an optional string array (null or `[]` when no degradation); populated by the PDF processor when rendering quality is reduced; verbatim strings are defined in the `JobStatus` schema above. Existing consumers that do not read `warnings` are unaffected (AC-3).

**GET /providers/health** — returns health status for each configured provider. Each element: `{provider, status, latency_ms}` where `status` is one of `online`, `offline`, `not_configured`. `latency_ms` is omitted when `status` is `not_configured`. PANJIT is always probed; DeepSeek is probed only when a valid key is supplied via the `X-DeepSeek-Api-Key` request header, otherwise returned as `not_configured`. The key is transmitted as a header (not a query parameter) to prevent exposure in server access logs and browser history (BR-65). See BR-63.

**GET /providers/models** — returns the model list for each provider, sourced from `config/providers.yml` in-memory (already loaded via `load_providers_config()`). NOT a live `/v1/models` network call. Returns `ProviderModelEntry[]` where each entry has `{provider, translate_model, long_doc_model}`. See BR-63.

**POST /providers/test-translation** — runs a parallel test translation across the requested models. Synchronous (no `job_id`). Request: `TestTranslationRequest` with fields `text`, `src_lang`, `targets[]`, optional `profile`, `models[]`, `deepseek_api_key`. Response: `TestTranslationResult[]` — `{model_id, provider, duration_ms}` plus optional `translation`, `comet_score` (omitted when `QE_ENABLED=false`), and `error` (present when that model call failed). Partial failure is isolated per model. DeepSeek path not invoked without a key — returns `error: "DeepSeek API key not provided"`. See BR-64, BR-65.

**GET /jobs/{job_id}/quality** — returns quality evaluation scores produced by the COMET/xCOMET model after job completion. Returns HTTP 200 with `status: "available"` and a populated `scores` array when scores are ready. Returns HTTP 200 with `status: "pending"` when the job exists but has not yet completed or scores are not yet attached. Returns HTTP 200 with `status: "disabled"` when `QE_ENABLED=false`. Returns HTTP 200 with `status: "unavailable"` when the QE model failed to load or scoring failed for this job. Returns HTTP 404 `{"detail": "Job not found"}` for an unknown `job_id`. See BR-54, BR-55, BR-56, BR-57. QE scoring never blocks translation job completion (BR-56).

**GET /jobs/{job_id}/judge** — returns judge evaluation results produced by the Gemma judge after job completion. HTTP 200 with `judge_status: "available"` and populated score/feedback fields when judge results are ready. HTTP 200 with `judge_status: "disabled"` when `JUDGE_ENABLED=false`. HTTP 200 with `judge_status: "unavailable"` when Gemma was unreachable or any judge exception occurred. HTTP 404 for an unknown `job_id`. The `translated_text` field is a display-only joined view of the judge's accepted final text — it is NOT the document output until the user confirms apply (see BR-75). See BR-72, BR-73, BR-74, BR-75.

**POST /jobs/{job_id}/judge/apply** — triggers async re-render of the job's output document using the judge's per-block re-translated text. Preconditions (else HTTP 409): `job.status == "completed"` AND `JUDGE_ENABLED` AND `judge_status == "available"` AND `retranslated_blocks` map is non-empty AND original source files remain on disk. Unknown `job_id` → HTTP 404. On success returns HTTP 202 `{"status": "applying"}`; re-render runs in a background daemon thread. Frontend polls `GET /api/jobs/{id}` until `judge_apply_status` transitions to `applied` or `failed`. When `judge_apply_status == "applied"`, the stable `download_url` serves the updated document. A second apply call while `judge_apply_status == "applying"` returns HTTP 202 without spawning a duplicate worker (idempotent under lock). See BR-76, BR-77.

**POST /api/jobs** (`output_mode`) — accepts an optional `output_mode` field (`"append"` | `"replace"` | `"bilingual"` | `"adjacent"` | `"annotation"`; default `"append"`). `"append"` adds translations after source text (existing behavior). `"replace"` overwrites source paragraphs/text-frames in-place. `"bilingual"` (DOCX/DOC only) converts each body paragraph into a two-column source/translation table; degrades to `"append"` for XLSX/PPTX/PDF with a notice in `job.warnings`. `"adjacent"` (XLSX/XLS only) writes translation to the block of columns immediately to the right of the original data; degrades to `"append"` for DOCX/PPTX/PDF with a notice in `job.warnings`. `"annotation"` (XLSX/XLS only) attaches translation as a cell comment; degrades to `"append"` for DOCX/PPTX/PDF with a notice in `job.warnings`. When a job targets more than one language, `output_mode` is silently clamped to `"append"` — see BR-66, BR-67. Invalid values are rejected with HTTP 422.

## Error Format

See `contracts/api/error-format.md`. Handled errors use `raise HTTPException(status_code, detail)` which produces `{"detail": "<human message>"}`. Request-validation failures (Pydantic / Form / File) produce HTTP 422 with `{"detail": [{loc, msg, type}]}`. No custom error envelope, no symbolic error code, no retry hints are emitted.

## Compatibility Policy

All paths are served under the `/api` prefix (mounted in `app/backend/main.py`). The endpoint table above is the compatibility surface. Removing or renaming a path, changing a required method, or removing a required response field is a **breaking change**. Adding optional response fields or new endpoints is non-breaking.

## Endpoint Inventory Policy

The endpoint table above plus `contracts/api/api-inventory.md` must list every route defined in `app/backend/api/routes.py`. Conformance (`.cdd/conformance.json`, currently `enabled: false`) can mechanically enforce this once enabled. Until then, route accuracy is verified manually during change classification.

## Breaking Change Policy

Per frontmatter `breaking-change-policy: deprecate-2-minors`. Breaking changes require updating this contract in the same change, or the gate will fail on drift. A deprecation notice must precede removal by at least two minor releases.
