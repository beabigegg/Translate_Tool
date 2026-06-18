---
change-id: p2-renderer-convergence
schema-version: 0.1.0
last-changed: 2026-06-18
---

# Implementation Plan: p2-renderer-convergence

## Objective
Converge the PDF render layer onto a fitz-primary / ReportLab-fallback architecture in which both backends are thin adapters that delegate all IR→placement logic to a single new shared component (`bbox_reflow`). Deliver the behavior fixed by BR-34, BR-35, Table K, and `data-shape-contract.md § Renderer IR-consumption contract`, proven by the AC-1..AC-7 tests in `test-plan.md`.

## Execution Scope

### In Scope
Implement design.md `## Affected Components` and `## Key Decisions A–D`:
- New `app/backend/renderers/bbox_reflow.py` — shared IR→placement (Decision A).
- Rename `app/backend/renderers/pdf_generator.py` → `fitz_renderer.py`, reduced to a fitz adapter consuming `bbox_reflow` (Decision D).
- `app/backend/renderers/coordinate_renderer.py` — ReportLab fallback adapter consuming `bbox_reflow`.
- `app/backend/renderers/text_region_renderer.py` — demoted to ReportLab draw helper; its `create_text_regions_from_elements` IR logic moves into `bbox_reflow`.
- `app/backend/processors/pdf_processor.py::_translate_pdf_to_pdf` — fitz-primary dispatch with ReportLab fallback on exception (Decision B, BR-34, Table K).
- `app/backend/renderers/__init__.py` — update exports for the rename.
- TDD test authoring/extension per `test-plan.md`.

### Out of Scope
See Non-goals below and `test-plan.md ## Out of Scope`.

## Non-goals (MUST NOT)
- Do NOT change the IR wire schema in `models/translatable_document.py` (ElementType wire values, field names, `to_dict`/`from_dict`); IR is consumed read-only.
- Do NOT modify DOCX/PPTX/XLSX render or processor paths; `inline_renderer.py` is untouched (Decision D).
- Do NOT alter any API endpoint, route, or `pdf_processor` public entry signatures other than the internal `_translate_pdf_to_pdf` dispatch body.
- Do NOT implement side-by-side equivalence; the equivalence contract scopes to OVERLAY mode only (design.md Open Risks).
- Do NOT pursue byte/raster-identical output; equivalence is element-level decision identity + ±2.0 pt placement (Decision C).
- Do NOT broaden the fallback catch to `BaseException` or swallow non-fitz errors (Decision B).
- Do NOT add a new dependency (ReportLab already present, CER-001 resolved).
- Do NOT edit `design.md`, contracts, or the CI workflow files (owned by other agents).

## Required Changes
| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | renderers/bbox_reflow.py (new) | Shared IR→placement: bbox/reading_order/element_type/translated_content honoring + null fallbacks per data-shape § Renderer IR-consumption contract | backend-engineer |
| IP-2 | pdf_generator.py → fitz_renderer.py | Rename; reduce to fitz adapter consuming IP-1; drop inline placement from `_generate_overlay` | backend-engineer |
| IP-3 | coordinate_renderer.py | Reduce to ReportLab fallback adapter consuming IP-1 | backend-engineer |
| IP-4 | text_region_renderer.py | Demote to ReportLab draw helper; move `create_text_regions_from_elements` IR logic into IP-1 | backend-engineer |
| IP-5 | pdf_processor.py `_translate_pdf_to_pdf` | fitz-primary try / ReportLab fallback on exception; WARNING log (exc type + doc id) per BR-34 | backend-engineer |
| IP-6 | renderers/__init__.py | Update imports/`__all__` for rename | backend-engineer |
| IP-7 | tests (new + extended) | Author/extend tests per test-plan.md (TDD) | backend-engineer |

## Source Artifact Pointers
| source | relevant pointer | used for |
|---|---|---|
| design.md | Decisions A–D, ## Affected Components, ## Open Risks | architecture constraints |
| business-rules.md | BR-34, BR-35, Table K | dispatch/fallback + decision-identity rules |
| data-shape-contract.md | § Renderer IR-consumption contract, § Malformed IR handling (AC-6) | field obligations + malformed-IR behavior |
| test-plan.md | AC→test mapping, new file + extensions | tests to write/run |
| ci-gates.md | required gates table | verification commands |
| change-classification.md | AC-1..AC-7 | acceptance criteria |

## File-Level Plan
| path or glob | action | notes |
|---|---|---|
| app/backend/renderers/bbox_reflow.py | create | IP-1; reuse `utils/bbox_utils` geometry; no fitz/ReportLab imports |
| app/backend/renderers/pdf_generator.py | rename → fitz_renderer.py | IP-2; keep `PDFGenerator` class name exported; fitz quad-search refine retained over reflow bbox (Open Risk) |
| app/backend/renderers/coordinate_renderer.py | modify | IP-3; consume reflow output |
| app/backend/renderers/text_region_renderer.py | modify | IP-4; draw-only; IR logic removed |
| app/backend/processors/pdf_processor.py | modify | IP-5; `_translate_pdf_to_pdf` (~lines 441–560); update import at line 443; keep existing DOCX fail-soft as outer last resort |
| app/backend/renderers/__init__.py | modify | IP-6; lines 8 + 14 |
| tests/test_renderer_convergence.py | create | IP-7; all classes per test-plan.md ## New Test File |
| tests/test_pdf_generator.py | extend | add `class TestFallbackPath` (extend only, no deletion) |
| tests/test_ir_pipeline_decoupling.py | extend | add `TestReadingOrderPreservedBothPaths`, `TestElementTypingPreservedBothPaths`, `TestMalformedIRBothPaths` |

Import-site requirement: every reference to `app.backend.renderers.pdf_generator` MUST become `fitz_renderer` (confirmed sites: `renderers/__init__.py:8`, `pdf_processor.py:443`) or the gate import-conformance check fails (design.md Open Risk).

## Contract Updates
- API: none.
- CSS/UI: none.
- Env: none (optional `PDF_RENDERER_PRIMARY` switch is design.md rollback guidance, not required this change).
- Data shape: consume `data-shape-contract.md § Renderer IR-consumption contract` — do not redefine.
- Business logic: BR-34 / BR-35 / Table K already authored — consume, do not edit.
- CI/CD: `renderer-equivalence` gate already added by ci-cd-gatekeeper — do not edit the workflow.

## TDD Sequence
Write failing tests first, then implement to green:
1. AC-1 `TestIRBboxReflow` (`test_shared_reflow_returns_placement_for_valid_bbox`, `_skips_null_bbox`, `_deterministic`) — must fail (module absent) → implement IP-1.
2. AC-2 `TestFitzPrimary` (`test_fitz_renderer_selected_by_default`, `_produces_valid_pdf`) → implement IP-2 + IP-5 default selection.
3. AC-3 `TestFitzFallback` (`test_fallback_to_reportlab_on_fitz_exception`, `_fallback_emits_warning_log`, `_no_job_abort_on_fitz_failure`) + `test_pdf_generator.py::TestFallbackPath` → implement IP-5 dispatch (Decision B, BR-34).
4. AC-5 `TestReadingOrderPreservedBothPaths`, `TestElementTypingPreservedBothPaths` (BR-35) → implement IP-3 + IP-4 consuming IP-1.
5. AC-6 `TestMalformedIRDataBoundary` + `TestMalformedIRBothPaths` (§ Malformed IR handling): null bbox/reading_order, unknown element_type→text, null translated_content→content, empty elements→valid empty page.
6. AC-4 `TestLayoutEquivalence` (`test_element_count_equivalent_fitz_vs_reportlab`, `test_bbox_placement_within_tolerance_fitz_vs_reportlab`) — ±2.0 pt per bbox edge (Decision C).
7. AC-7 `TestEquivalenceGolden` (`test_golden_fitz_snapshot_stable`, `_reportlab_snapshot_stable`) + existing `tests/test_golden_regression.py` must stay green.

## Contract Constraints
- BR-34 / Table K: fitz primary; ReportLab invoked only on fitz unhandled exception; WARNING logs exception type + document id; both consume the same IR via shared reflow.
- BR-35: identical element-level decisions across paths — inclusion/exclusion, reading-order resolution, text-source selection; unknown `element_type` → `text` on both.
- data-shape § Renderer IR-consumption contract (field table) + § Malformed IR handling (five rows).
- Equivalence tolerance ±2.0 pt; element count exactly equal; not equivalence-tested: fonts/glyphs/raster/bytes (Decision C). Confirm ±2.0 pt against golden fixtures before locking `TestLayoutEquivalence` (Open Risk; widen only with recorded rationale).
- AC-1..AC-7: see change-classification.md.

## Test Execution Plan
| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 | tests/test_renderer_convergence.py::TestIRBboxReflow | pass |
| AC-2 | tests/test_renderer_convergence.py::TestFitzPrimary | pass |
| AC-3 | tests/test_renderer_convergence.py::TestFitzFallback | pass |
| AC-3 | tests/test_pdf_generator.py::TestFallbackPath | pass |
| AC-4 | tests/test_renderer_convergence.py::TestLayoutEquivalence | pass within ±2.0 pt |
| AC-5 | tests/test_ir_pipeline_decoupling.py::TestReadingOrderPreservedBothPaths | pass |
| AC-5 | tests/test_ir_pipeline_decoupling.py::TestElementTypingPreservedBothPaths | pass |
| AC-6 | tests/test_ir_pipeline_decoupling.py::TestMalformedIRBothPaths | pass |
| AC-6 | tests/test_renderer_convergence.py::TestMalformedIRDataBoundary | pass |
| AC-7 | tests/test_golden_regression.py | no regression |
| AC-7 | tests/test_renderer_convergence.py::TestEquivalenceGolden | snapshots stable |

## Test Execution Ladder
Run via `cdd-kit test run` and produce `test-evidence.yml` before the gate. Required phases for this change: `collect`, `targeted`, `changed-area`, `contract` (data-shape/BR-35 boundary + `renderer-equivalence` gate). Full ladder lives in `test-plan.md` and `references/sdd-tdd-policy.md` — do not restate. Gate commands: `ci-gates.md` required-gates table (`contract-validate`, `change-gate`, `unit-tests`, `golden-sample-regression`, `renderer-equivalence`).

## Handoff Constraints
- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved.
- `bbox_reflow` module path MUST match the import path the test-strategist committed in `TestIRBboxReflow`; align test and module path before implementing.

## Known Risks
- Fitz uses `page.search_for()` quad-precise redaction; reflow must carry the IR bbox while letting the fitz adapter still refine via quad search (design.md Open Risk) — do not collapse fitz to bbox-only placement.
- The rename touches import sites; a missed site fails import-conformance.
- ±2.0 pt tolerance is provisional; validate against golden fixtures before locking pass criteria.
- Side-by-side mode differs structurally between backends; equivalence is OVERLAY-scoped only — keep side-by-side out of the equivalence assertions.
