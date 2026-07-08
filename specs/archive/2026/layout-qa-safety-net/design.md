# Design: layout-qa-safety-net

## Summary
Add a runtime, output-side layout-QA safety net for the PDF→PDF render path, gated by a new default-off `LAYOUT_QA_ENABLED` flag. After a PDF is rendered, a new fail-soft `run_layout_qa(...)` re-opens the output, measures mean best-match BIoU regression and residual source text against the source IR bboxes, and on regression emits exactly ONE aggregated `job.warnings` string through the existing BR-96/BR-104 `warnings_callback` → `_record_job_warning` plumbing. The metric core (`compute_biou`, `check_residual_text`, `compute_truncation_rate`, `BIOU_REGRESSION_BUDGET`) is promoted from the test tree into `app/backend/services/layout_qa.py` as the single source of truth, with `tests/metrics/*` reduced to re-export shims so both the CI gates and the runtime service share one implementation. Additive, observational, never alters output or fails a job.

## Affected Components
| component | file path(s) | nature of change |
|---|---|---|
| Layout-QA service (new) | `app/backend/services/layout_qa.py` | NEW — hosts promoted metric core + `run_layout_qa` composition; lazy `fitz` import; fail-soft |
| Metric re-export shims | `tests/metrics/biou.py`, `residual_text.py`, `truncation_rate.py` | MODIFIED — bodies replaced by re-exports from `layout_qa`; all public names incl. `_iou`, `BIOU_REGRESSION_BUDGET` preserved |
| PDF render seam | `app/backend/processors/pdf_processor.py` | MODIFIED — call `run_layout_qa(...)` in `_render_with_fallback` immediately after `_emit_truncation_disclosure_warning` (~L1160), guarded by `LAYOUT_QA_ENABLED` |
| Config flag | `app/backend/config.py` | MODIFIED — add `LAYOUT_QA_ENABLED` (default off), mirroring `LAYOUT_DETECTOR_ENABLED` (L176) |
| Warning plumbing | `app/backend/services/job_manager.py` | UNCHANGED — reuse `_record_job_warning`/`warnings_callback`; no new field |
| Env contract | `contracts/env/env-contract.md` (+ `.env.example.template`, `env.schema.json`) | MODIFIED — document `LAYOUT_QA_ENABLED` |
| Business rule | `contracts/business/business-rules.md` | MODIFIED — new BR-106 (next free above BR-105) |

## Key Decisions

- **1 — Metric-core hosting (module boundary).** Move the metric core into `app/backend/services/layout_qa.py` (module-level, stdlib-only, duck-typed) and make `tests/metrics/{biou,residual_text,truncation_rate}.py` thin re-export shims. Rationale: single source of truth lives in the shipped runtime tree; the runtime service imports its own module, never test-tree code. → **Rejected: runtime imports from `tests/metrics/`** — production importing the test tree is an anti-pattern; `tests/` is commonly excluded from packaged deploys, so an enabled QA pass would `ImportError` at runtime (latent, flag-gated). CI consequence: the gate commands in `ci-gate-contract.md` reference *test files* (`test_layout_metrics.py`, `test_pdf_layout_refactor.py`), NOT the `tests/metrics/*` module paths, so **no CI-contract tool-path edit is needed**. The shim MUST preserve `from tests.metrics.biou import compute_biou, _iou, BIOU_REGRESSION_BUDGET` etc. because `tests/test_layout_metrics.py` (L19-21, L93, L277-290) has explicit importability tests; keeping the shims means no import site breaks. See ADR 0015.

- **2 — Post-render seam.** BR-104's `render_truncated` sweep does NOT run in `orchestrator.py` (the change-request framing is imprecise); it runs in `pdf_processor.py::_render_with_fallback` at ~L1160 via `_emit_truncation_disclosure_warning(doc, doc_id, warnings_callback)`, PDF→PDF path only. `run_layout_qa(...)` is invoked at that exact seam because it is the only place with `doc` (source bboxes via `doc.elements`), the finalized `output_path`, `doc_id`, and `warnings_callback` all in scope, and it is reached only for `output_format=pdf`. → **Rejected: orchestrator `.pdf` branch (after L883)** — has `out_path` but no `doc`; would force `translate_pdf` to return the IR or a source re-parse, adding coupling and cost for no benefit.

- **3 — Aggregated-warning shape.** `_record_job_warning` (job_manager.py L146-156) appends a plain `str` to `job.warnings: Optional[List[str]]` with a dedup guard; BR-96/BR-104 warnings are plain strings. `run_layout_qa` emits exactly ONE aggregated string per file (BIoU-regression + residual-text signals combined, naming affected pages), mirroring `TEXT_TRUNCATION_WARNING_TEMPLATE`. No new field, no new category. → **`contracts/data/data-shape-contract.md` is NOT edited** (task 2.4 N/A, CER-002 stays unneeded); reuses the existing `List[str]` shape and plumbing.

- **4 — BIoU regression budget.** Reuse the existing named constant `BIOU_REGRESSION_BUDGET = 0.8` (currently in `tests/metrics/biou.py` L14), which moves to `app/backend/services/layout_qa.py` under Decision 1 and is re-exported. `run_layout_qa` flags regression when `mean_biou < BIOU_REGRESSION_BUDGET`. Kept a module constant (not env-configurable) to match its current form; may be promoted to config later if tuning is needed. → **Rejected: inline literal 0.8** — magic number, violates AC-9.

- **5 — Performance bound.** `compute_biou` is O(source_boxes × rendered_boxes). Two bounds: (a) match BIoU **per page** (source vs rendered boxes within the same `page_num`), turning a global product into Σ per-page products — this is also more correct (no cross-page matches) and aligns with residual-text's already page-scoped `get_text(clip=...)`; (b) a named short-circuit `LAYOUT_QA_MAX_BOXES_PER_PAGE` (default e.g. 500, in `layout_qa.py`) above which a page is skipped and logged, so a pathological page cannot dominate render time. Default-off means zero cost unless enabled; when enabled the pass is bounded. → **Rejected: global O(N×M) matching with no cap** — quadratic blow-up on large PDFs.

## Public surface of `run_layout_qa(...)`
```python
def run_layout_qa(doc, output_path, doc_id, warnings_callback, log=None) -> "LayoutQAResult | None":
    # Fail-soft: any exception (corrupt/unreadable PDF, metric error) → log + return None; never raises.
    # Re-open output_path (lazy `import fitz`); per page: source bboxes = doc.elements[page].bbox.
    #   Skip page if len(source) or len(rendered) > LAYOUT_QA_MAX_BOXES_PER_PAGE.
    #   mean_biou over pages via compute_biou(source, rendered); residual via check_residual_text(page, source).
    # If mean_biou < BIOU_REGRESSION_BUDGET OR residual records found:
    #     warnings_callback(one aggregated string naming affected pages)   # exactly one entry per file
    # Return LayoutQAResult(mean_biou, biou_regressed, residual_pages, warned) for test assertions; None when skipped.
```

## Migration / Rollback
Pure additive, default-off feature flag — no data migration, no schema change. Rollback is `LAYOUT_QA_ENABLED=false` (the default) or a plain `git revert`; with the flag off, behavior is byte-for-byte unchanged. The only cross-tree move is the metric core; the re-export shims keep `tests.metrics.*` import paths and all CI gates working, so reverting the move restores the standalone implementations with no contract downgrade.

## Contract scope for downstream reviewers
- **WILL touch:** `contracts/env/*` (new `LAYOUT_QA_ENABLED`), `contracts/business/business-rules.md` (new BR-106).
- **WILL NOT touch:** `contracts/ci/ci-gate-contract.md` (gate commands reference test files, not `tests/metrics/*` paths — re-hosting is transparent; ci-cd-gatekeeper should verify the shims keep `tests.metrics.*` importable so gate tests still resolve). `contracts/data/data-shape-contract.md` (reuses existing `job.warnings: List[str]` shape — no new field/category). `contracts/api/*` (no endpoint; non-goal).

## Open Risks
- The metric-core move creates a shared module consumed by both CI gate tests and runtime (the promoted "orphaned shared module" risk). Mitigation: shims + the existing `test_layout_metrics.py` importability tests; backend-engineer must grep all `tests.metrics.*` / `compute_biou` / `check_residual_text` import sites before marking done.
- `check_residual_text` as-hosted flags ANY text inside a source bbox; distinguishing residual *source* text from correctly-placed *translated* text is an implementation detail left to backend-engineer/test-strategist — over-eager warnings are the main false-positive risk, but fail-soft/observational nature caps the blast radius.
- Seam correctness depends on `_render_with_fallback` having the finalized `output_path` written before the call (it does — the sweep runs post-render). If the fitz→ReportLab fallback path changes the output-handle lifecycle, re-verify the QA call still sees a finalized file.
