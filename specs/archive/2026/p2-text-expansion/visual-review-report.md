# Visual Review Report

## Change
p2-text-expansion — 5-step fit cascade + metric-compatible font fallback

## Affected Screens
Backend PDF rendering output (rendered page regions for text elements, all document types processed by fitz_renderer.py).
No web UI surface. Visual acceptance is evaluated against rendered bbox geometry and glyph presence.

## Viewports Checked
Not applicable — output is a PDF document surface, not a browser viewport.
The equivalent axis is: page format (A4, Letter), language pair (en→de, en→es), and bbox tightness (generous / typical / tight).

## States Checked
| State | Coverage |
|---|---|
| Text fits without cascade | Covered by functional unit tests (generous bbox) |
| Font-size shrink fires (step a) | Covered by functional unit test (narrow bbox, `test_cascade_step_order_font_before_line_spacing`) |
| Line-spacing compression fires (step b) | Covered by functional unit test (font_size < min, line_spacing asserted in [1.0, 1.15]) |
| Letter-spacing reduction fires (step c) | Covered by functional unit test (letter_spacing >= -0.005 floor asserted) |
| Controlled overflow fires (step d) | Step d is **documented degraded behavior**: `available_whitespace_below=0.0` always passed from fitz_renderer; step d is always skipped per backend-engineer log and design Open Risk |
| Truncation fires (step e) | Covered by functional unit tests (small bbox, ellipsis marker asserted) |
| Rendered PDF — en→de benchmark | **NOT COVERED** — no committed rendered output in fixtures/golden/expansion/ |
| Rendered PDF — en→es benchmark | **NOT COVERED** — no committed rendered output in fixtures/golden/expansion/ |
| Tofu glyph absence | Partially covered: fallback chain unit test (`get_metric_compatible_fallback` returns non-empty string); no rendered glyph image evidence |

## Evidence
- screenshots: **none** — `tests/fixtures/golden/expansion/` is empty (directory exists, zero files)
- videos: none
- diff reports: none
- functional test output: 575 passed, 3 skipped, 0 failed (backend-engineer.yml; full suite run 2026-06-18)
- benchmark test file: `tests/test_text_expansion_benchmark.py` present and passing (in-memory assertions only)

## CSS Contract Findings
Not applicable — this change has no CSS or web UI surface. No design-token violations. No shared component contract findings.

## AC Findings

### AC-1: en→de rendered output has 0 bbox overflow across golden sample set
**BLOCKED — no visual evidence.**
`TestEnDeBenchmark` in `tests/test_text_expansion_benchmark.py` asserts the cascade returns non-empty `fitted_text` and `truncated=False` on a generous in-memory bbox for 5 parametrized translation pairs. This is a functional assertion on the cascade helper directly, not a rendered PDF geometry check.
No committed baseline/current rendered page images exist in `tests/fixtures/golden/expansion/`.
The `text-expansion-benchmark` CI gate as implemented cannot confirm 0 bbox overflow on real rendered pages.

### AC-2: en→es rendered output has 0 bbox overflow across golden sample set
**BLOCKED — no visual evidence.**
Same situation as AC-1. `TestEnEsBenchmark` passes functionally against in-memory cascade decisions; no rendered PDF output for the benchmark pairs has been committed.

### AC-3: 0 tofu boxes in benchmark set (metric-compatible font fallback fires correctly)
**PARTIALLY MET — no rendered glyph evidence.**
`TestMetricFallbackZeroTofu::test_fallback_always_returns_string` asserts `get_metric_compatible_fallback` returns a non-empty font name for `target_char="Ä"`. This confirms the fallback chain does not return None or empty string, preventing a code path that would produce tofu.
However, no rendered PDF pages with Umlaut or non-Latin characters have been committed or inspected. Rendered glyph evidence (screenshot or PDF page image) confirming 0 tofu boxes is absent.

### AC-4: Cascade steps applied in correct order (visual evidence: font-size reduction visible before truncation)
**FUNCTIONALLY MET, NOT VISUALLY CONFIRMED.**
`TestCascadeContract::test_cascade_step_order_font_before_line_spacing` asserts step (a) fires before step (b) by checking `font_size < 11.0` and `line_spacing` in [1.0, 1.15].
No rendered side-by-side comparison image exists showing font-size reduction in a real page region before truncation triggers. Visual confirmation of cascade step ordering requires a rendered output image where intermediate cascade states can be observed across a set of increasingly tight bboxes.
Step (d) controlled overflow is confirmed permanently disabled (degraded behavior, `available_whitespace_below=0.0` hardcoded). This narrows the effective cascade to 4 steps in practice.

### AC-5: Truncated text shows ellipsis marker (not abrupt cut)
**FUNCTIONALLY MET, NOT VISUALLY CONFIRMED.**
`TestCascadeContract::test_cascade_truncated_text_ends_with_ellipsis` and `TestEnDeBenchmark::test_truncated_flag_set_when_forced` both assert `fitted_text.endswith("…")` when `truncated=True`.
No rendered page image showing the ellipsis marker in an actual PDF text region has been committed. The IR `render_truncated` field is tested by `TestRenderTruncatedField` (backend-engineer.yml). Machine-readability is confirmed; visual rendered appearance of the ellipsis in context is not confirmed.

## Blocking Issues

**BLOCKER-1: `tests/fixtures/golden/expansion/` is empty.**
The `change-classification.md` states: "durable visual evidence bundle for en→de/es benchmark is primary acceptance proof." The directory exists but contains zero files. No rendered output artifacts (rendered PDF pages, page images, pixel diff reports, or screenshots comparing before/after) have been committed. The `text-expansion-benchmark` CI gate tests the cascade helper in memory; it does not render or inspect actual PDF page output. Without committed rendered artifacts, the visual acceptance criteria (AC-1, AC-2, AC-3 rendered evidence) cannot be signed off.

**BLOCKER-2: Step (d) controlled overflow permanently disabled.**
The backend-engineer agent log documents that `available_whitespace_below=0.0` is hardcoded in `fitz_renderer._insert_text_in_rect` because fitz does not expose neighbor geometry. Design.md listed this as an Open Risk. AC-4 as stated ("cascade steps applied in correct order") covers a 4-step cascade in practice (not 5). This is not a visual review blocker in itself, but it must be documented in `design.md` and `contracts/business/business-rules.md` as a permanent limitation before QA sign-off. The visual review cannot confirm step (d) behavior because it cannot fire.

## Approved-With-Risk Items
None — change is classified **blocked** pending resolution of BLOCKER-1. No items can be approved-with-risk when the primary acceptance evidence is absent.

## Required Remediation (before re-review)

1. **Commit rendered benchmark artifacts to `tests/fixtures/golden/expansion/`.**
   For each of the 5 en→de pairs and 5 en→es pairs: render the translated text into a representative tight bbox (equivalent to a real document region, not the generous 300×60 test bbox) using `fitz_renderer.py`, export the PDF page as a PNG or a bbox-annotated image, and commit the output. Overlay or annotate bbox boundaries so overflow is visually inspectable.
   Alternatively, commit rendered PDF pages from a real document sample with annotated bbox geometry data (JSON sidecar) so overflow can be programmatically confirmed from the rendered page.

2. **Commit a rendered tofu-validation image for AC-3.**
   Render a page containing known Umlaut or other non-Latin characters (e.g. German "Einstellungen" with ä/ö/ü, or a CJK fallback trigger) using the fallback chain, export as PNG, and commit it to `tests/fixtures/golden/expansion/`. The image should show 0 tofu boxes (no empty squares).

3. **Update `tests/fixtures/golden/README.md`** to document provenance for any new expansion fixtures.

4. **Document step (d) degradation in `contracts/business/business-rules.md` and `design.md`** as a permanent limitation (not just an Open Risk), so the 4-step effective cascade is the normative specification going forward.

## Decision
**blocked**

Visual acceptance evidence required by `change-classification.md` ("durable visual evidence bundle") is absent. `tests/fixtures/golden/expansion/` is empty. All AC-1/AC-2/AC-3 visual findings are blocked. Functional tests pass (575/0), but functional passage of in-memory cascade assertions does not substitute for rendered output inspection per the acceptance criteria definition. Re-submit after committing rendered benchmark artifacts and addressing BLOCKER-1.
