---
contract: api
summary: API behavior, compatibility rules, and endpoint contract requirements.
owner: application-team
surface: api
schema-version: 0.1.0
last-changed: 2026-04-27
breaking-change-policy: deprecate-2-minors
---

# API Contract

## API Style
- response style:
- error style:
- auth style:
- pagination style:
- date/time style:

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
| GET | /terms/approved | none | - | TermItem[] | - | tests/contract/ |
| PATCH | /terms/edit | none | TermEditRequest | - | 404 | tests/contract/ |
| POST | /terms/wikidata/search | none | WikidataSearchRequest | WikidataSearchResponse | 422 | tests/contract/ |
| POST | /terms/wikidata/import | none | WikidataImportRequest | - | 422 | tests/contract/ |

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
| target | string | yes |  |  |
| model | string | yes |  |  |
| profile_id | string | yes |  |  |
| model_type | string | yes |  |  |
| is_primary | boolean | yes |  |  |

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

### TermStatsResponse
| field | type | required | format | notes |
|---|---|---|---|---|
| total | integer | yes |  |  |
| unverified | integer | yes |  |  |
| by_target_lang | string | yes |  | serialized as JSON map of lang -> count |
| by_domain | string | yes |  | serialized as JSON map of domain -> count |

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

## Error Format

## Compatibility Policy

## Endpoint Inventory Policy

## Breaking Change Policy
