# Change Classification

## Change Types
- primary: bug-fix
- secondary: visual-rendering-fix

## Lane
- bug-fix

## Bug Symptom Type
- visual

## Diagnostic Only
- no

## Risk Level
- medium

## Impact Radius
- module-level

## Tier
- 3

## Risk Factors
- Visual rendering defect affecting output-document fidelity (user-visible PDF quality); regression risk to existing overlay/side-by-side masking paths.
- Geometry/masking logic change in a shared renderer (`fitz_renderer.py`) with two existing render modes (`_generate_overlay`, `_generate_side_by_side`); a too-narrow mask could leave source text visible, a too-wide mask could erase borders — the two fixes pull in opposite directions and must be balanced.
- No API / env / data-shape / contract change; no new packages; confined to one renderer file. This caps the radius at module-level.
- Golden-regression coverage exists (`tests/test_golden_regression.py`, `tests/fixtures/golden/pdf/`) — masking changes can shift golden PDFs and must be re-baselined deliberately, not silently.

## Architecture Review Required
- no

## Required Artifacts

The following 7 artifacts are always required for implementation changes:
`change-request.md`, `change-classification.md`, `implementation-plan.md`, `test-plan.md`, `ci-gates.md`, `tasks.yml`, `context-manifest.md`

## Optional Artifacts

| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | Broken behavior captured by bug evidence + failing tests |
| proposal.md | no | No user-facing behavior decision; fix restores intended masking behavior |
| spec.md | no | No new spec; behavior specified by AC-1/AC-2 |
| design.md | no | No architecture review required; geometry fix inside one existing renderer |
| qa-report.md | no | Routine pass/fail captured in agent-log/qa-reviewer.yml |
| regression-report.md | no | Regression evidence recorded as bug-fix evidence + golden-regression test result |
| visual-review-report.md | yes | Visual defect requires durable before/after rendered-PDF evidence for AC-1 (borders preserved) and AC-2 (right panel source text fully masked) |
| monkey-test-report.md | no | Not an input-fuzzing concern |
| stress-soak-report.md | no | No high-load / long-running path |

## Required Contracts
- API: none
- CSS/UI: none
- Env: none
- Data shape: none
- Business logic: none
- CI/CD: none

## Tasks Not Applicable
- not-applicable: 1.3

## Inferred Acceptance Criteria
- AC-1: In overlay-mode output PDFs, table grid lines (1-pt and multi-pt rules) remain visible after translation; no white-mask rectangle covers a table border stroke.
- AC-2: In side-by-side-mode output PDFs, the right panel contains no visible source-language text; all source text regions are masked before translated text is placed.
- AC-3: Overlay-mode white masking still fully covers source text content areas (no residual source text); border preservation does not reintroduce text bleed-through.
- AC-4: Existing golden-regression PDF fixtures either pass unchanged or are re-baselined with explicit justification recorded in the change; no unrelated render output regresses.
- AC-5: The fix is confined to `app/backend/renderers/fitz_renderer.py` rendering geometry; no API, env, data-shape, or contract surface changes and no new package dependencies.

## Required Agents
- bug-fix-engineer (owns reproduction, root cause, failing test, fix; records evidence in agent-log/bug-fix-engineer.yml)
- test-strategist (failing-then-passing regression tests + golden-baseline handling)
- ci-cd-gatekeeper (ci-gates.md)
- implementation-planner (turns evidence + tests into execution packet before backend-engineer implements)
- backend-engineer (implements masking-geometry fix in fitz_renderer.py — rendering owner)
- visual-reviewer (verifies rendered-PDF evidence for AC-1 and AC-2; writes visual-review-report.md)
- qa-reviewer (release readiness; required-test pass enforcement)

## Open Questions
- Should border preservation re-draw detected rule strokes on top of the mask, or shrink/split the mask to avoid them? Both satisfy AC-1; bug-fix-engineer should pick the more robust approach.
- How are table rule strokes distinguished from text rects in the source PDF page? (vector strokes vs. text regions)
