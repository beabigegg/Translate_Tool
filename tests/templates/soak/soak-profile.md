# Soak Profile

## Target Feature

## Duration

## Refresh / Request Pattern

## Cache / Queue / DB Expectations

## Metrics

## Failure Thresholds

## Artifact Retention

## Runner Config (REQUIRED — fill before running)

- runner: k6 | locust | artillery
- config file: tests/soak/<scenario>.<ext>
- target environment:
- constant load (VUs or arrival rate):
- duration: <!-- soak runs are typically 2h–24h+ -->
- pass criteria (must include leak/drift signals):
  - memory growth: <!-- e.g., RSS < 1.2× baseline after 4h -->
  - latency drift: <!-- e.g., p95 within ±10% of hour-1 baseline -->
  - error rate: <!-- e.g., < 0.5% sustained -->
- artifacts:

### Reference templates
See `tests/templates/soak/k6-example.js` or `locust-example.py`.
