# Archive — layout-qa-safety-net

## Change Summary
Added a runtime, output-side **layout-QA safety net** for the PDF render path,
salvaging the still-valuable part of the closed PR #13 (branch
`claude/session-uu3mpx`) as a clean re-implementation on current `main` rather
than rebasing 31 commits. When `LAYOUT_QA_ENABLED=true`, after a PDF is rendered
`run_layout_qa()` re-opens the output and measures per-page **BIoU regression**
(mean best-match bbox IoU vs `BIOU_REGRESSION_BUDGET=0.8`) and **residual
untranslated source text**, emitting exactly one aggregated `job.warnings` entry
via the existing BR-96/BR-104 `warnings_callback` plumbing. Fail-soft (never fails
a job), default-off, PDF output path only. Governed by new **BR-106**.

## Final Behavior
- `LAYOUT_QA_ENABLED=false` (default): no QA pass; rendered output + job behavior
  byte-for-byte unchanged.
- `LAYOUT_QA_ENABLED=true`: a PDF whose output has BIoU below budget and/or
  residual source text produces ONE aggregated `job.warnings` entry (naming doc id
  + affected pages); both signals combine into the same entry. Any exception is
  caught+logged, no warning fabricated, job never fails.
- Complements (does not duplicate) BR-104's truncation disclosure — catches
  *untranslated leftovers* and *bbox drift*, which truncation disclosure does not.

## Final Contracts Updated
- `contracts/env/env-contract.md` — `LAYOUT_QA_ENABLED` (default false) +
  `LAYOUT_QA_MAX_BOXES_PER_PAGE` (default 500); schema-version 0.15.0 → 0.16.0.
- `contracts/env/.env.example.template`, `contracts/env/env.schema.json` — both vars.
- `contracts/business/business-rules.md` — **BR-106** (`layout-qa-safety-net-disclosure`);
  schema-version 0.24.2 → 0.25.0. Seam named `pdf_processor._dispatch_render` (corrected
  from the nonexistent `_render_with_fallback`).
- `contracts/CHANGELOG.md` — `[env 0.16.0]` + `[business 0.25.0]`.
- No edit to api-contract, data-shape (warning reuses existing `job.warnings: string[]`),
  or ci-gate-contract (CI references test files, not `tests/metrics/*` module paths).
- `docs/adr/0015-layout-qa-metric-core-in-runtime.md` — the metric-core-hosting decision.

## Final Tests Added / Updated
- `app/backend/services/layout_qa.py` (new) — metric core + `run_layout_qa`.
- `tests/metrics/{biou,residual_text,truncation_rate}.py` — reduced to re-export shims.
- `tests/test_layout_qa.py` (new) — AC-2..AC-9 (BIoU regression, residual
  disambiguation, aggregation, fail-soft, data-boundary, shim import-identity,
  named-constant, BR-106 presence, Office-absence).
- `tests/test_pdf_render_warnings.py` — `TestLayoutQaDisabled` (asserts
  `run_layout_qa.assert_not_called()`) + `TestLayoutQaWarning` (drives real
  `_dispatch_render` seam).
- `tests/test_env_contract.py` — AC-6 flag/default tests.
- Full smoke: 1217 passed / 0 failed / 4 skipped.

## Final CI/CD Gates
- `contract-and-fast-tests` (required) + `full-regression` (informational) — green on PR #22.
- All format/renderer gates green; no new workflow/job/secret (blanket pytest +
  `cdd-kit validate --contracts` auto-cover the new tests + contract edits).

## Production Reality Findings
- **Seam-name drift**: design.md / ADR / spec-architect log named a nonexistent
  `_render_with_fallback`; the real post-render seam is
  `pdf_processor._dispatch_render` (at BR-104's `_emit_truncation_disclosure_warning`
  site). implementation-planner (which has shell access) caught it against live
  source; BR-106 + code use the correct name. Root: no-shell planning agents read
  `.cdd/code-map.yml` as a static snapshot and can name a symbol that doesn't exist.
- **Metric-core hosting** (ADR-0015): the metric logic moved into
  `app/backend/services/layout_qa.py` (shipped tree) with `tests/metrics/*` as
  re-export shims — runtime must NOT import the `tests/` tree (excluded from
  packaged deploys → latent flag-gated `ImportError`). Shim import-identity is
  asserted by a test.
- **Pre-existing CI-gate defect (out of scope)**: the `residual-text` gate command
  `pytest tests/test_pdf_layout_refactor.py -k "residual_text"` collects 0 tests
  (silent pass); pre-existing since PR #8 (`31d0cd51`). Recorded as follow-up.

## Lessons Promoted to Standards
Both **promote-to-guidance** (contract-reviewer adjudicated), applied inside the
`CLAUDE.md` `cdd-kit:learnings` markers; product behavior itself lives in BR-106 +
ADR-0015, not here.
- **A (metric-in-runtime shim)** — FOLDED into the existing "shared module …
  verify all consumer imports" learning (net 0 new bullets): added the clause "when
  the module must also run at production runtime, host the core in the shipped tree
  and reduce any `tests/` copy to a re-export shim (all public+private names) with an
  import-identity test — never the reverse; `tests/` is excluded from packaged
  deploys." Pointer → `docs/adr/0015-layout-qa-metric-core-in-runtime.md`. Evidence:
  ADR-0015; `tests/test_layout_qa.py::TestMetricCoreIdentity`; `agent-log/backend-engineer.yml`.
- **B (no-shell agent names a nonexistent seam)** — NEW bullet (+1): no-shell planning
  agents can assert a plausible-but-nonexistent seam even when `code-map.yml` is
  accurate (pattern-matched from prose); the first shell-capable agent must verify
  every named seam/symbol against live source and correct the contract/design.
  Pointer → BR-106 seam-name correction + implementation-planner log. Evidence:
  `.cdd/code-map.yml:822` (correct entry pre-existed) vs `agent-log/spec-architect.yml`
  (wrong name) vs `agent-log/implementation-planner.yml` (correction) + BR-106.
- Net CLAUDE.md growth: +1 line.

## Follow-up Work
- **Non-blocking, pre-existing:** retarget the CI `residual-text` gate `-k` filter (or
  the test name) so it collects the intended test instead of 0 — owner
  ci-cd-gatekeeper + test-strategist. Pre-existing since PR #8; not this change's scope.

## Cold Data Warning
This archive is historical evidence. Current requirements live in `contracts/` and
active project guidance.
