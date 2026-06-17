# Change Request

## Original Request

Add a metrics endpoint to api/routes.py that exposes model latency, provider failure rate, and font cache hit rate — observable via HTTP GET /api/metrics; success criterion: endpoint returns JSON with current counters that update on each translation/font-load call.

## Business / User Goal

Provide operational visibility into translation service performance so that latency regressions, provider failures, and cache effectiveness can be detected without grepping logs.

## Non-goals

- Persistent storage / time-series metrics (no Prometheus/InfluxDB integration)
- Authentication on the metrics endpoint
- Historical trend data beyond what is held in process memory

## Constraints

- In-process counters only (no external metrics service)
- Must be additive — no behavior change to existing translation or font-load paths beyond incrementing counters
- Depends on p1-provider-routing being complete (model/provider resolved before latency can be attributed)

## Known Context

- p1-provider-routing is archived; routing logic lives in app/backend/services/model_router.py
- Font cache (lru_cache on _load_font_buffer) was added in p1-font-lru-cache (archived)
- API routes live in app/backend/api/routes.py (or similar path under app/backend/)

## Open Questions

## Requested Delivery Date / Priority

P1-9 (next in sequence after p1-font-lru-cache)
