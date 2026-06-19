---
change-id: p2-table-border-protection
schema-version: 0.1.0
last-changed: 2026-06-19
---

# Implementation Plan: p2-table-border-protection

## Objective
Fix two visual-rendering defects in the fitz primary PDF renderer
(`app/backend/renderers/fitz_renderer.py`), confined to that one file plus a new
test file:

- Bug (a) — overlay mode: table grid lines (borders) are erased when source text
  is masked. After the fix, table rule strokes (1-pt and multi-pt) remain visible
  while source text is still fully removed (AC-1, AC-3).
- Bug (b) — side-by-side mode: source-language text remains visible on the right
  panel under/around the translated overlay. After the fix, all source text on
  the right-panel copy is masked before the translated overlay is placed (AC-2).

Note on file naming: `change-request.md`, `change-classification.md`, and the
context manifest all refer to `fitz_renderer.py`. The class inside it is
`PDFGenerator` (formerly `pdf_generator.py`, renamed in p2-renderer-convergence).
The `.cdd/code-map.yml` (generated 2026-06-17) still indexes the old
`pdf_generator.py` path and is stale for this file — see `## Known Risks`. Use
the live `fitz_renderer.py` line numbers in this plan, not the code map.

## Execution Scope

### In Scope
- Bug (a) — `PDFGenerator._generate_overlay` (`fitz_renderer.py` lines 219-376),
  specifically the redaction geometry (lines 309-343) and the
  `page.apply_redactions()` call (line 353). `apply_redactions()` with default
  arguments rasterizes/removes overlapping vector line-art; table borders inside
  a redact rect can be erased even after the `PDF_MASK_MARGIN_PT` shrink. The fix
  must keep source text removed while preserving vector strokes (e.g. pass a
  line-art-preserving option to `apply_redactions`, and/or keep the redact rect
  inset from borders via the existing margin). The bug-fix-engineer picks the
  approach (Open Question in `change-classification.md`); both
  redraw-strokes-on-top and shrink/preserve-line-art satisfy AC-1.
- Bug (b) — `PDFGenerator._generate_side_by_side` (`fitz_renderer.py` lines
  572-657). After the right-panel copy is drawn (lines 613-618) and before the
  translated overlay is placed (lines 633-642), add an explicit white mask over
  the source text regions on the right-panel copy. The per-region
  `draw_background` in `_create_page_overlay`/`render_text_region` is not a full
  source redaction and leaves source text showing where region rects do not fully
  cover it. Right-panel mask rects must be offset by `src_rect.width` (right-half
  origin).
- New test file `tests/test_table_border_protection.py` with the classes named in
  `test-plan.md` § New Test File.

### Out of Scope
- No changes to `bbox_reflow.py`, `text_region_renderer.py`, `font_utils.py`,
  `bbox_utils.py`, `base.py`, or any file other than `fitz_renderer.py` and the
  new test file — unless the investigation reveals a hard dependency, in which
  case file a Context Expansion Request and report `blocked` rather than editing
  out of scope.
- No new package dependencies; no new top-level imports in `fitz_renderer.py`
  (AC-5, enforced by `TestConfinementNoNewImports`).
- No API, env, data-shape, business-logic, or CI contract changes (AC-5).
- No opportunistic refactor of the font cache, fit cascade, `_insert_text_in_rect`,
  or reflow logic.
- Visual before/after PDF evidence is owned by visual-reviewer
  (`visual-review-report.md`), not by implementation agents.
- Golden fixture re-baselining is deliberate only — see `## Contract Updates`.

## Required Changes
| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | diagnosis | Read `fitz_renderer.py` overlay (309-353) and side-by-side (613-642) paths; reproduce both defects; record root cause in `agent-log/bug-fix-engineer.yml` before editing source | bug-fix-engineer |
| IP-2 | tests (failing-first) | Create `tests/test_table_border_protection.py` with all unit + integration classes from `test-plan.md`; confirm they fail against current code | bug-fix-engineer |
| IP-3 | bug (a) overlay borders | Fix overlay redaction so table vector strokes survive while source text is removed; touch only redaction geometry + `apply_redactions()` call | bug-fix-engineer |
| IP-4 | bug (b) side-by-side mask | Add explicit source-text white-mask pass over the right-panel copy before the translated overlay is placed | bug-fix-engineer |
| IP-5 | implementation handoff | If either fix requires a wider refactor or a new helper beyond the two targeted edits, hand the scope to backend-engineer with a precise note; do not expand silently | bug-fix-engineer → backend-engineer |
| IP-6 | green tests | Make IP-2 tests pass; run the full test ladder; handle golden re-baseline per `## Contract Updates` | bug-fix-engineer (or backend-engineer if IP-5 fires) |

## Source Artifact Pointers
| source | relevant pointer | used for |
|---|---|---|
| test-plan.md | § Acceptance Criteria → Test Mapping | AC→test class mapping |
| test-plan.md | § New Test File: tests/test_table_border_protection.py | exact test class/method names to author |
| test-plan.md | § Notes | mock `fitz.Page` methods; `skipif(not HAS_PYMUPDF)`; import `PDF_MASK_MARGIN_PT` from config |
| test-plan.md | § Test Update Contract | golden re-baseline rule (AC-4) |
| ci-gates.md | § Required Gates table | verification commands (5 required gates) |
| change-classification.md | § Open Questions | overlay border approach choice + stroke-vs-text distinction |
| change-classification.md | § Inferred Acceptance Criteria | AC-1..AC-5 definitions |
| context-manifest.md | § Allowed Paths | read/edit boundary |

## File-Level Plan
| path or glob | action | notes |
|---|---|---|
| app/backend/renderers/fitz_renderer.py | edit (bug a) | overlay redaction geometry (309-343) + `apply_redactions()` (353); preserve vector strokes; keep source text removed; no new top-level imports |
| app/backend/renderers/fitz_renderer.py | edit (bug b) | `_generate_side_by_side` (613-642): add right-panel source-text mask pass before overlay placement; offset rects by `src_rect.width` |
| tests/test_table_border_protection.py | create | test classes per `test-plan.md` § New Test File; repo root via `Path(__file__).parent.parent`; import `PDF_MASK_MARGIN_PT` from `app.backend.config` |
| (any other path) | none | only via approved Context Expansion Request |

## Contract Updates
- API: none (AC-5).
- CSS/UI: none.
- Env: none — `PDF_MASK_MARGIN_PT` already exists in `app/backend/config.py`
  (line 139); reuse it, do not add config.
- Data shape: none.
- Business logic: none — behavior restores the intended masking contract; no new
  BR.
- CI/CD: none — gates already wired in `.github/workflows/contract-driven-gates.yml`
  per `ci-gates.md`. If overlay/side-by-side masking geometry shifts element
  extraction, golden fixtures under `tests/fixtures/golden/pdf/` may be
  re-baselined; any re-baseline commit must cite change-id
  `p2-table-border-protection` and state the reason (test-plan.md § Test Update
  Contract, AC-4). Do not silently regenerate snapshots.

## Test Execution Plan
| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 (unit) | tests/test_table_border_protection.py::TestBorderAwareRedactRect | redact rect inset by `PDF_MASK_MARGIN_PT`; fallback uses `*2`; too-small skipped; text rect from placement not quad |
| AC-1 (integration) | tests/test_table_border_protection.py::TestOverlayBorderPreservation | `page.get_drawings()` non-empty after redaction (vector strokes survive) |
| AC-2 (unit) | tests/test_table_border_protection.py::TestSideBySideSourceMasking | right-panel source mask applied before overlay (mock call-order); N mask rects for N elements |
| AC-2 (integration) | tests/test_table_border_protection.py::TestSideBySideRightPanelMasking | right-half clip has no source text; translated text present |
| AC-3 (unit) | tests/test_table_border_protection.py::TestMaskCoversTextContent | redact rect interior to bbox; margin 0 → redact rect == quad rect |
| AC-3 (integration) | tests/test_table_border_protection.py::TestOverlayBorderPreservation | source text absent from `page.get_text()` of output |
| AC-4 | tests/test_golden_regression.py | passes unchanged, or re-baselined with cited justification |
| AC-5 | tests/test_table_border_protection.py::TestConfinementNoNewImports | no new top-level package import in `fitz_renderer.py` |

Test phases (bug-fix-engineer runs in order; floor = collect, targeted,
changed-area; full ladder for this Tier-3 change). Prefix every `cdd-kit`
command with `source ~/.nvm/nvm.sh &&`. Use the env pytest at
`/home/egg/miniforge3/envs/translate-tool/bin/pytest`:

1. collect:
   `source ~/.nvm/nvm.sh && cdd-kit test run p2-table-border-protection --phase collect --command "pytest tests/ --collect-only -q"`
2. targeted:
   `/home/egg/miniforge3/envs/translate-tool/bin/pytest tests/test_table_border_protection.py -x -q --tb=short`
3. changed-area:
   `/home/egg/miniforge3/envs/translate-tool/bin/pytest tests/test_table_border_protection.py tests/test_golden_regression.py tests/test_pdf_generator.py -x -q --tb=short`
4. full:
   `/home/egg/miniforge3/envs/translate-tool/bin/pytest tests/ -x -q --tb=short`

Record evidence via `cdd-kit test run` so the gate can validate
`test-evidence.yml`. CI gate commands are in `ci-gates.md` § Required Gates and
are not duplicated here.

## Handoff Constraints
- TDD order is mandatory: bug-fix-engineer must NOT edit source before
  diagnosing. Read the overlay (309-353) and side-by-side (613-642) paths, write
  the failing tests (IP-2), confirm they fail, THEN implement (IP-3, IP-4).
- `PDF_MASK_MARGIN_PT` must be imported from `app.backend.config` in tests, never
  hardcoded (test-plan.md § Notes).
- Test files must derive repo root via `Path(__file__).parent.parent`, never a
  hardcoded absolute path (promoted lesson;
  `tests/test_text_region_renderer.py::TestSinglePathEnforcement` is the
  reference pattern).
- Integration tests guard with `@pytest.mark.skipif(not HAS_PYMUPDF, ...)`; unit
  tests mock `fitz.Page` methods (`add_redact_annot`, `apply_redactions`,
  `draw_rect`).
- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into
  this plan; follow the source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and
  report `blocked`. Keep implementation within the file-level plan unless a
  Context Expansion Request is approved.
- If a fix exceeds the two targeted edits (e.g. a shared helper is genuinely
  needed), bug-fix-engineer hands off to backend-engineer (IP-5) with a precise
  scope note instead of broadening the edit unilaterally.

## Known Risks
- `.cdd/code-map.yml` is stale: it indexes `pdf_generator.py` (the old name), not
  `fitz_renderer.py`. Line ranges in this plan come from a live read of
  `fitz_renderer.py`, not the map. Ask the user to run `cdd-kit code-map` to
  refresh the index; meanwhile, trust this plan's line numbers over the map.
- The two fixes pull in opposite directions: a too-wide overlay mask erases
  borders (bug a), a too-narrow right-panel mask leaves source text visible (bug
  b). AC-3 guards bug (a) against under-masking text; AC-2 guards bug (b) against
  source bleed-through. Both must hold simultaneously.
- `apply_redactions()` default behavior may rasterize page content or remove line
  art; verify the chosen option preserves both embedded images and vector strokes
  without reintroducing source text (AC-1 + AC-3 together).
- Masking-geometry change can shift golden-regression element extraction
  (AC-4 / `golden-sample-regression` gate). Re-baseline only with explicit cited
  justification; an un-cited snapshot change will be treated as a regression and
  trigger the `ci-gates.md` § Rollback Policy.
- `renderer-equivalence` gate (`ci-gates.md`) asserts fitz/ReportLab element-level
  parity; since the right-panel mask pass is fitz-only, confirm it does not alter
  the shared `reflow_document` placement decisions (it must not touch
  `bbox_reflow.py`).
