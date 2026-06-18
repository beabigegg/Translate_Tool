# Archive — p2-ir-document-model

> Cold Data Warning: This archive is historical evidence. Current requirements live in `contracts/` and active project guidance.

## Change Summary

Matured `TranslatableDocument` / `TranslatableElement` (defined in `app/backend/models/translatable_document.py`) into a fully decoupled parse↔translate↔render intermediary layer. The IR previously served as a thin data bag with 8 element types and no reading-order field. This change expanded it to 12 element types (adding `table`, `figure`, `formula`, `list` with lowercase wire values matching the existing enum pattern per ADR 0002), added an optional `reading_order: int | None` field that parsers now assign sequentially after their final extraction/sort, updated serialization/deserialization to handle both old-format and new-format dicts without raising, and introduced a golden-sample regression harness with committed PDF snapshots and a CI gate to guard against silent IR drift.

## Final Behavior

- `ElementType` now contains 12 members: 8 original + `TABLE`, `FIGURE`, `FORMULA`, `LIST` (all lowercase wire values).
- Every `TranslatableElement` carries a `reading_order: Optional[int]` field. PDF, DOCX, and PPTX parsers assign sequential integers (0-based) after their internal sort step; the field is `None` only for elements that pre-date the field or came from external callers that don't set it.
- `get_elements_in_reading_order()` uses a two-bucket sort: elements with an explicit `reading_order` first (sorted by index), then null-`reading_order` elements (sorted by page_num, bbox.y0, bbox.x0). In practice all parser-produced documents fall into the first bucket.
- `to_dict()` / `from_dict()` are backward-compatible: old dicts lacking `reading_order` deserialize cleanly via `data.get("reading_order", None)`.
- The golden-sample regression CI job runs on every PR against committed `.ir.json` snapshots; any pre-existing-field diff blocks merge.

## Final Contracts Updated

| contract | version | change |
|---|---|---|
| `contracts/data/data-shape-contract.md` | v0.4.0 | Added IR section: ElementType enum table (12 values, lowercase wire), TranslatableElement field shape, BoundingBox/StyleInfo/TranslatableDocument shapes, round-trip guarantee, backward-compat rule, known-consumers table |
| `contracts/ci/ci-gate-contract.md` | v0.2.0 | Added `golden-sample-regression` gate row and Required Check Policy section |
| `contracts/CHANGELOG.md` | — | Prepended [data 0.4.0] and [ci 0.2.0] entries |

Evidence: `agent-log/backend-engineer.yml`, `agent-log/ci-cd-gatekeeper.yml`

## Final Tests Added / Updated

| file | class / test | purpose |
|---|---|---|
| `tests/test_translatable_document.py` | `TestElementType` (4 tests) | AC-1: new enum members, wire values, existing unchanged |
| `tests/test_translatable_document.py` | `TestTranslatableElementReadingOrder` (4 tests) | AC-2: field default, assignment, sort |
| `tests/test_translatable_document.py` | `TestRoundTripFidelity` (5 tests) | AC-3: round-trip of all fields including reading_order |
| `tests/test_translatable_document.py` | `TestBackwardCompat` (8 tests) | AC-4: old-format dict deserialization |
| `tests/test_pdf_parser.py` | `TestReadingOrderField` (3 tests) | AC-2: PDF parser assigns int, not y-bucket |
| `tests/test_ir_pipeline_decoupling.py` | 4 tests | AC-5/AC-8: re-render without re-parse; swap MT without re-render |
| `tests/test_golden_regression.py` | 10 tests | AC-6/AC-7: dual-run offline comparison against committed snapshots |

Evidence: `agent-log/test-strategist.yml`, `agent-log/backend-engineer.yml`

## Final CI/CD Gates

| gate | tier | trigger |
|---|---|---|
| `cdd-kit validate --contracts` | 1 (required) | pre-commit / PR |
| `cdd-kit gate p2-ir-document-model` | 1 (required) | pre-commit / PR |
| `pytest tests/ -x -q --tb=short` | 1 (required) | PR |
| `pytest tests/test_golden_regression.py --tb=short -q` | 1 (required) | PR |

Evidence: `agent-log/ci-cd-gatekeeper.yml`, `ci-gates.md`

## Production Reality Findings

- **IP-7 (wire-value case)**: Flagged by `implementation-planner` as a risk. In practice, `data-shape-contract.md` already reflected lowercase wire values from the outset; no conflict to resolve at implementation time.
- **DOCX/PPTX golden fixtures deferred**: No license-clean test files were available at change time. Tests skip gracefully via `pytest.mark.skip`; the harness is functional and will activate automatically when fixtures are added. Explicitly deferred in `contracts/ci/ci-gate-contract.md` and `qa-report.md` RISK-1. Exit date: before `p2-renderer-convergence` gate.
- **Pre-existing stale test** (`TestPyMuPDFParserIntegration::test_reading_order`) still asserts monotonic bucket order — passes because sequential ordering is also monotonically non-decreasing. Documented in `qa-report.md` RISK-2; new dedicated test `TestReadingOrderField::test_reading_order_sequential_not_y_bucket` provides the correct AC-2 guard.

Evidence: `qa-report.md`, `regression-report.md`, `agent-log/backend-engineer.yml`

## Lessons Promoted to Standards

| lesson | target | version | evidence |
|---|---|---|---|
| A — ElementType wire-value convention (lowercase MUST) | `contracts/data/data-shape-contract.md` §ElementType wire-value convention | 0.4.0 → 0.4.1 | `docs/adr/0002-ir-elementtype-serialized-values.md` |
| C — Golden snapshot auto-init must fail (not write) | `contracts/ci/ci-gate-contract.md` §golden-sample-regression gate, snapshot initialization bullet | 0.2.0 → 0.3.0 | `qa-report.md` RISK-3, `agent-log/backend-engineer.yml` |
| F — Informational gate promotion policy | `contracts/ci/ci-gate-contract.md` §Informational Gate Promotion Policy | rides C's 0.3.0 bump | `agent-log/ci-cd-gatekeeper.yml` |

Lessons B (IR backward-compat rule), D (DOCX/PPTX sourcing gap), E (two-bucket sort): not promoted — already verbatim in contract (B, E) or one-off logistics with no durable cross-change rule (D).

## Follow-up Work

1. **DOCX/PPTX golden fixtures** — commit 3+ license-clean `.docx` and `.pptx` files to `tests/fixtures/golden/docx/` and `tests/fixtures/golden/pptx/`; snapshots auto-initialize on first CI run. Required before `p2-renderer-convergence` gate.
2. **Snapshot fail-not-write guard** — add CI guard to `test_golden_regression.py` that fails (not silently writes) when a snapshot JSON is missing; prevents RISK-3 (auto-init on new fixture without committed snapshot).
3. **Stale test cleanup** — update or remove `TestPyMuPDFParserIntegration::test_reading_order` which guards a weaker property than AC-2 now requires.
