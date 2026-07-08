# Change Request

## Original Request
Add a runtime, output-side **layout-QA safety net** for the PDF render path. After
a PDF is rendered (translated text inserted), re-open the output PDF and measure
two layout-fidelity signals:
1. **BIoU regression** — did the source bounding boxes survive translation
   insertion (mean best-match bbox IoU vs a regression budget)?
2. **Residual source text** — is untranslated source text still visible inside its
   own bbox region in the rendered output (a "text didn't get replaced" failure)?

When fidelity regresses below budget or residual source text is found, emit a
**fail-soft job warning** through the existing post-render warnings plumbing
(`warnings_callback` → `_record_job_warning`, the BR-96/BR-104 mechanism). Layout
QA must NEVER fail a job — any exception is logged and the pass is skipped.

Gate the whole feature behind a new `LAYOUT_QA_ENABLED` config flag (default off),
mirroring `LAYOUT_DETECTOR_ENABLED`. Reuse the existing standalone
`tests/metrics/{biou,residual_text,truncation_rate}.py` as the metric core
(promote/host them so both the CI gate and the runtime service share one
implementation).

## Business / User Goal
A translator gets an automatic, non-blocking warning when a translated PDF comes
out visually broken — boxes shifted (BIoU drop) or source text left untranslated
in place — instead of silently shipping a bad-looking document. This complements
the already-shipped truncation disclosure (BR-104), which only covers text
clipping, not bbox drift or untranslated leftovers.

## Non-goals
- NOT re-adding truncation disclosure — already shipped as **BR-104**
  (`pdf-render-truncation-disclosure`); this change must reuse it, not duplicate it.
- NOT reintroducing the extended BR-38 wording from PR #13 (BR-38 already exists on
  main as `no-silent-truncation`); no BR-38 edit.
- NOT failing/blocking jobs on layout QA — disclosure-only, fail-soft.
- NOT adding a new API endpoint or UI component — warnings surface through the
  existing `job.warnings` field/plumbing.
- NOT wiring QA into Office (docx/pptx/xlsx) paths — PDF output path only for now.

## Constraints
- Additive/observational only; no change to translation output or render pixels.
- `LAYOUT_QA_ENABLED` default **off** — zero behavior change unless explicitly enabled.
- Fail-soft: any exception inside the QA pass is caught, logged, and returns no
  warning (never propagates, never fails the job).
- Reuse `warnings_callback`/`_record_job_warning` (BR-96) — do not invent new
  warning plumbing.
- Metric functions stay stdlib-only + duck-typed (as the existing
  `tests/metrics/` versions already are).

## Known Context
- Design reference (CLOSED PR #13, do NOT merge/rebase): branch
  `claude/session-uu3mpx` — files `app/backend/services/layout_qa.py`,
  `tests/test_layout_qa.py`, `tests/test_layout_confirmation_warnings.py`,
  `docs/layout-pipeline-verification.md`. Use as a design reference for the metric
  and service shape; the truncation-disclosure parts of that branch are superseded
  by BR-104 and must be dropped.
- Existing on main: `tests/metrics/{biou,residual_text,truncation_rate}.py`
  (standalone, CI-gate tools per `contracts/ci/ci-gate-contract.md`);
  `warnings_callback` post-render plumbing (BR-96); truncation disclosure (BR-104);
  `LAYOUT_DETECTOR_ENABLED` flag pattern in `config.py`.
- Likely fix seam: `app/backend/processors/orchestrator.py` PDF render/dispatch
  branch (where BR-104's post-render sweep already runs), a new
  `app/backend/services/layout_qa.py`, and `config.py`.

## Open Questions
- Exact BIoU regression budget default (PR #13 used 0.8) — confirm with
  contract-reviewer/planner; treat as a documented constant.
- Whether the metric core should physically move into
  `app/backend/services/layout_qa.py` with `tests/metrics/` re-exporting, or the
  service should import from `tests/metrics/` — planner to decide (avoid duplicating
  the metric logic either way).

## Success Criterion
With `LAYOUT_QA_ENABLED=true`, after a PDF render whose output has (a) mean BIoU
below the regression budget, or (b) residual untranslated source text in a bbox,
`run_layout_qa(...)` returns a result that causes exactly one aggregated
`job.warnings` entry to be emitted via `warnings_callback` — and never raises, and
never alters rendered output. With `LAYOUT_QA_ENABLED=false` (default), no QA runs
and behavior is byte-for-byte unchanged.

## Requested Delivery Date / Priority
Follow-up salvage of the valuable part of closed PR #13; normal priority.
