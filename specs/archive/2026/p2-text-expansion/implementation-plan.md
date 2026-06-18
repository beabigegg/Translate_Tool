---
change-id: p2-text-expansion
schema-version: 0.1.0
last-changed: 2026-06-18
---

# Implementation Plan: p2-text-expansion

## Objective
Replace the inline "shrink to ~4pt then silently truncate" fit loop on the converged
fitz primary PDF path with an explicit, ordered fit cascade
(font-size shrink → line-spacing → letter-spacing → controlled downward overflow → marked
truncation) implemented as a backend-neutral helper, and add a metric-compatible font
fallback chain plus an advisory expansion-factor table in `font_utils.py`. Truncation is
last-resort and is recorded on the IR element (`render_truncated`) so the QA safety net
can find it. All expansion/cascade logic lives only on the fitz primary path + shared
`bbox_reflow.py`; no duplication in any legacy renderer path. Target: en→de (+30%) /
en→es (+25%) benchmark renders with 0 bbox overflow and 0 tofu.

## Execution Scope

### In Scope
- New backend-neutral fit-cascade function in `app/backend/renderers/text_region_renderer.py`
  returning a structured decision object (font size, line spacing, letter spacing,
  overflow flag, truncated flag), implementing the 5-step priority order of BR-36.
- Rewire `app/backend/renderers/fitz_renderer.py` `PDFGenerator._insert_text_in_rect`
  (lines 453-570) to drive the shared cascade instead of the inline 25-iteration shrink
  loop, and to set `render_truncated = True` on the element when cascade step (e) fires.
- New `font_utils.py` helpers: `get_metric_compatible_fallback(primary_face, target_char,
  registered_faces)` (BR-39) and an expansion-factor lookup table + default-factor
  accessor (BR-37), reusing `register_fonts` state and the P1 `_load_font_buffer` LRU cache
  (which lives in `fitz_renderer.py`).
- Additive optional `render_truncated: bool = False` field on `TranslatableElement`
  (`translatable_document.py`), wired through `to_dict()`/`from_dict()` (from_dict defaults
  `False` when key absent).
- TDD-first tests for the new cascade and fallback functions (see Test Execution Plan).
- Grep verification that `coordinate_renderer.py`, `inline_renderer.py`, and legacy
  `pdf_generator.py` import no cascade helper (BR-40 / AC-6).
- Commit benchmark fixture PDFs required by the `text-expansion-benchmark` gate (see
  Operational Precondition under Known Risks).

### Out of Scope
- CJK vertical writing (P3-5) and RTL mirroring (P3-4).
- Table border protection (`p2-table-border-protection`).
- Any change to translation content; this change only adjusts rendering presentation.
- Frontend, API contract/endpoints/schemas, CSS/UI, env vars, secrets, datastore
  migrations, schema/ENUM DDL.
- Cascade or expansion logic in `coordinate_renderer.py`, `inline_renderer.py`, or
  `pdf_generator.py` (forbidden by BR-40 / AC-6).
- New bundled fallback font asset (rejected in design.md Decision 2; reuse existing Noto).
- DOCX/PPTX golden fixture expansion (test-plan.md Out of Scope).

## Required Changes
| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | renderer (cascade engine) | Add backend-neutral fit-cascade function + decision dataclass in `text_region_renderer.py` implementing BR-36 step order (a→e); return structured decision (size, line_spacing, letter_spacing, overflow, truncated). | backend-engineer |
| IP-2 | renderer (fitz adapter) | Rewrite `fitz_renderer.PDFGenerator._insert_text_in_rect` (453-570) to consume the IP-1 cascade decision; remove the inline 25-iteration shrink loop; set `render_truncated=True` on the element when step (e) truncates (BR-38). | backend-engineer |
| IP-3 | font utils (fallback) | Add `get_metric_compatible_fallback(primary_face, target_char, registered_faces)` selecting nearest Noto face by x-height→cap-height→advance-width; Noto terminal fallback; reuse `register_fonts` state + `_load_font_buffer` LRU cache; memoize per-face metrics (BR-39 / AC-7). | backend-engineer |
| IP-4 | font utils (expansion table) | Add expansion-factor table (en→de 1.30, en→es 1.25, en→fr 1.20) + documented default 1.15 with a lookup accessor in `font_utils.py`; advisory only — measured width governs (BR-37 / AC-8). Factors must not be magic numbers in the renderer. | backend-engineer |
| IP-5 | IR data shape | Add additive optional `render_truncated: bool = False` to `TranslatableElement`; include in `to_dict()`; `from_dict()` defaults `False` when key absent (data-shape-contract.md row + § Renderer IR-consumption contract). | backend-engineer |
| IP-6 | single-path enforcement | Grep-verify no cascade-helper import in `coordinate_renderer.py`, `inline_renderer.py`, `pdf_generator.py`; confirm consumers route through `bbox_reflow.reflow_document` (BR-40 / AC-6). | backend-engineer |
| IP-7 | tests | Author failing-first unit/contract tests for cascade order, truncation marker, metric fallback, expansion table; extend convergence + golden-regression coverage per test-plan.md. | backend-engineer |
| IP-8 | benchmark fixtures | Commit the pre-rendered/source benchmark fixture PDFs that `tests/test_text_expansion_benchmark.py` consumes (no network, no GPU). | backend-engineer |

## Source Artifact Pointers
| source | relevant pointer | used for |
|---|---|---|
| design.md | Decision 1 (cascade order + per-step thresholds) | IP-1/IP-2 cascade step floors |
| design.md | Decision 2 (metric-compatible fallback chain) | IP-3 selection heuristic + Noto terminal fallback |
| design.md | Decision 3 (truncation marker on IR) + ADR 0004 | IP-5 field placement and ownership |
| design.md | Decision 4 (expansion table + 1.15 default) | IP-4 factors and default policy |
| design.md | Open Risks (controlled-overflow neighbor geometry) | IP-1 step (d) degraded-behavior note |
| business-rules.md | BR-36, BR-37, BR-38, BR-39, BR-40; Table L | cascade order, factors, no-silent-truncation, fallback, single-path |
| data-shape-contract.md | `render_truncated` field row; § Renderer IR-consumption contract; Known consumers table | IP-5 shape + renderer obligation |
| test-plan.md | AC→test mapping; Test Update Contract | IP-7 test targets and existing-test edits |
| ci-gates.md | Required Gates table | verification commands / merge eligibility |

## File-Level Plan
| path or glob | action | notes |
|---|---|---|
| `app/backend/renderers/text_region_renderer.py` | modify | Add cascade decision dataclass + cascade function (per BR-36 / design Decision 1). Existing `fit_text_to_bbox` import/usage at line ~151 unpacks a 2-tuple — if the cascade supersedes `fit_text_to_bbox`'s return shape, update this call site and `font_utils.fit_text_to_bbox` together (test-plan Test Update Contract: `TestFitTextToBbox` extends for new fields). Do NOT break `render_text_region` for the ReportLab path. |
| `app/backend/renderers/fitz_renderer.py` | modify | Rewrite `PDFGenerator._insert_text_in_rect` (453-570); replace inline `for _ in range(25)` shrink loop (509-548) and the final truncation attempt (549-570) with a call into the IP-1 cascade; emit `render_truncated=True` on the element when step (e) fires. Keep `_load_font_buffer` LRU usage (481-493) and the metrics hooks. |
| `app/backend/utils/font_utils.py` | modify | Add `get_metric_compatible_fallback(...)` (BR-39); add expansion-factor table + default accessor (BR-37). Reuse `register_fonts`/`LANGUAGE_FONT_MAP` Noto faces; load bytes only via `_load_font_buffer` (imported from `fitz_renderer`); memoize per-face metrics. |
| `app/backend/models/translatable_document.py` | modify | `TranslatableElement` (128-171): add `render_truncated: bool = False`; add to `to_dict()` (142-155); `from_dict()` (157-171) `data.get("render_truncated", False)`. |
| `app/backend/renderers/bbox_reflow.py` | no logic change | Remains the single placement source the cascade consumes. `Placement` is frozen and does NOT carry `render_truncated`; the marker is written on the IR element, not the Placement. Confirm step (d) neighbor-whitespace availability; if unavailable, document degraded "skip (d), go to (e)" behavior. |
| `app/backend/renderers/coordinate_renderer.py` | verify only (CER-001 approved) | Must NOT import or duplicate the cascade helper (BR-40). |
| `app/backend/renderers/inline_renderer.py` | verify only (CER-001 approved) | Must NOT import or duplicate the cascade helper (BR-40). |
| `app/backend/renderers/pdf_generator.py` | verify only (CER-001 approved) | Legacy ReportLab fallback per data-shape Known-consumers table; confirmed no fit/cascade logic present today. Must NOT gain cascade logic (BR-40). |
| `tests/test_text_region_renderer.py` | modify | Add cascade-order, truncation-marker, contract, and single-path-enforcement tests (test-plan.md AC-4/AC-5/AC-6 rows). |
| `tests/test_font_utils.py` | modify | Add metric-fallback, LRU-reuse, and expansion-factor tests (AC-3/AC-7/AC-8 rows); extend `TestFitTextToBbox` per Test Update Contract. |
| `tests/test_renderer_convergence.py` | modify | Extend `TestLayoutEquivalence` with cascade-wiring mock.patch assertions (AC-6) without breaking existing placement tests. |
| `tests/test_golden_regression.py` | verify/extend | `render_truncated` newly present in IR snapshots; data-boundary round-trip (AC-1/AC-5 data-boundary rows). |
| `tests/test_text_expansion_benchmark.py` | create | New benchmark test for the `text-expansion-benchmark` gate (AC-1/AC-2/AC-3): 0 overflow, 0 tofu; consumes committed fixtures only. |
| `tests/fixtures/golden/` (and benchmark fixtures) | add | Commit benchmark fixture PDFs (Operational Precondition). |

## Contract Updates

- API: none (no endpoint/schema change).
- CSS/UI: none.
- Env: none (font LRU cache is in-process; no new env var/secret).
- Data shape: already authored by contract-reviewer — `render_truncated` field row,
  § Renderer IR-consumption contract obligation, and Known-consumers table in
  `contracts/data/data-shape-contract.md`. Implementation must match that shape; do not
  edit the contract.
- Business logic: already authored — BR-36/37/38/39/40 and Table L in
  `contracts/business/business-rules.md`. Implement to those rules; do not edit the
  contract.
- CI/CD: `text-expansion-benchmark` and extended `renderer-equivalence` jobs already
  defined in `ci-gates.md` / `.github/workflows/contract-driven-gates.yml`
  (ci-cd-gatekeeper owns; do not edit here).

## Test Execution Plan
Required phases run in order via `cdd-kit test run`: `collect` → `targeted` (write
failing tests first; must be red before implementation) → `changed-area` → `contract`
→ `full`. Floor phases (collect, targeted, changed-area) are mandatory; contract and
full apply here because this change touches a contract surface and a shared render path.
AC-4/AC-5 tests and the `render_truncated` field tests MUST fail before the cascade
helper and the IR field exist (test-plan.md Notes / TDD gate).

| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 | tests/test_text_region_renderer.py::TestFitCascade::test_ende_no_overflow | 0 overflow at +30% |
| AC-2 | tests/test_text_region_renderer.py::TestFitCascade::test_enes_no_overflow | 0 overflow at +25% |
| AC-3 | tests/test_font_utils.py::TestMetricFallbackChain | missing glyph selects Noto; no tofu/metric drift |
| AC-4 | tests/test_text_region_renderer.py::TestFitCascade | cascade applies steps a→e in order; truncation last-resort only |
| AC-4 | tests/test_text_region_renderer.py::TestFitCascadeContract::test_cascade_decision_fields_present | decision object exposes all required fields |
| AC-5 | tests/test_text_region_renderer.py::TestTruncationMarker | truncation sets `render_truncated=True`; no-truncation keeps `False`; field present in `to_dict()` |
| AC-6 | tests/test_renderer_convergence.py::TestLayoutEquivalence | both/ReportLab paths call `reflow_document` (mock.patch) |
| AC-6 | tests/test_text_region_renderer.py::TestSinglePathEnforcement::test_no_cascade_logic_in_legacy_paths | cascade helper not imported in legacy paths |
| AC-7 | tests/test_font_utils.py::TestMetricFallbackChain::test_fallback_reuses_lru_cache | `_load_font_buffer` call count ≤ 1 per face across repeated fallback |
| AC-8 | tests/test_font_utils.py::TestExpansionFactorTable | en→de/es/fr factors correct; unknown pair → 1.15; default documented |
| AC-1/AC-5 (data-boundary) | tests/test_golden_regression.py | `render_truncated` round-trips; pre-existing-field diff blocks merge |
| AC-1/AC-2/AC-3 (gate) | tests/test_text_expansion_benchmark.py | zero-overflow + zero-tofu assertion log |

## Handoff Constraints

- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above.
- The fit cascade helper is the single implementation surface; the fitz adapter and the
  ReportLab adapter both render from its decision. Do NOT add a second cascade in any
  legacy path (BR-40 / AC-6).
- The `render_truncated` marker is written on the IR `TranslatableElement` by the renderer
  only at cascade step (e); parsers and the translation layer must never set it.
  `bbox_reflow.Placement` is frozen and does not carry the marker.
- Keep `_load_font_buffer` (in `fitz_renderer.py`) as the only font-byte I/O path; metric
  fallback must not introduce redundant reads (AC-7).
- If the cascade changes the return shape of `font_utils.fit_text_to_bbox`, update its
  single call site in `text_region_renderer.render_text_region` (line ~151) in the same
  change, and extend `tests/test_font_utils.py::TestFitTextToBbox` per the Test Update
  Contract. Do not silently break the 2-tuple unpack.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved.

## Known Risks

- **Stale code-map.** `.cdd/code-map.yml` (generated 2026-06-17) maps the cascade to
  `pdf_generator.py::PDFGenerator._insert_text_in_rect`, but the converged primary path is
  `app/backend/renderers/fitz_renderer.py` (renamed in p2-renderer-convergence). The live
  fit loop is in `fitz_renderer.py` lines 453-570; `pdf_generator.py` is now the legacy
  ReportLab fallback consumer (data-shape Known-consumers table) and has no fit/cascade
  logic. Recommend running `cdd-kit code-map` before implementation so future reads are
  accurate. Line ranges in this plan were taken from the live `fitz_renderer.py`, not the
  stale map.
- **Step (d) neighbor geometry (design Open Risk).** Controlled downward overflow depends
  on `bbox_reflow` exposing adjacent-whitespace geometry. If unavailable, step (d) degrades
  to "skip (d), proceed directly to (e) truncation" (BR-36 Table L row). Implementation
  must confirm neighbor-whitespace availability or document the degraded behavior.
- **Operational precondition — benchmark fixtures.** The `text-expansion-benchmark` gate
  (`pytest tests/test_text_expansion_benchmark.py`, required-for-merge per ci-gates.md)
  fails until the benchmark fixture PDFs are committed. These must be pre-committed,
  network-free, GPU-free fixtures (IP-8). Commit them before invoking the gate.
- **Font-rendering non-determinism.** The benchmark may flake across runner font stacks;
  per ci-gates.md Promotion Policy, flaky sub-checks are quarantined to an informational
  sub-job while deterministic assertions stay required.
- **`fit_text_to_bbox` return-shape coupling.** Changing its tuple return ripples to
  `text_region_renderer.render_text_region` (line ~151). Treat as a coordinated edit.
