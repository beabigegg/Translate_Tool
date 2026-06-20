# Archive — download-url-in-jobstatus

## Change Summary
The `GET /jobs/{job_id}` endpoint never returned a `download_url` field, leaving the frontend download button permanently invisible. The root cause was a two-part omission: `JobStatus` (Pydantic model in `schemas.py`) had no `download_url` field at all, and `routes.py::job_status()` never derived a URL from the already-available `status` and `output_ready` locals. The frontend (`TranslatePage.jsx:173`) was already correctly gated on `jobStatus.download_url` — it just always received `null/undefined`.

## Final Behavior
`GET /jobs/{job_id}` now returns `download_url: "/api/jobs/{job_id}/download"` when `status == "completed"` and the output zip exists on disk; `null` in all other states (running, failed, stopped, or completed with a missing archive). The download endpoint itself (`GET /jobs/{job_id}/download`) was not changed. The frontend download button now renders automatically when a job completes.

## Final Contracts Updated
- `contracts/api/api-contract.md` — schema-version bumped 0.5.0 → 0.6.0; `JobStatus` table gained three previously-undocumented optional fields: `download_url`, `quality_score_avg` (p2-comet-qe gap), `audit_hit_rate` (p2-term-audit gap); endpoint derivation rule added to `## Endpoint Notes`
- `contracts/api/openapi.yml` — regenerated; `JobStatus` component now includes all three new fields

## Final Tests Added / Updated
- `tests/test_jobstatus_download_url.py` (new, 17 tests) — `TestDownloadUrlDerivation` parametrized matrix (status × zip-state × disk-existence), `TestJobStatusEndpoint` (JSON payload via TestClient), `TestDownloadEndpointUnchanged` (AC-7 regression)
- `tests/test_provider_fallback.py` — 2 new methods in `TestJobStatusShape`: field default-None and string-acceptance

## Final CI/CD Gates
- contract-validation, openapi-sync, targeted-unit-tests, full-test-suite (all Tier 1 required)
- No new workflow gate row (Tier 3 policy)

## Production Reality Findings
- Two previously undocumented `JobStatus` fields (`quality_score_avg`, `audit_hit_rate`) were in `schemas.py` but absent from the contract table — bundled into this change's contract update rather than opening a separate change
- Gate tier-floor false-positive on "endpoint" keyword (see CLAUDE.md promoted lesson); resolved with `tier-floor-override`
- Reproduction proof required a pre-fix failing run; initial `cdd-kit test run` was executed against post-fix code; resolved by temporary stash → failing run → restore

## Lessons Promoted to Standards
(none — no new cross-change workflow rule emerged; tier-floor false-positive pattern already covered by existing CLAUDE.md entry)

## Follow-up Work
None. The `GET /jobs/{job_id}/download` endpoint and `TranslatePage.jsx` download button logic were correct before this change and remain unchanged.

## Cold Data Warning
This archive is historical evidence. Current requirements live in `contracts/` and active project guidance.
