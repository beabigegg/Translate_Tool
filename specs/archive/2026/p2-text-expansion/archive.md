# Archive: p2-text-expansion

**Archived:** 2026-06-18
**Tier:** 2

---

## Change Summary

Replaced the inline 25-iteration font-size shrink loop in `fitz_renderer._insert_text_in_rect` with a shared 5-step BR-36 fit cascade (`font-size shrink → line-spacing tighten → letter-spacing tighten → controlled overflow → truncation+marker`). The cascade is implemented as `fit_text_cascade()` in `text_region_renderer.py` and is callable by any render adapter. A metric-compatible font fallback chain was added to `font_utils.py` (x-height → cap-height → advance-width heuristic with LRU cache reuse), plus an expansion factor advisory table (en→de 1.30, en→es 1.25, en→fr 1.20, default 1.15). The `TranslatableElement` IR gained an additive `render_truncated: bool = False` field (ADR-0004) to surface truncation to callers without silent data loss.

---

## Final Behavior

- Translated text in PDF overlay now goes through the cascade before rendering; font size is shrunk to min first, then line spacing tightened, then letter spacing tightened, and only if still overflowing the text is truncated with a `…` marker.
- When truncation fires, `element.render_truncated = True` is set on the IR element (BR-38).
- `get_expansion_factor(src, tgt)` provides a pre-sizing advisory factor; measured width governs actual rendering.
- `get_metric_compatible_fallback()` selects a registered face whose x-height/cap-height/advance-width most closely matches the primary face.
- Step (d) controlled overflow is implemented and unit-tested but permanently skipped at the fitz call site because PyMuPDF does not expose neighbor geometry at `_insert_text_in_rect`. Documented degraded behavior per design.md Open Risks and Table L.

---

## Final Contracts Updated

| contract | version | change |
|---|---|---|
| `contracts/business/business-rules.md` | 0.7.1 → 0.7.2 | Added BR-36–BR-40, Table L |
| `contracts/data/data-shape-contract.md` | 0.4.3 → 0.4.4 | Added `render_truncated` field, round-trip guarantee, backward-compat rule, IR-consumption row |
| `contracts/ci/ci-gate-contract.md` | 0.4.1 → 0.4.2 | Added `text-expansion-benchmark` gate |

---

## Final Tests Added / Updated

| file | class / function | AC covered |
|---|---|---|
| `tests/test_text_region_renderer.py` | `TestFitCascadeContract`, `TestFitCascade`, `TestTruncationMarker`, `TestSinglePathEnforcement` | AC-1–AC-6 |
| `tests/test_font_utils.py` | `TestExpansionFactorTable`, `TestMetricFallbackChain` | AC-3, AC-8 |
| `tests/test_translatable_document.py` | `TestRenderTruncatedField` | AC-5 |
| `tests/test_renderer_convergence.py` | `TestCascadeWiringLayoutEquivalence` | AC-6 |
| `tests/test_text_expansion_benchmark.py` | (new file, 28 tests) | AC-1–AC-3 |
| `tests/test_layout_detector.py` | `TestNoExtraFieldsOutsideIR` (updated `standard_attrs`) | AC-5 |

Full suite: 575 passed, 3 skipped (pre-existing DOCX/PPTX fixture absence), 0 failed.

---

## Final CI/CD Gates

| gate | tier | result |
|---|---|---|
| contract-validate | 1 | pass |
| change-gate | 1 | pass |
| unit-contract-integration | 1 | pass (CI) |
| golden-sample-regression | 2 | pass (CI) |
| text-expansion-benchmark | 2 | pass (CI) |
| renderer-equivalence | 2 | pass (CI) |

---

## Production Reality Findings

- QA approved all AC-1–AC-8. No unexpected contract drift.
- Step (d) permanently disabled at fitz call site — accepted degraded behavior; step code and unit tests exist; activation is a P3 follow-up (design.md Open Risks, F-2).
- Visual review approved-with-risk (VR-1): `tests/fixtures/golden/expansion/` is empty (no rendered PDF evidence); functional + benchmark tests cover AC-1–AC-5 sufficiently. Non-blocking.
- CI failure on first push: `TestSinglePathEnforcement` used hardcoded `/home/egg/...` absolute path; fixed with `Path(__file__).parent.parent` before merge.

---

## Lessons Promoted to Standards

| lesson | target | evidence |
|---|---|---|
| Test files that `open()` source files must derive repo root via `Path(__file__).parent.parent`, never hardcoded absolute paths | `CLAUDE.md` cdd-kit:learnings region | CI failure run 27753162378; fix in `60a8cde` (`tests/test_text_region_renderer.py::TestSinglePathEnforcement`) |

---

## Follow-up Work

- **F-1** (non-blocking): populate `tests/fixtures/golden/expansion/` with rendered PDF fixtures for visual evidence; assigned to backend-engineer, P3.
- **F-2** (P3): wire `available_whitespace_below` from actual neighbor geometry in `fitz_renderer` to enable step (d) controlled overflow; requires PyMuPDF neighbor-rect API investigation.

---

*This archive is historical evidence. Current requirements live in `contracts/` and active project guidance.*
