---
contract: api-error-format
summary: Standard error payload shape, safety rules, and reusable error code table.
owner: application-team
surface: api
---

# API Error Format

## Standard Error Shape

This API uses the **FastAPI default error format** — no custom error envelope.

**Handled errors** (`raise HTTPException(status_code, detail)`):
```json
{"detail": "<human message>"}
```

**Request-validation errors** (Pydantic / `Form` / `File` parameter failures, HTTP 422):
```json
{"detail": [{"loc": ["<source>", "<field>"], "msg": "<message>", "type": "<error_type>"}]}
```

Rules:
- No symbolic error `code` field exists.
- No retry-after hints are emitted.
- In-job processing failures (including document-size limit breaches) are NOT HTTP errors — they surface via `GET /api/jobs/{id}` as `status: "failed"` with the `error` field set.
- Detail strings are human-readable English. They MUST NOT contain secrets, stack traces, or file-system paths.

## Error Codes
| code | status | user-facing message | retryable | owner |
|---|---:|---|---:|---|
| (none) | 400 | "No files uploaded" | no | application-team |
| (none) | 400 | "No target languages provided" | no | application-team |
| (none) | 400 | "format must be json, csv, or xlsx" | no | application-team |
| (none) | 400 | "strategy must be skip, overwrite, merge, or force" | no | application-team |
| (none) | 400 | "Only .json and .csv files are supported" | no | application-team |
| (none) | 404 | "Job not found" | no | application-team |
| (none) | 404 | "Output not ready" | no | application-team |
| (none) | 404 | "Term not found" | no | application-team |
| (none) | 422 | "num_ctx must be a positive integer" | no | application-team |
| (none) | 422 | "num_ctx must be between {min} and {max}…" | no | application-team |
| (none) | 422 | str(exc) on import parse failure | no | application-team |
| (none) | 422 | Pydantic validation array (see shape above) | no | application-team |
| (none) | 500 | str(exc) on term export failure | no | application-team |
