# ADR 0015: Host the layout-fidelity metric core in the runtime tree, re-exported by the test tree

## Status
proposed

## Context
The layout-QA safety net (`layout-qa-safety-net`) needs the same BIoU / residual-text /
truncation-rate metric logic in two places: the CI-gate tests and a new runtime service
`app/backend/services/layout_qa.py` that runs post-render inside `pdf_processor.py`. That
logic exists today only as standalone, stdlib-only, duck-typed modules under
`tests/metrics/{biou,residual_text,truncation_rate}.py`.

Duplicating the metric implementation across the test tree and the runtime service is the
"shared module consumed by multiple backends" drift risk called out in the project's
promoted learnings — the two copies would silently diverge (a BIoU tweak in one place would
not move the CI gate, or vice-versa). A future engineer must not be able to reverse this
into two copies without the review surfacing it.

Two placements were possible: (a) move the core into the runtime tree and have the test tree
re-export it, or (b) have the runtime service import from the test tree. `contracts/ci/ci-gate-contract.md`
invokes the gates via *test files* (`test_layout_metrics.py`, `test_pdf_layout_refactor.py`),
not via the `tests/metrics/*` module paths, and `tests/test_layout_metrics.py` (L277-290)
has explicit `from tests.metrics.biou import ...` importability assertions that must keep
passing.

## Decision
Host the metric core (`compute_biou`, `_iou`, `check_residual_text`,
`compute_truncation_rate`, `BIOU_REGRESSION_BUDGET`) at module level in
`app/backend/services/layout_qa.py`, keeping it stdlib-only and duck-typed. Reduce
`tests/metrics/{biou,residual_text,truncation_rate}.py` to thin re-export shims that import
those names from `layout_qa`. The runtime `run_layout_qa` imports the core directly from its
own module; `fitz` (used only to re-open the rendered PDF) stays a lazy in-function import so
importing `layout_qa` — and therefore the shims — pulls no third-party dependency.

Reject placement (b): production code importing the test tree is an anti-pattern; `tests/`
is routinely excluded from packaged/deployed artifacts, so an enabled QA pass would raise
`ImportError` at runtime — a latent, flag-gated failure.

## Consequences
- Single source of truth for the metric logic lives in the shipped runtime tree; the CI gate
  and the runtime service can never diverge.
- The `tests.metrics.*` import path is preserved, so `tests/test_layout_metrics.py` and every
  gate command in `ci-gate-contract.md` keep working with no contract edit — the shims MUST
  re-export every public name including the private `_iou` that the tests import.
- `contracts/ci/ci-gate-contract.md` is NOT modified by this change (its tool paths are test
  files, transparent to the re-host); ci-cd-gatekeeper only verifies shim importability.
- Reversal (moving the core back to `tests/` or duplicating it) would silently re-open the
  divergence risk and is the specific thing this ADR forbids; any future change proposing it
  must supersede this ADR.
- Rollback of the whole feature is `git revert`; the shims restore to the standalone
  implementations with no downgrade path required.
