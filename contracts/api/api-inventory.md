---
contract: api-inventory
summary: Endpoint inventory categories and ownership map for non-standard API surfaces.
owner: application-team
surface: api
---

# API Inventory

All routes are served under the `/api` prefix (mounted in `app/backend/main.py`).

| method | path | category | owner | contract test | notes |
|---|---|---|---|---|---|
| GET | /api/health | health-exception | application-team | — | liveness probe |
| GET | /api/models | standard-json | application-team | — | Ollama model list |
| GET | /api/profiles | standard-json | application-team | — | translation profiles |
| GET | /api/model-config | standard-json | application-team | — | per-model VRAM/ctx config |
| GET | /api/route-info | standard-json | application-team | — | query `targets` (csv) → RouteInfoResponse |
| POST | /api/jobs | file-upload-exception | application-team | — | multipart; creates async job; 400, 422 |
| GET | /api/jobs/{job_id} | standard-json | application-team | — | job status + progress; 404 |
| POST | /api/jobs/{job_id}/cancel | standard-json | application-team | — | sets stop flag; 404 |
| GET | /api/jobs/{job_id}/download | stream-download-exception | application-team | — | zip output; 404 if not ready |
| GET | /api/stats | standard-json | application-team | — | job queue stats |
| GET | /api/cache/stats | standard-json | application-team | — | translation cache stats |
| DELETE | /api/cache | standard-json | application-team | — | clear cache; query `model` |
| GET | /api/terms/stats | standard-json | application-team | — | term db counts |
| GET | /api/terms/export | stream-download-exception | application-team | — | query `format`, `status`; 400, 500 |
| POST | /api/terms/import | file-upload-exception | application-team | — | multipart; query `strategy`; 400, 422 |
| GET | /api/terms/unverified | standard-json | application-team | — | query `target_lang`, `domain` |
| POST | /api/terms/approve | standard-json | application-team | — | body: TermApproveRequest; 404 |
| GET | /api/terms/approved | standard-json | application-team | — | query `target_lang`, `domain` |
| PATCH | /api/terms/edit | standard-json | application-team | — | body: TermEditRequest; 404 |
| POST | /api/terms/wikidata/search | standard-json | application-team | — | external Wikidata lookup |
| POST | /api/terms/wikidata/import | standard-json | application-team | — | insert lookup result (confidence 0.9, unverified) |

## Categories

- standard-json
- health-exception
- stream-download-exception
- file-upload-exception
- websocket-exception
- legacy-transition
