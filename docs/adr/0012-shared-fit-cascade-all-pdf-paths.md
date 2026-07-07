# ADR 0012: fit_text_cascade is the single fit/wrap authority for all PDF renderer paths

## Status
proposed

## Context
BR-40 (single-path-expansion-enforcement) confined the BR-36 fit cascade
(word-wrap + font-shrink + line/letter-spacing + controlled overflow +
truncation) to the fitz primary renderer path and the shared `bbox_reflow.py`
component, explicitly forbidding cascade/expansion logic in the legacy renderer
paths. The intent was to prevent duplicated, drifting fit logic. A side effect:
the ReportLab draw path (`render_text_region`, used by PDF side-by-side output
AND the fitz-crash fallback per BR-34) was left with only the legacy shrink-only
`fit_text_to_bbox`, which does no word-wrap and, on `fits=False`, still draws the
full unwrapped string at floor font size. Result: translated text overflows and
obscures adjacent content in both PDF presentation modes (pdf-text-overflow-fix).

The two draw call-sites already consume the same output shape — a list of
pre-wrapped lines plus a font size and line spacing. fitz draws each line via
`fitz.TextWriter.append`; ReportLab draws each line via `canvas.drawString`.
Wrapping and sizing are canvas-API-agnostic; only the terminal draw primitive
differs. `fit_text_cascade` and `_wrap_lines_simple` already live in
`text_region_renderer.py`, a shared module both paths import.

## Decision
Amend BR-40: `fit_text_cascade` (with `_wrap_lines_simple`) is the SINGLE shared
source of truth for text fit/wrap/truncation across ALL PDF renderer paths — the
fitz primary path AND the ReportLab side-by-side/fallback path — not fitz-only.
`render_text_region` calls `fit_text_cascade`, then `_wrap_lines_simple` on the
returned `fitted_text`/`font_size`, then draws each line with `canvas.drawString`,
honoring `line_spacing` and setting `render_truncated` on truncation (BR-38).
The BR-40 prohibition is re-scoped from "no cascade outside fitz + bbox_reflow"
to "no DUPLICATE or divergent cascade implementation anywhere; all PDF paths call
the one shared cascade." The legacy `fit_text_to_bbox` is no longer a fit
authority on PDF paths.

## Consequences
- BR-40 in `contracts/business/business-rules.md` must be amended (contract-reviewer
  owns) and its convergence test (`test_renderer_convergence.py`) updated to assert
  the shared-call, not the fitz-exclusivity, invariant.
- BR-36/BR-38/BR-84/BR-85 guarantees now hold on the side-by-side/fallback paths
  too; the fitz path is unchanged (must-not-regress reference).
- The `TextRegion`/placement plumbing must carry source style and an element
  reference so the cascade gets a faithful starting font and a truncation-marker
  target; without the element ref, fallback-path truncation degrades to log-only.
- Reversing this later (re-restricting the cascade to fitz and reviving a separate
  ReportLab fitter) would silently reintroduce the no-wrap overflow bug and split
  fit logic into two drifting implementations — hence this ADR records the
  single-authority decision durably.