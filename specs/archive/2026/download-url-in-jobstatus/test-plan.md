---
change-id: download-url-in-jobstatus
schema-version: 0.1.0
last-changed: 2026-06-20
risk: low
tier: 1
---

# Test Plan: download-url-in-jobstatus

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1: `download_url` field declared on `JobStatus`, defaults to `None` | unit | `tests/test_provider_fallback.py::TestJobStatusShape::test_job_status_download_url_field_defaults_to_none` | 0 |
| AC-1: `download_url` field accepts `Optional[str]` value | unit | `tests/test_provider_fallback.py::TestJobStatusShape::test_job_status_download_url_field_accepts_string` | 0 |
| AC-2: status=completed + output_zip exists → `download_url == "/api/jobs/{id}/download"` | unit | `tests/test_jobstatus_download_url.py::TestDownloadUrlDerivation::test_completed_with_existing_zip` | 0 |
| AC-3: status=running → `download_url` is `None` | unit | `tests/test_jobstatus_download_url.py::TestDownloadUrlDerivation::test_running_status_returns_none` | 0 |
| AC-3: status=failed → `download_url` is `None` | unit | `tests/test_jobstatus_download_url.py::TestDownloadUrlDerivation::test_failed_status_returns_none` | 0 |
| AC-3: status=completed + output_zip is `None` → `download_url` is `None` | unit | `tests/test_jobstatus_download_url.py::TestDownloadUrlDerivation::test_completed_no_zip_returns_none` | 0 |
| AC-3: status=completed + output_zip path absent on disk → `download_url` is `None` | unit | `tests/test_jobstatus_download_url.py::TestDownloadUrlDerivation::test_completed_zip_path_missing_on_disk` | 0 |
| AC-2/AC-3: parametrized sweep (queued, running, stopped, failed, completed × zip states) | unit | `tests/test_jobstatus_download_url.py::TestDownloadUrlDerivation::test_derivation_parametrized` | 0 |
| AC-4: `GET /jobs/{id}` completed job JSON payload carries correct `download_url` | integration | `tests/test_jobstatus_download_url.py::TestJobStatusEndpoint::test_get_job_status_completed_has_download_url` | 1 |
| AC-4: `GET /jobs/{id}` running job returns `download_url: null` in JSON | integration | `tests/test_jobstatus_download_url.py::TestJobStatusEndpoint::test_get_job_status_running_download_url_null` | 1 |
| AC-5: no existing `JobStatus` field dropped or type-changed | unit | `tests/test_provider_fallback.py::TestJobStatusShape` (full class — existing tests stay green) | 0 |
| AC-6: `api-contract.md` documents `download_url`; `openapi.yml` in sync | contract | `cdd-kit validate` | 1 |
| AC-7: download endpoint `routes.py:339-350` still reachable and returns ZIP | integration | `tests/test_jobstatus_download_url.py::TestDownloadEndpointUnchanged::test_download_endpoint_still_returns_zip` | 1 |

## Test Families Required

| family | tier | notes |
|---|---|---|
| unit | 0 | Schema field declaration (extend `TestJobStatusShape`) + derivation rule via `TestClient` with `job_manager.get_job` mocked at the `job_manager` module boundary |
| integration | 1 | `TestClient` against the real FastAPI app; synthetic `JobRecord` with a real temp-file `output_zip`; covers `GET /jobs/{id}` JSON response and download endpoint reachability |
| contract | 1 | `cdd-kit validate` after `openapi.yml` is regenerated; fails if `download_url` is absent from the OpenAPI spec |

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| `tests/test_provider_fallback.py::TestJobStatusShape` | extend (add two tests) | AC-1 requires two new assertions on `download_url`; no existing test is changed or deleted |

## Out of Scope

- Frontend rendering (`TranslatePage.jsx` untouched — no frontend tests needed).
- `JobRecord` dataclass fields (`job_manager.py` not modified).
- `tests/contract/response-samples.json` — deferred pending CER-001 approval.
- Stress / soak / monkey / resilience / e2e tiers.

## Notes

- Extend `tests/test_provider_fallback.py::TestJobStatusShape` for AC-1/AC-5; do not create a parallel schema-shape class.
- New file `tests/test_jobstatus_download_url.py` owns all derivation-rule and endpoint tests (AC-2, AC-3, AC-4, AC-7).
- Mock at the `job_manager.get_job` boundary in the consumer module (`app.backend.api.routes.job_manager`), not at the definition path.
- The authoritative derivation rule (from `implementation-plan.md`): `download_url = f"/api/jobs/{job_id}/download" if (status == "completed" and output_ready) else None`.
- After implementation, run `cdd-kit openapi export --out contracts/api/openapi.yml` before the contract gate.
