# Stress Load Profile

## Target Feature

## Workload Mix

## Concurrency

## Data Volume

## Duration

## Metrics

## Thresholds

## Runner Config (REQUIRED — fill before running)

- runner: k6 | locust | artillery   <!-- pick one -->
- config file: tests/stress/<scenario>.<ext>   <!-- e.g., tests/stress/checkout-load.js -->
- target environment: <!-- staging | preprod | local -->
- VUs / arrival rate: <!-- e.g., 50 VUs, or 20 req/s -->
- duration: <!-- e.g., 3m -->
- pass criteria: <!-- must reference an SLO, e.g., p95 < 500ms, error rate < 1% -->
- artifacts: <!-- where stdout/HTML report is stored, e.g., ci/artifacts/stress/<run-id>/ -->

### Reference templates
See `tests/templates/stress/k6-example.js`, `locust-example.py`, or
`artillery-example.yml` for runner-specific starting points.
