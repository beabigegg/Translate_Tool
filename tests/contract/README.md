# Response-shape contract tests (data-shape conformance)

This directory is the **body-level** half of API conformance (ADR 0007). The
route-level checker (`validate_api_conformance.py`) only verifies that an
endpoint's method + path line up. This harness verifies the **shape of the
response body** — the field names and types that actually break frontend/backend
integration when they drift.

It is stack-agnostic: it validates a captured JSON **sample** of each endpoint's
real response against the response **schema** the contract declares. That works
the same whether your backend is FastAPI, Flask, Express, or Go — the only thing
checked is the serialized JSON at the HTTP boundary.

## How it works

```
contracts/api/api-contract.md   ← you declare a typed response schema (## Schemas)
        │  cdd-kit openapi export --out contracts/api/openapi.json
        ▼
contracts/api/openapi.json      ← generated; carries the resolved response schemas
        │
        ▼  validate_response_shape.py  (runs inside `cdd-kit validate --contracts` and the gate)
tests/contract/response-samples.json  ← maps each endpoint → a captured sample
tests/contract/samples/*.json         ← the captured response bodies
```

A mismatch is an **error by default** once you have a `response-samples.json`
(see ADR 0007 — a check that defaults to advisory gets disarmed). Endpoints whose
contract response cell is still prose are simply not checked, so you can adopt
this one endpoint at a time.

## Activate it (3 steps)

1. **Declare a typed schema** for an endpoint's response in
   `contracts/api/api-contract.md`. Either a field table or a `json-schema`
   block under `## Schemas`, then point the endpoint's `response schema` column
   at it. (`cdd-kit contract schema set <Name> --field ...` and
   `cdd-kit contract endpoint set ...` do this for you.)

   > **Field table (Tier A) vs json-schema block (Tier B).** A field table
   > supports primitive types (`string`, `integer`, `number`, `boolean`),
   > `enum(a, b, c)`, references to another named schema, and `[]` suffixes. For
   > anything richer — arrays of free-form objects, nested objects, unions — use
   > a fenced ` ```json-schema ` block, which accepts arbitrary JSON Schema. For
   > example `topReasons` as an array of objects must be a json-schema block:
   >
   > ```json-schema
   > { "type": "object", "required": ["topReasons"],
   >   "properties": { "topReasons": { "type": "array", "items": { "type": "object" } } } }
   > ```

2. **Regenerate** the projection and copy the example manifest:

   ```bash
   cdd-kit openapi export --out contracts/api/openapi.json
   cp tests/contract/response-samples.example.json tests/contract/response-samples.json
   ```

3. **Capture a real sample** for the endpoint (see snippets below) and add an
   entry to `response-samples.json`. Then `cdd-kit validate --contracts` (and the
   gate) enforces it.

## Manifest format (`response-samples.json`)

```jsonc
{
  // "METHOD /path": "samples/<file>.json"
  "GET /health": "samples/health.json",

  // Or an object, to drill into an envelope before validating. Use this when
  // your API wraps payloads, e.g. { "success": true, "data": { ... } } and your
  // schema describes the inner `data`:
  "POST /api/hold-overview/summary": {
    "sample": "samples/hold_overview_summary.json",
    "dataPath": "data"
  }
}
```

`dataPath` is dotted (`data`, `result.items`, …). The path is matched against the
contract's normalized endpoint path, so `/users/:id` and `/users/{id}` are
equivalent.

## Capturing samples (regenerate, don't hand-write)

Hand-written samples go stale. Capture them from the **real app** in a test so
each run asserts live output. Pick the snippet for your stack:

### FastAPI

```python
# tests/contract/capture_samples.py  — run before validate in CI
import json, pathlib
from fastapi.testclient import TestClient
from myapp.main import app

client = TestClient(app)
out = pathlib.Path("tests/contract/samples"); out.mkdir(parents=True, exist_ok=True)

resp = client.post("/api/hold-overview/summary", json={...})
(out / "hold_overview_summary.json").write_text(json.dumps(resp.json()), encoding="utf-8")
```

> With FastAPI you can also make drift **preventive**: run `npm run contract:models`
> (wired by `cdd-kit init` when FastAPI is detected) to generate Pydantic models
> from `openapi.json`, and declare them as each route's `response_model`. FastAPI
> then enforces the contracted shape at runtime, before the sample test even runs.

### Flask

```python
# tests/contract/capture_samples.py
import json, pathlib
from myapp import create_app

client = create_app({"TESTING": True}).test_client()
out = pathlib.Path("tests/contract/samples"); out.mkdir(parents=True, exist_ok=True)

resp = client.post("/api/hold-overview/summary", json={...})
(out / "hold_overview_summary.json").write_text(
    json.dumps(resp.get_json()), encoding="utf-8")
```

### Express / Node (supertest)

```js
// tests/contract/capture-samples.mjs
import { writeFileSync, mkdirSync } from 'node:fs';
import request from 'supertest';
import app from '../../src/app.js';

mkdirSync('tests/contract/samples', { recursive: true });
const res = await request(app).get('/health');
writeFileSync('tests/contract/samples/health.json', JSON.stringify(res.body));
```

Wire `capture → cdd-kit validate --contracts` into your test command so samples
are regenerated and validated together. Committed static samples also work — you
just own keeping them representative.

## Config (optional, `.cdd/conformance.json`)

```jsonc
{
  "responseShape": {
    "enabled": true,                 // default true once a manifest exists
    "severity": "error",             // default error; "warning" = non-blocking ratchet
    "manifest": "tests/contract/response-samples.json"
  }
}
```
