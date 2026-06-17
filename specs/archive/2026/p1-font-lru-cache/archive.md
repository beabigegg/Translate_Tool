# Archive — p1-font-lru-cache

## Change Summary

Added a module-level `functools.lru_cache`-backed `_load_font_buffer()` helper in
`app/backend/renderers/pdf_generator.py` to eliminate repeated disk I/O in
`_insert_text_in_rect`. Prior to this change, every call to `_insert_text_in_rect`
opened and read the font file from disk. After this change, the same font path is
read from disk only once per process lifetime; subsequent calls retrieve the cached
`bytes` object from memory. A `clear_font_cache()` helper exposes `.cache_clear()`
for test isolation. Cache key is `os.path.realpath(font_path)` to avoid relative/
absolute path miss-hits.

## Final Behavior

`_insert_text_in_rect` retrieves the font buffer via `_load_font_buffer(font_path)`.
The first call for a given (realpath-normalized) path reads disk; all subsequent
calls return the cached buffer. Exceptions propagate unchanged (lru_cache does not
cache exceptions). The surrounding try/except fallback to `fitz.Font("helv")` is
untouched. The caller-visible behavior is identical; only internal I/O is reduced.

## Final Contracts Updated

- None. Internal I/O optimization only; no API, env, data-shape, business-logic,
  or CI/CD contracts modified.

## Final Tests Added / Updated

- `tests/test_pdf_generator.py::TestFontBufferCache` — 6 new tests:
  - `test_first_call_reads_disk_once` (AC-1)
  - `test_second_call_hits_cache_not_disk` (AC-2)
  - `test_distinct_paths_cached_independently` (AC-3)
  - `test_cached_and_uncached_render_output_equivalent` (AC-4)
  - `test_error_path_does_not_cache_bad_buffer` (error-path invariant)
  - `test_cache_reset_between_tests` (reset hook)
- Total suite: 367 passed, 0 failed (baseline 361 + 6 new).

## Final CI/CD Gates

| gate | result |
|---|---|
| contract-and-fast-tests (Tier 1) | PASS |
| change-gate p1-font-lru-cache (Tier 1) | PASS (tier-floor-override accepted) |
| full-regression (Tier 2, informational) | PASS — 367/0/0 |

## Production Reality Findings

- `tier-floor-override` required: `cdd-kit gate` flagged the keyword "cache" and
  wanted to force Tier 2. Backend-engineer added the override with written rationale
  ("process-internal memory optimisation, not an external cache surface"). Gate
  accepted the override.
- PyPDF2 deprecation warning is pre-existing and outside scope.

## Lessons Promoted to Standards

1. **tier-floor-override generalized** (CLAUDE.md `cdd-kit:learnings`) — expanded existing entry to cover `"cache"` keyword (forces Tier 2 for in-process `lru_cache`) alongside the already-documented `"api key"` pattern. Evidence: `agent-log/audit.yml`, gate override accepted.
2. **CI gate cleanup on archive** (CLAUDE.md `cdd-kit:learnings`) — new entry: at `/cdd-close`, remove `cdd-kit gate <id>` from `.github/workflows/contract-driven-gates.yml` before or after `cdd-kit archive`. Evidence: CI failure (commit `7844225`) when `p1-cloud-providers` and `p1-provider-routing` remained in gate step after archiving.
3. **OpenAPI sync** (CLAUDE.md `cdd-kit:learnings`) — new entry: after any `api-contract.md` change, regenerate and commit `openapi.yml` via `cdd-kit openapi export`. Evidence: CI failure (commit `d12e3f5`) from stale `openapi.yml` after `p1-provider-routing` contract updates.

## Follow-up Work

- None from this change. The no-lock single-thread stance (documented in code comment)
  should be revisited if PDF jobs are ever made concurrent.

## Cold Data Warning

This archive is historical evidence. Current requirements live in `contracts/` and
active project guidance.
