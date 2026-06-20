# Regression Report

## Change ID
term-extraction-db-first

## Date
2026-06-20

## Baseline
Full test suite before change: 748 tests passing (from fallback-chain-cloud-providers close commit).

## Regression Surface

| area | tests affected | result |
|---|---|---|
| Term extractor (unit) | tests/test_term_extractor.py — 18 new + pre-existing | PASS |
| Term DB (unit) | tests/test_term_db.py — 4 new + pre-existing | PASS |
| Orchestrator Phase 0 (integration) | tests/test_orchestrator_phase0.py — 3 new | PASS |
| Term extractor resilience (data-boundary) | tests/test_term_extractor_resilience.py — 13 new | PASS |
| Env contract wiring | tests/test_env_contract.py — 6 new | PASS |
| Provider fallback chain | tests/test_provider_fallback.py — pre-existing | PASS (no regression) |
| Quality evaluation (COMET) | tests/test_quality_evaluation.py — pre-existing | PASS (no regression) |
| Terminology audit | tests/test_term_audit.py — pre-existing | PASS (no regression) |
| Full suite | 764 passed, 4 skipped, 0 failed | PASS |

## Regressions Found
None.

## Pre-existing failures excluded from gate
None — no pre-existing test failures were present at baseline.

## Notes
- Term extraction path no longer calls `localhost:11434` (Ollama). The Ollama `extraction_only` path is preserved unchanged (AC-7).
- `test_orchestrator_phase0.py::test_phase0_hook_uses_panjit_config` verifies exact PANJIT URL and key are threaded through from provider config — confirms no silent misconfiguration.
- All resilience failure modes (ConnectionError, Timeout, HTTPError/5xx, SSLError) confirmed non-fatal at the real `embed()` call boundary.
