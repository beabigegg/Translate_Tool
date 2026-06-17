---
change-id: p1-font-lru-cache
schema-version: 0.1.0
last-changed: 2026-06-17
---

# Implementation Plan: p1-font-lru-cache

## Objective
Eliminate redundant per-call disk reads of the target-language font file in
`PDFGenerator._insert_text_in_rect` by introducing a module-level, resettable
in-memory font-buffer cache. Caller-visible behavior of `_insert_text_in_rect`
must remain byte-equivalent (no contract change).

## Execution Scope

### In Scope
- `app/backend/renderers/pdf_generator.py`: add a cached font-buffer loader and a
  `clear_font_cache()` reset hook; route the existing `open(font_file, "rb")`
  read (currently lines 423-425) through it.
- `tests/test_pdf_generator.py`: add `TestFontBufferCache` (6 tests, see Test Execution Plan).

### Out of Scope
- Path-normalization aliasing (relative vs absolute same file) — test-plan.md §Out of Scope.
- Thread-safety stress testing; multi-threaded render pipeline.
- Any change to `_get_font_file`, `font_utils.py`, or the fallback `fitz.Font(...)` paths.
- Contracts, API, CI workflow content (ci-cd-gatekeeper already added the gate line).

## Non-Goals
- Do not refactor font selection, `_wrap_text`, the sizing loop, or unrelated methods.
- Do not add locking; single-threaded PDF job model is the deliberate stance (document with a comment).
- Do not change observable output, signatures, or error semantics.

## Required Changes

| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | renderers | Read current `_insert_text_in_rect` font-load site (lines 421-440) and `_get_font_file` | backend-engineer |
| IP-2 | tests | Add `TestFontBufferCache` (all 6 tests) — must FAIL before IP-3 | backend-engineer |
| IP-3 | renderers | Implement module-level cached loader + `clear_font_cache()`; route the read through it | backend-engineer |
| IP-4 | tests | Run TDD ladder (collect/targeted/changed-area/full) per test-plan.md | backend-engineer |
| IP-5 | gate | Run `cdd-kit gate p1-font-lru-cache`; confirm pass | backend-engineer |

## Source Artifact Pointers

| source | relevant pointer | used for |
|---|---|---|
| test-plan.md | AC→Test Mapping table; New Tests list; Execution Ladder | tests to write / run |
| test-plan.md | Notes (patch `open` at module scope; named `clear_font_cache()`) | test + API constraints |
| ci-gates.md | Required Gates table; Promotion Policy | verification commands |
| change-classification.md | Inferred AC-1..AC-5; Risk Factors | cache key / error-path / reset constraints |
| pdf_generator.py:421-440 | `open(font_file, "rb")` read site | call site to reroute |

## File-Level Plan

| path or glob | action | notes |
|---|---|---|
| app/backend/renderers/pdf_generator.py | edit | Add module-level cached loader + `clear_font_cache()`; replace inline `open()` read |
| tests/test_pdf_generator.py | edit | Append `TestFontBufferCache` class + autouse cache-reset fixture |

## Contract Updates

- API: none
- CSS/UI: none
- Env: none
- Data shape: none
- Business logic: none
- CI/CD: none

(change-classification.md §Required Contracts: all none; caller-visible behavior unchanged.)

## Implementation Detail (IP-3)
- Add a module-level function, e.g. `_load_font_buffer(font_path: str) -> bytes`,
  decorated with `functools.lru_cache(maxsize=None)` (preferred over a raw dict for
  simplicity and the built-in `.cache_clear()`).
- Cache key: normalized absolute path — `os.path.realpath(font_path)` (or `Path.resolve()`),
  so relative/absolute references to the same file do not double-read. Aliasing
  correctness beyond this normalization is out of scope.
- Body reads via `open(<resolved path>, "rb")` and returns the bytes; on a read
  failure let the exception propagate (do NOT cache exceptions or empty buffers —
  `lru_cache` already stores nothing for a raising call).
- In `_insert_text_in_rect`, replace lines 423-425
  (`with open(font_file, "rb") as f: font_buffer = f.read()`) with
  `font_buffer = _load_font_buffer(font_file)`. Keep the surrounding `try/except`
  exactly as-is so the error-path fallback to `fitz.Font("helv")` is unchanged.
- Add `def clear_font_cache() -> None: _load_font_buffer.cache_clear()` as a named public helper.
- Add a one-line comment stating the deliberate no-lock / single-threaded-job assumption.

## Test Execution Plan

(Add an autouse fixture or `setup_method` in `TestFontBufferCache` that calls
`clear_font_cache()` before each test to prevent cross-test state bleed. Patch `open`
at `app.backend.renderers.pdf_generator` scope, never globally — test-plan.md Notes.)

| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 | tests/test_pdf_generator.py::TestFontBufferCache::test_first_call_reads_disk_once | `open` called exactly once |
| AC-2 | tests/test_pdf_generator.py::TestFontBufferCache::test_second_call_hits_cache_not_disk | `open` count stays at 1 |
| AC-3 | tests/test_pdf_generator.py::TestFontBufferCache::test_distinct_paths_cached_independently | `open` count == 2 |
| AC-4 | tests/test_pdf_generator.py::TestFontBufferCache::test_cached_and_uncached_render_output_equivalent | warm-cache vs reset-cache buffer bytes identical |
| (error path) | tests/test_pdf_generator.py::TestFontBufferCache::test_error_path_does_not_cache_bad_buffer | no cache entry; next call re-reads disk |
| (reset hook) | tests/test_pdf_generator.py::TestFontBufferCache::test_cache_reset_between_tests | `clear_font_cache()` forces re-read |
| AC-5 | tests/test_pdf_generator.py | existing TestPDFGenerator/TestGenerateTranslatedPdf/TestPDFGeneratorEdgeCases pass |

TDD order: write IP-2 tests first and confirm they FAIL, then implement IP-3.
Required phases (test-plan.md Execution Ladder): collect → targeted → changed-area → full.
Generate evidence with `cdd-kit test run`; the gate validates `test-evidence.yml`.

## Handoff Constraints

- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved.

## Known Risks

- Process-global mutable cache → cross-test bleed; mitigated by autouse `clear_font_cache()` fixture.
- Unguarded cache could race under concurrent calls; deliberately accepted (single-threaded job model), documented in code.
- Key correctness: relative vs absolute path miss-hit; mitigated by `realpath`/`resolve` normalization (full aliasing out of scope).
