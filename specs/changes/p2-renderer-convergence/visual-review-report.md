# Visual Review Report

## Change
p2-renderer-convergence — fitz-primary / ReportLab-fallback PDF rendering with shared IR-bbox reflow component.

## Affected Screens
PDF layout output (not a web UI surface). The review assesses rendered PDF placement correctness and cross-path layout equivalence, not pixel or CSS compliance.

## Viewports Checked
Not applicable — output is PDF pages, not browser viewports.

---

## 1. Evidence Assessment — What Equivalence Evidence Exists; Is It Sufficient for BR-35?

### What exists

`tests/test_renderer_convergence.py` is implemented and covers the full test-plan matrix:

| class | purpose | AC |
|---|---|---|
| `TestIRBboxReflow` | Shared `reflow_element` / `reflow_document` in isolation: valid bbox returns placement, null bbox returns None, determinism, text-source selection, unknown element_type passthrough, coordinate pass-through | AC-1 |
| `TestFitzPrimary` | `fitz_renderer` module present; fitz path renders to a valid non-empty PDF | AC-2 |
| `TestFitzFallback` | fitz raises → ReportLab invoked; WARNING log contains exception type + doc id; exception does not propagate; double-failure propagates | AC-3 |
| `TestLayoutEquivalence` | `reflow_document` called twice with same IR → identical element count and coordinates within ±2.0 pt | AC-4 |
| `TestMalformedIRDataBoundary` | null bbox skipped, null reading_order falls back, unknown element_type passes through, null translated_content falls back to source, empty elements yields empty list | AC-6 |
| `TestEquivalenceGolden` | `reflow_document` called twice for the same synthetic doc → placements are structurally equal | AC-7 |

`tests/test_golden_regression.py` adds:
- `TestGoldenPDFParseIRStable` — parse-IR snapshot stability per fixture (element count, element types, reading_order presence).
- `TestDualRunDiffNoRegressions` — parse-twice determinism per fixture.
- `TestDualRunLayoutDetectorVsHeuristic` — schema compatibility across detector/heuristic paths.
- `TestMultiColumnReadingOrderAccuracy` — column ordering correctness.
- `TestGoldenOfflineNoNetwork` — offline gate.

BR-35 specifically requires that both paths make **identical element-level decisions** (include/exclude, reading-order, text-source). The test suite proves this by routing both paths through the same `reflow_document` call — a single shared component with no per-backend branching. Calling the component twice with identical input and asserting structural equality (`test_golden_fitz_snapshot_stable`, `test_element_count_equivalent_fitz_vs_reportlab`, `test_bbox_placement_within_tolerance_fitz_vs_reportlab`) is logically equivalent to asserting BR-35 identity: if both adapters consume the same reflow output, and reflow is deterministic, they will always make identical decisions.

### Gaps

1. **No integration-level comparison of actual backend outputs.** `TestLayoutEquivalence` calls `reflow_document` twice against the same call site — it does not independently drive `fitz_renderer` and `coordinate_renderer` through `_dispatch_render` and extract their placement outputs from the resulting PDFs. This means the tests prove the shared component is deterministic and that the component satisfies the ±2.0 pt tolerance relative to IR-bbox input, but they do not prove that each backend adapter correctly passes `reflow_document` output through to the rendered PDF without independent placement logic. The architecture decision (shared reflow, thin adapters) makes this the correct structural approach, but the adapter-to-placement pipeline is only tested via `test_fitz_renderer_produces_valid_pdf` (existence check only, no coordinate extraction).

2. **No `.layout.json` golden snapshots exist.** The `design.md` §Migration/Rollback Strategy specifies `*.layout.json` snapshot files alongside `*.ir.json` as the mechanism for catching reflow regressions before they reach either backend. The `tests/fixtures/golden/pdf/` directory contains only `test.ir.json`, `simple.ir.json`, `multipage.ir.json` — no `.layout.json` equivalents. `TestEquivalenceGolden` uses an in-memory synthetic document rather than the committed golden PDF fixtures, so any regression in how `reflow_document` handles real fixture content would not be caught by the current snapshot set.

3. **`TestEquivalenceGolden` tests reflow stability, not backend-specific rendering stability.** Both `test_golden_fitz_snapshot_stable` and `test_golden_reportlab_snapshot_stable` call `reflow_document` on the same synthetic doc. The test names imply per-backend evidence but the implementations are identical. This is architecturally correct (shared component) but is a clarity gap in the evidence chain — the test-plan intent for AC-7 was to show per-backend snapshot stability against golden fixtures.

**Sufficiency verdict for BR-35:** The shared-component architecture means that any two adapters consuming the same `reflow_document` output will automatically satisfy BR-35 element-level identity. The test suite proves the shared component satisfies the contract. The remaining gap (no adapter-level integration extraction test) is an accepted architecture consequence: it shifts risk to verifying that neither adapter adds independent placement logic, which the code review (backend-engineer agent) must confirm. The evidence is sufficient for the equivalence claim given the architecture, but conditional on that code-review confirmation.

---

## 2. Tolerance Review — Is ±2.0 pt per Edge Adequate? Any Risk of Layout Drift at Boundaries?

**Source of the tolerance:** Design.md §Decision C states ±2.0 pt per bbox edge matches "the existing fitz redaction margin in `_generate_overlay`." This derivation is grounded in the existing system behavior rather than an arbitrary selection.

**Test enforcement:** `test_bbox_placement_within_tolerance_fitz_vs_reportlab` (lines 456–470) checks `abs(p.x0 - elem.bbox.x0) <= 2.0` for each edge. The test exercises the shared reflow component against the IR bbox values, asserting that reflow does not introduce drift beyond 2.0 pt.

**Adequacy assessment:**
- At 72 dpi (PDF user space), 2.0 pt ≈ 0.028 inches ≈ 0.7 mm. This is sub-line-height drift for body text and is appropriate for a redaction-overlay context where the fitz path preserves the original page as a background raster and the ReportLab path reconstructs the page.
- The tolerance covers the practical source of drift: fitz can refine text quads via `page.search_for()` while ReportLab places by IR bbox directly. A 2.0 pt margin accommodates this sub-word-level quad refinement.
- **Boundary risk — Open Risk from design.md:** The fitz path currently uses `page.search_for()` to locate exact text quads for redaction. The design notes that `reflow` must expose bbox-based placement without forcing fitz to abandon quad-precise redaction. If the fitz adapter refines placement coordinates via `search_for()` after receiving reflow output, the actual rendered coordinates may diverge from `reflow_document` output by more than 2.0 pt for certain text shapes. This path is tested only at the "valid PDF produced" level (existence check), not with coordinate extraction.

**Risk: moderate.** The ±2.0 pt tolerance is well-derived and the test enforces it at the reflow level. The adapter-level risk (fitz quad refinement introducing post-reflow drift) is an identified open risk in design.md and is not currently tested. If fitz quad refinement shifts placement beyond 2.0 pt, `TestLayoutEquivalence` would not catch it because the test does not extract final rendered coordinates from the PDF.

---

## 3. Golden Fixture Coverage — Are Existing Fixtures Adequate? Gaps?

### Current fixture inventory
```
tests/fixtures/golden/pdf/
  test.pdf       + test.ir.json
  simple.pdf     + simple.ir.json
  multipage.pdf  + multipage.ir.json
```

Three PDF fixtures with three `*.ir.json` parse-IR snapshots. No `*.layout.json` placement snapshots.

### What the existing fixtures prove
The `TestGoldenPDFParseIRStable` tests parse each fixture and compare element count, element types, and reading_order presence against the committed `*.ir.json` snapshot. This detects parse-IR regressions (wrong element count after a parser change) but does not detect placement regressions (reflow producing different coordinates for the same IR).

### What is missing for this change
1. **`*.layout.json` placement snapshots are absent.** The design.md §Migration/Rollback Strategy explicitly calls for split snapshot files: `*.ir.json` for parse-IR stability and `*.layout.json` for placement-decision stability. None of the three golden fixtures have a `.layout.json` companion. This means a regression in `bbox_reflow.py` (e.g., coordinate transform error, reading-order sort change) would not be caught by any snapshot comparison against real fixture content.

2. **`TestEquivalenceGolden` uses a synthetic, in-memory document** (`_make_doc()`), not any of the three golden fixture PDFs. Real fixture content may expose edge cases (multi-column layouts, elements with extreme bbox values, mixed element types) that the synthetic two-element doc does not exercise.

3. **Fixture variety is limited.** Three fixtures cover minimal surface. There is no fixture with: (a) null-bbox elements present in a real document, (b) multi-page content requiring cross-page reading_order normalization, (c) mixed ElementType (TABLE, FIGURE, FORMULA) elements. The `multipage.pdf` fixture exists but its content is not described; it may cover the multi-page case.

**Coverage verdict:** The existing fixture set (3 PDFs, 3 `*.ir.json` snapshots) is the minimum acceptable per `TestGoldenFixtureInventory` (floor of 3). It is adequate for parse-IR regression detection. It is **not adequate** for layout-placement regression detection. The absence of `.layout.json` snapshots is the most significant gap in the visual evidence bundle.

---

## 4. Risk Findings — Visual Layout Risks Not Covered by Tests

| risk id | risk | severity | covered? |
|---|---|---|---|
| VR-1 | fitz quad-refinement post-reflow shifts rendered coordinates beyond ±2.0 pt | medium | No — tests do not extract PDF coordinates |
| VR-2 | No `.layout.json` golden snapshots; reflow regression on real fixture content is silent | medium-high | No — snapshots not yet written |
| VR-3 | `TestEquivalenceGolden` uses synthetic doc only; does not validate against real fixture content | medium | Partial — structure tested, real content not |
| VR-4 | `test_golden_fitz_snapshot_stable` and `test_golden_reportlab_snapshot_stable` are identical calls; per-backend distinction is nominal | low | Architecture acceptable; clarity gap only |
| VR-5 | Side-by-side mode placement explicitly excluded from equivalence scope (design.md §Decision C); no test documents side-by-side behavior delta | low | Out of scope per design; gap is documentation |
| VR-6 | `reflow_document` sort fallback for null reading_order: `test_null_reading_order_handled_identically_both_paths` asserts "at least one placement" but not the sort order itself | low | Partial — sort order not verified |
| VR-7 | Empty elements list fast-path: `test_empty_elements_produces_valid_empty_result` passes; no risk | none | Covered |

**Highest-impact gap: VR-2.** If `bbox_reflow.py` is modified after this change ships (e.g., coordinate normalization change), no test will catch the regression against committed fixture content because `.layout.json` snapshots do not exist.

---

## 5. States Checked

| state | applicable? | evidence |
|---|---|---|
| Default (valid IR, fitz primary) | yes | `TestFitzPrimary::test_fitz_renderer_produces_valid_pdf` |
| Fallback (fitz raises, ReportLab invoked) | yes | `TestFitzFallback::test_fallback_to_reportlab_on_fitz_exception` |
| Double failure (both paths raise) | yes | `TestFitzFallback::test_double_failure_propagates` |
| Empty document | yes | `TestMalformedIRDataBoundary::test_empty_elements_produces_valid_empty_result` |
| Null bbox element | yes | `TestIRBboxReflow::test_shared_reflow_skips_null_bbox` |
| Null reading_order element | yes | `TestMalformedIRDataBoundary::test_null_reading_order_handled_identically_both_paths` |
| Unknown element_type | yes | `TestIRBboxReflow::test_reflow_unknown_element_type_treated_as_text` |
| Null translated_content | yes | `TestIRBboxReflow::test_reflow_falls_back_to_content_when_translated_content_null` |
| Multi-page document | partial | `multipage.pdf` fixture exists; no `.layout.json` snapshot; not driven through reflow |
| Side-by-side mode | no | Explicitly out of scope (Decision C) |

---

## Evidence

- screenshots: n/a — PDF output; no raster pixel comparison performed; tooling unavailable in this environment
- videos: n/a
- diff reports: n/a — no `.layout.json` snapshots exist to diff against
- test file reviewed: `tests/test_renderer_convergence.py` (lines 1–599)
- golden fixtures reviewed: `tests/fixtures/golden/pdf/` — 3 PDFs, 3 `*.ir.json`, 0 `*.layout.json`
- contracts reviewed: `contracts/business/business-rules.md` BR-34, BR-35, Table K
- design reviewed: `specs/changes/p2-renderer-convergence/design.md` §Decision C, §Open Risks
- test-plan reviewed: `specs/changes/p2-renderer-convergence/test-plan.md` §Visual

---

## CSS Contract Findings

Not applicable — this change produces PDF output. There are no web-UI tokens, CSS contracts, or viewport layout concerns.

---

## Required Actions Before Merge

1. **[Blocking — VR-2]** Generate and commit `.layout.json` placement snapshots for all three golden fixtures (`test`, `simple`, `multipage`) by running `reflow_document` against the parsed IR of each fixture and writing the resulting placement list. Update `TestEquivalenceGolden` to load at least one real golden fixture and compare its reflow output against the committed `.layout.json` snapshot. Without this, placement regressions in `bbox_reflow.py` are undetectable.

2. **[Blocking — VR-1 / Open Risk from design.md]** Confirm whether the fitz adapter applies `page.search_for()` quad refinement after receiving `reflow_document` output, and if so, measure the maximum observed coordinate delta on the golden fixtures. If the delta can exceed 2.0 pt, either (a) widen the documented tolerance with recorded rationale, or (b) suppress quad refinement in the OVERLAY path to keep coordinates within the reflow output. Record the resolution in `design.md §Open Risks`.

3. **[Recommended — VR-3]** Update `TestEquivalenceGolden` to drive at least one golden fixture PDF through `reflow_document` (using its parsed IR) rather than the synthetic `_make_doc()` document, so real-content edge cases are covered by the snapshot regression.

---

## Decision

**approve-with-risk**

The test suite is architecturally sound: routing both render backends through a single shared `reflow_document` component is the correct structural proof of BR-35 element-level identity. The unit, resilience, and data-boundary coverage is thorough. The tolerance derivation is grounded. Two blocking items prevent full approval:

1. No `.layout.json` golden snapshots exist, leaving the placement-regression safety net absent for the durable fixture set.
2. The fitz quad-refinement open risk (design.md §Open Risks) is unresolved; if quad refinement pushes coordinates beyond ±2.0 pt the tolerance contract is violated with no test catching it.

These items must be resolved (or explicitly accepted with owner and follow-up recorded) before the gate closes.
