---
change-id: p1-font-lru-cache
schema-version: 0.1.0
last-changed: 2026-06-17
risk: low
tier: 0
---

# Test Plan: p1-font-lru-cache

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | unit | tests/test_pdf_generator.py::TestFontBufferCache::test_first_call_reads_disk_once | 0 |
| AC-2 | unit | tests/test_pdf_generator.py::TestFontBufferCache::test_second_call_hits_cache_not_disk | 0 |
| AC-3 | unit | tests/test_pdf_generator.py::TestFontBufferCache::test_distinct_paths_cached_independently | 0 |
| AC-4 | unit | tests/test_pdf_generator.py::TestFontBufferCache::test_cached_and_uncached_render_output_equivalent | 0 |
| AC-5 | regression | tests/test_pdf_generator.py | 0 |

## Test Families Required

| family | tier | notes |
|---|---|---|
| unit | 0 | Spy on `open()` scoped to `app.backend.renderers.pdf_generator` to count disk reads per font path. Cache must be cleared in a `setup_method` / `autouse` fixture. |
| regression | 0 | Full run of pre-existing `TestPDFGenerator`, `TestGenerateTranslatedPdf`, `TestPDFGeneratorEdgeCases` proves AC-5 (no caller-visible behavior change). |

## New Tests (extend `tests/test_pdf_generator.py`, new class `TestFontBufferCache`)

- `test_first_call_reads_disk_once` — one `_insert_text_in_rect` call for a known font path; assert `open` called exactly once.
- `test_second_call_hits_cache_not_disk` — two calls for the same path; assert `open` call count stays at 1.
- `test_distinct_paths_cached_independently` — one call each for two distinct paths; assert `open` call count equals 2.
- `test_cached_and_uncached_render_output_equivalent` — compare font buffer bytes from a warm-cache call and a cache-reset call; assert they are identical.
- `test_error_path_does_not_cache_bad_buffer` — simulate unreadable font on first call; assert cache has no entry and next call re-attempts disk read.
- `test_cache_reset_between_tests` — call `clear_font_cache()` helper; assert next call re-reads disk.

## Execution Ladder

| phase | command |
|---|---|
| collect | `pytest --collect-only tests/test_pdf_generator.py` |
| targeted | `pytest tests/test_pdf_generator.py` |
| changed-area | `pytest tests/test_pdf_generator.py` |
| full | `pytest tests/` |

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| (none) | — | No existing test behavior changes; cache is implementation-internal. |

## Out of Scope

- Thread-safety stress testing (single-threaded design; stance recorded in implementation-plan).
- Path-normalization aliasing (relative vs. absolute path same file) — out of scope for this change.
- Integration tests against a live PDF render pipeline.
- Font file presence on CI runners — new tests must stub the file read.

## Notes

- Patch `open` at `app.backend.renderers.pdf_generator` import scope, not globally.
- Expose `clear_font_cache()` as a named public helper so tests reset state without touching private internals.
- All new tests go in the existing `tests/test_pdf_generator.py`; no new test files required.
