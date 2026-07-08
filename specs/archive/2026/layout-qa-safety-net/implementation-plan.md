---
change-id: layout-qa-safety-net
schema-version: 0.1.0
last-changed: 2026-07-08
---

# Implementation Plan: layout-qa-safety-net

## Objective
Ship a runtime, output-side layout-QA safety net for the PDF→PDF render path,
gated by a new default-off `LAYOUT_QA_ENABLED` flag. When enabled, after a PDF is
rendered, a new fail-soft `run_layout_qa(...)` re-opens the output, measures mean
best-match BIoU regression and residual untranslated source text against the
source IR bboxes, and on regression emits exactly ONE aggregated `job.warnings`
string through the existing BR-96/BR-104 `warnings_callback` → `_record_job_warning`
plumbing. The BIoU/residual/truncation metric core is promoted from the test tree
into `app/backend/services/layout_qa.py` (single source of truth), with
`tests/metrics/*` reduced to re-export shims. Additive, observational, never
alters output, never fails a job, zero cost when the flag is off.

Design is locked in `design.md` (Decisions 1-5) and
`docs/adr/0015-layout-qa-metric-core-in-runtime.md`. Contracts are ALREADY
applied — do not re-plan them (see Contract Updates).

## Execution Scope

### In Scope
- New service module `app/backend/services/layout_qa.py`: hosts the promoted
  metric core + the `run_layout_qa(...)` composition (design.md "Public surface"
  + Decisions 1, 4, 5).
- Reduce `tests/metrics/{biou,residual_text,truncation_rate}.py` to re-export
  shims that import every public name from `layout_qa` (Decision 1, ADR-0015).
- Add the guarded `run_layout_qa(...)` call at the PDF post-render seam in
  `app/backend/processors/pdf_processor.py` (Decision 2 — see the seam-name
  correction in File-Level Plan / Known Risks).
- Add `LAYOUT_QA_ENABLED` (default false) and `LAYOUT_QA_MAX_BOXES_PER_PAGE`
  (default 500) to `app/backend/config.py` (Decision 5).
- Concrete residual-source-text disambiguation inside `run_layout_qa` (see
  dedicated section below).

### Out of Scope (do NOT do these)
- All change-request `## Non-goals`: no re-adding BR-104 truncation disclosure
  (reuse it), no BR-38 edit, no job failing/blocking, no new API endpoint or UI
  component, no Office (docx/pptx/xlsx) wiring.
- No contract edits — env + BR-106 are already written and applied (see Contract
  Updates). Do NOT touch `contracts/data/data-shape-contract.md` or
  `contracts/ci/ci-gate-contract.md` (design Decisions 1 & 3; ci-gates.md verdict).
- No change to `job_manager.py::_record_job_warning` / `warnings_callback`
  signature — reuse as-is (Decision 3; design "Affected Components" marks it
  UNCHANGED).
- No opportunistic refactor of `_dispatch_render`, the renderers, or the metric
  math. Metric bodies move verbatim; do not "improve" `compute_biou`/`_iou`/
  `check_residual_text`/`compute_truncation_rate`.
- No new third-party import at module import time — `fitz` stays a lazy
  in-function import (ADR-0015).

## Required Changes
| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | backend service | Create `app/backend/services/layout_qa.py`; move metric core (`BIOU_REGRESSION_BUDGET`, `_iou`, `compute_biou`, `check_residual_text`, `compute_truncation_rate`) verbatim from `tests/metrics/*`; add `run_layout_qa(...)` + `LayoutQAResult`; lazy `import fitz`; fail-soft wrap | backend-engineer |
| IP-2 | test-tree shims | Replace bodies of `tests/metrics/biou.py`, `residual_text.py`, `truncation_rate.py` with re-exports from `app.backend.services.layout_qa`, preserving EVERY public name (incl. private `_iou` and `BIOU_REGRESSION_BUDGET`) | backend-engineer |
| IP-3 | render seam | In `pdf_processor.py::_dispatch_render`, immediately after the L1160 `_emit_truncation_disclosure_warning(doc, doc_id, warnings_callback)` call, add a `LAYOUT_QA_ENABLED`-guarded `run_layout_qa(doc, output_path, doc_id, warnings_callback, log=log)` call (PDF→PDF path only) | backend-engineer |
| IP-4 | config | Add `LAYOUT_QA_ENABLED` (bool, default false) + `LAYOUT_QA_MAX_BOXES_PER_PAGE` (int, default 500) to `config.py`, mirroring `LAYOUT_DETECTOR_ENABLED` (L176) | backend-engineer |
| IP-5 | residual disambiguation | Implement source-vs-translated discrimination in `run_layout_qa` (see dedicated section) — do NOT feed raw `check_residual_text` output into the warning | backend-engineer |
| IP-6 | verification | Grep every importer of `tests.metrics.*` / `compute_biou` / `check_residual_text` / `_iou` / `BIOU_REGRESSION_BUDGET`; confirm none breaks after the move (shared-module orphan check) | backend-engineer |

## Source Artifact Pointers
| source | relevant pointer | used for |
|---|---|---|
| design.md | "Public surface of `run_layout_qa(...)`" (L29-39) | `run_layout_qa` signature + return contract |
| design.md | Decision 1 + ADR-0015 | metric-core hosting + shim rule (preserve all public names) |
| design.md | Decision 2 | post-render seam placement (see seam-name correction below) |
| design.md | Decision 3 | aggregated single-`str` warning shape; reuse `_record_job_warning` |
| design.md | Decision 4 | `BIOU_REGRESSION_BUDGET = 0.8` named constant; flag when `mean_biou < budget` |
| design.md | Decision 5 + Open Risks (residual) | per-page BIoU + `LAYOUT_QA_MAX_BOXES_PER_PAGE` cap; residual disambiguation is the flagged open detail |
| test-plan.md | AC→test mapping table, "Test Families Required" | tests to run/write + phases |
| ci-gates.md | "Required Gates for This Change" table | verification commands (`pytest tests/`, `residual-text` gate, `cdd-kit gate/validate`) |
| contracts/business/business-rules.md | BR-106 (L117) | already-applied behavior contract this code must satisfy |
| contracts/env/env-contract.md | `LAYOUT_QA_ENABLED` / `LAYOUT_QA_MAX_BOXES_PER_PAGE` entries | already-applied env contract for the two new flags |
| app/backend/processors/pdf_processor.py | `_dispatch_render` L1094-1160; `_emit_truncation_disclosure_warning` L1163-1185; `TEXT_TRUNCATION_WARNING_TEMPLATE` L53 | seam + warning-string template to mirror |
| app/backend/services/job_manager.py | `_record_job_warning` L146-156 | warning-append plumbing (reuse, do not re-invent) |
| app/backend/config.py | `LAYOUT_DETECTOR_ENABLED` L176 | flag-declaration pattern to mirror |

## File-Level Plan
| path or glob | action | notes |
|---|---|---|
| `app/backend/services/layout_qa.py` | CREATE | Module-level metric core moved verbatim from `tests/metrics/*` (stdlib-only, duck-typed). Add `LayoutQAResult` (fields `mean_biou`, `biou_regressed`, `residual_pages`, `warned` — design L38) and `run_layout_qa(doc, output_path, doc_id, warnings_callback, log=None) -> LayoutQAResult | None`. `import fitz` lazy inside `run_layout_qa`. Whole pass wrapped fail-soft (catch `Exception`, log, return `None`; do NOT catch `BaseException`/`KeyboardInterrupt`). Aggregated warning string mirrors `TEXT_TRUNCATION_WARNING_TEMPLATE` shape (names doc id + page numbers). Read `LAYOUT_QA_ENABLED`/`LAYOUT_QA_MAX_BOXES_PER_PAGE`/`BIOU_REGRESSION_BUDGET` as this module's own names/config imports. |
| `tests/metrics/biou.py` | MODIFY | Replace body with `from app.backend.services.layout_qa import BIOU_REGRESSION_BUDGET, _iou, compute_biou  # re-export`. Keep all three importable from this path. |
| `tests/metrics/residual_text.py` | MODIFY | Replace body with `from app.backend.services.layout_qa import check_residual_text  # re-export`. |
| `tests/metrics/truncation_rate.py` | MODIFY | Replace body with `from app.backend.services.layout_qa import compute_truncation_rate  # re-export`. |
| `tests/metrics/__init__.py` | KEEP | Currently empty; leave empty. |
| `app/backend/processors/pdf_processor.py` | MODIFY | In `_dispatch_render` (L1094-1160), after L1160 `_emit_truncation_disclosure_warning(...)`, add a `LAYOUT_QA_ENABLED` guard (import from `app.backend.config`) then `run_layout_qa(doc, output_path, doc_id, warnings_callback, log=log)` (import from `app.backend.services.layout_qa`). Seam already has `doc`, `output_path`, `doc_id`, `warnings_callback` in scope. Do not restructure the fitz→ReportLab fallback. |
| `app/backend/config.py` | MODIFY | Add near L176: `LAYOUT_QA_ENABLED: bool = os.environ.get("LAYOUT_QA_ENABLED", "false").lower() in ("1", "true", "yes")` and `LAYOUT_QA_MAX_BOXES_PER_PAGE: int = int(os.getenv("LAYOUT_QA_MAX_BOXES_PER_PAGE", "500"))`, with a comment mirroring the `LAYOUT_DETECTOR_ENABLED` block. |
| `tests/test_layout_qa.py` | CREATE (test-strategist) | Unit / data-boundary / resilience / shim-identity / BR-106-presence / office-absence per test-plan.md AC map. |
| `tests/test_pdf_render_warnings.py` | MODIFY (test-strategist) | Add `TestLayoutQaDisabled` / `TestLayoutQaWarning` sibling classes reusing `TestTruncationDisclosureWarning`'s `_make_doc`/`_make_job`. NOTE: not currently in the manifest Allowed Paths — see Known Risks. |
| `tests/test_env_contract.py` | MODIFY (test-strategist) | Assert both new flags declared + `LAYOUT_QA_ENABLED` default false. |

> Seam-name correction (load-bearing): design.md and BR-106 describe the seam as
> `_render_with_fallback`, but no function of that name exists. The real seam is
> `pdf_processor.py::_dispatch_render` (L1094-1160); the BR-104 sweep it must sit
> beside is the `_emit_truncation_disclosure_warning(doc, doc_id, warnings_callback)`
> call at L1160. Insert the `run_layout_qa` call there. The `_render_with_fallback`
> label in the contract/design is descriptive, not a literal symbol — do not create
> or rename a function to match it.

## Residual-source-text disambiguation (design.md Open Risk — concrete resolution)
`check_residual_text(page, bboxes)` flags ANY text inside a bbox, so calling it
raw against source bboxes on a rendered output would flag every correctly
TRANSLATED box as "residual." `run_layout_qa` MUST discriminate leftover SOURCE
text from correctly-placed translated text. Required approach:

1. Keep `check_residual_text` UNCHANGED as the shared low-level primitive (its
   CI-gate callers depend on the current any-text semantics; do not narrow it).
2. In `run_layout_qa`, per page, build `(bbox, source_string)` pairs from the
   page's source elements (`doc.elements` filtered by `page_num`). Read the
   source string duck-typed and defensively, exactly like the existing
   truncation code reads element attrs: `getattr(elem, "text", "") or ""`
   (the truncation sweep uses `getattr(elem, "render_truncated", False)` and
   `elem.page_num`; follow that pattern — do NOT import the `TranslatableElement`
   model).
3. Query the rendered clip text for each bbox (via `check_residual_text` records,
   or a direct `page.get_text("text", clip=(x0,y0,x1,y1))`), normalize both the
   source string and the rendered clip text identically (strip + casefold +
   collapse internal whitespace).
4. Flag a page as having residual source text ONLY when a source element's
   normalized source string is non-empty AND still appears as a substring of its
   own bbox's normalized rendered text — i.e. the box was NOT replaced by the
   translation. A box whose rendered text is the translated string (source string
   absent) is NOT flagged.
5. Skip elements whose source string is empty/whitespace. Edge case:
   untranslatable segments where source == translation may self-flag; acceptable
   given the fail-soft, observational, default-off nature — record any
   residual-tuning observation in the qa-reviewer log rather than adding
   suppression complexity.

This is the primary approach. The narrower acceptable fallback the design
permits — "flag only EXACT source-string matches remaining" (normalized equality
instead of substring containment in step 4) — is allowed if substring proves
noisy, but containment is preferred for catching partially-untranslated boxes.
Do NOT leave this undefined and do NOT emit warnings from raw `check_residual_text`.

## `run_layout_qa` public signature + return contract
Per design.md L29-39 (do not deviate):

- Signature: `run_layout_qa(doc, output_path, doc_id, warnings_callback, log=None) -> "LayoutQAResult | None"`.
- Re-opens `output_path` with a lazy `import fitz`. Per page: source bboxes from
  `doc.elements` (that page), rendered boxes from the reopened output.
- Skip a page whose source or rendered box count exceeds
  `LAYOUT_QA_MAX_BOXES_PER_PAGE` (log it; excluded from BIoU matching).
- `mean_biou` computed per page via `compute_biou(source, rendered)`; residual via
  the disambiguated logic above.
- If `mean_biou < BIOU_REGRESSION_BUDGET` OR residual records found →
  `warnings_callback(<one aggregated string naming affected pages>)`. Exactly ONE
  entry per file; both signals combine into the SAME entry when both fire.
- Returns `LayoutQAResult(mean_biou, biou_regressed, residual_pages, warned)` for
  test assertions; returns `None` when skipped (flag off, no `doc`, or fail-soft
  exception). NEVER raises; NEVER alters rendered output.

## Contract Updates (ALREADY APPLIED — verify only, do not re-author)
- API: none (non-goal; no endpoint; no `openapi.yml` re-export).
- CSS/UI: none (non-goal).
- Env: DONE — `LAYOUT_QA_ENABLED` (default off) + `LAYOUT_QA_MAX_BOXES_PER_PAGE`
  live in `contracts/env/env-contract.md`, `contracts/env/.env.example.template`,
  `contracts/env/env.schema.json`. Backend-engineer must keep `config.py` defaults
  byte-consistent with these (false / 500) so `tests/test_env_contract.py` passes.
- Data shape: NOT edited (Decision 3 — reuses existing `job.warnings: List[str]`
  shape; CER-002 stays unneeded).
- Business logic: DONE — BR-106 (`layout-qa-safety-net-disclosure`) at
  `contracts/business/business-rules.md` L117. Code must satisfy it. Do NOT touch
  BR-38 or BR-104.
- CI/CD: NOT edited (Decision 1 + ci-gates.md verdict — gate commands reference
  test files, not `tests/metrics/*` module paths; re-host is CI-transparent).

## Test Execution Plan
Run all phases in the `translate-tool` conda env so `torch`/`fitz` resolve (per
CLAUDE.md QE/COMET note): `conda run -n translate-tool cdd-kit test run <id> --phase <p>`.
Required floor: collect, targeted, changed-area; add contract (env + BR-106 are
affected). Full ladder + families in test-plan.md; ADR-0005 bounded ladder.
Selection: `cdd-kit test select` reads test-plan.md's AC→test map first.

| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 (flag-off no-op) | tests/test_pdf_render_warnings.py::TestLayoutQaDisabled::test_flag_off_run_layout_qa_not_invoked_no_warning | metric fns never called; no new `job.warnings` entry |
| AC-2 (BIoU regression) | tests/test_layout_qa.py::test_biou_regression_below_budget_emits_one_aggregated_warning | exactly one aggregated warning naming affected pages |
| AC-2 (real seam) | tests/test_pdf_render_warnings.py::TestLayoutQaWarning::test_biou_regression_warning_fires_through_real_seam | one `job.warnings` via `warnings_callback`→`_record_job_warning` |
| AC-3 (residual + aggregation) | tests/test_layout_qa.py::test_residual_source_text_emits_warning | residual path warns; both signals → SAME single entry |
| AC-4 (fail-soft) | tests/test_layout_qa.py::test_metric_exception_is_caught_returns_none_no_warning | exception caught, returns None, no warning |
| AC-4 (data-boundary) | tests/test_layout_qa.py::test_page_over_max_boxes_per_page_short_circuits_without_raising | no raise; over-cap page skipped+logged |
| AC-4 (job unaffected) | tests/test_pdf_render_warnings.py::TestLayoutQaWarning::test_layout_qa_exception_never_fails_job_or_fabricates_warning | job succeeds; no fabricated warning |
| AC-5 (shim identity) | tests/test_layout_qa.py::TestMetricCoreIdentity | shim names are the SAME objects as runtime; `_iou`/`BIOU_REGRESSION_BUDGET` importable from shim |
| AC-5 (existing stays green) | tests/test_layout_metrics.py | `TestModuleImports` (L277-291, L19-21) still passes after the move |
| AC-6 (env contract) | tests/test_env_contract.py::TestEnvContractDeclared | both flags declared; `LAYOUT_QA_ENABLED` default false in config |
| AC-7 (BR-106 present) | tests/test_layout_qa.py::test_br_106_documented_in_business_rules | BR-106 text present |
| AC-8 (PDF-only) | tests/test_layout_qa.py::test_office_processors_do_not_import_run_layout_qa | docx/pptx/xlsx processors never import `run_layout_qa` |
| AC-9 (named constant) | tests/test_layout_qa.py::test_biou_regression_budget_is_named_constant_and_consumed_by_run_layout_qa | `BIOU_REGRESSION_BUDGET` (not literal 0.8) drives the flag |
| CI gate (must stay green) | `pytest tests/test_pdf_layout_refactor.py -k "residual_text" --tb=short -q` | residual source-text count = 0 (ci-gates.md `residual-text` gate) |

## Handoff Constraints
- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into
  this plan; follow the source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and
  report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion
  Request is approved. The PR #13 branch (`claude/session-uu3mpx`) is OUT OF
  SCOPE to read (design reference only).
- Metric bodies move verbatim; the `run_layout_qa` signature is locked to
  design.md L31 — do not add/remove parameters.

## Known Risks
- SEAM NAME MISMATCH: design.md/BR-106 say `_render_with_fallback`; the real seam
  is `_dispatch_render` (pdf_processor.py L1094-1160), beside the L1160
  `_emit_truncation_disclosure_warning` call. Wire there; do not chase the
  descriptive label.
- SHARED-MODULE ORPHAN (CLAUDE.md learning + design Open Risks): after moving the
  metric core, GREP every importer of `tests.metrics.biou/residual_text/truncation_rate`
  and of `compute_biou`/`check_residual_text`/`_iou`/`BIOU_REGRESSION_BUDGET`
  (notably `tests/test_layout_metrics.py` L19-21, L93, L277-291, and
  `tests/test_pdf_layout_refactor.py`) and confirm none breaks. The shim MUST
  re-export the PRIVATE `_iou` and the `BIOU_REGRESSION_BUDGET` constant, not just
  the public functions — `test_layout_metrics.py` imports them explicitly.
- TEST-PATH SCOPE GAP: test-plan.md maps AC-1/2/4/8 integration tests to
  `tests/test_pdf_render_warnings.py`, but that file is NOT in the context-manifest
  Allowed Paths (nor in test-strategist's/backend-engineer's work packets). The
  manifest lists `tests/test_orchestrator_judge.py` only as the reference pattern.
  The orchestrating agent must expand Allowed Paths (or approve a CER) to include
  `tests/test_pdf_render_warnings.py` before those integration tests are written,
  or route the integration tests into an already-allowed file.
- CONDA ENV FOR TESTS: `run_layout_qa`'s lazy `import fitz` and QE-adjacent tests
  hard-error outside the `translate-tool` env; generate all `cdd-kit test run`
  evidence via `conda run -n translate-tool ...` (CLAUDE.md).
- RESIDUAL FALSE POSITIVES: over-eager residual flagging is the main false-positive
  vector; the disambiguation section bounds it, but source==translation segments
  may self-flag — acceptable under fail-soft/observational scope; record any
  residual-tuning observation in the qa-reviewer log, do not add suppression logic.
- SEAM FILE FINALIZATION: `run_layout_qa` requires `output_path` to be a finalized
  written file at the call site (it is — the sweep runs post-render). If the
  fitz→ReportLab fallback output-handle lifecycle changes, re-verify the QA call
  still sees a written file (design Open Risks; CER-001 covers the renderer files
  if the seam proves unresolvable there).
- `.cdd/code-map.yml` is fresh (generated 2026-07-08, this change's date); no
  staleness caveat.
