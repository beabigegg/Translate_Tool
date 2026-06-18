# QA Report — p2-ir-document-model

## Release Decision
**approved-with-risk**

## Test Evidence
- `specs/changes/p2-ir-document-model/test-evidence.yml` — all required phases passed
  - collect: passed
  - targeted: passed (tests/test_translatable_document.py)
  - changed-area: passed (IR tests, PDF parser tests, decoupling tests, golden regression)
  - contract: passed (TestBackwardCompat, TestRoundTripFidelity)
  - final-status: passed

## Acceptance Criteria Status

| criterion | status | evidence |
|---|---|---|
| AC-1: ElementType has TABLE/FIGURE/FORMULA/LIST; all existing values remain | PASS | TestElementType — 4 tests |
| AC-2: reading_order field present; pdf_parser does not use round(y0,10pt) for ordering | PASS | TestTranslatableElementReadingOrder + TestReadingOrderField |
| AC-3: Round-trip fidelity (bbox, font, element_type, reading_order) | PASS | TestRoundTripFidelity — 5 tests |
| AC-4: Backward-compat (old-format dicts deserialize); to_dict compatible | PASS | TestBackwardCompat — 8 tests |
| AC-5: Re-render without re-parse; swap MT engine without re-render | PASS | tests/test_ir_pipeline_decoupling.py |
| AC-6: 3-5 golden samples per format (PDF/DOCX/PPTX) | PARTIAL — PDF only (3 files); DOCX/PPTX deferred (see risk below) |
| AC-7: Dual-run comparison framework runs offline, wired as CI gate | PASS for PDF; DOCX/PPTX coverage deferred |
| AC-8: Translation main-path and API surface unchanged | PASS | test_ir_pipeline_decoupling.py::test_public_api_unchanged |

## Known Risks (Approved)

### RISK-1 (Medium): DOCX/PPTX golden fixtures deferred
**Description**: The CI gate golden-sample-regression runs only PDF samples. DOCX/PPTX directories contain `.gitkeep` placeholders. `test_golden_docx_parse_ir_stable` and `test_golden_pptx_parse_ir_stable` skip gracefully when no fixtures are present.

**Impact**: AC-6/AC-7 are partially unmet for DOCX and PPTX formats. The dual-run comparison harness is implemented and functional for PDF; it will cover DOCX/PPTX automatically once fixtures are committed.

**Mitigation**: CI contract updated to document the deferral explicitly. The harness skip-on-missing-fixtures behavior ensures no false pass — tests skip and report clearly. The PDF coverage (3 files, committed snapshots) demonstrates the framework is correct.

**Owner**: test-strategist / next iteration
**Follow-up**: Commit 3+ license-clean `.docx` and `.pptx` test fixtures to `tests/fixtures/golden/docx/` and `tests/fixtures/golden/pptx/`. No separate tracked change needed — can be committed directly to this branch or the follow-up `p2-layout-detection` change.
**Exit date**: Before `p2-renderer-convergence` gate (requires golden samples for renderer regression testing).

### RISK-2 (Low): Stale `TestPyMuPDFParserIntegration::test_reading_order`
**Description**: Pre-existing test asserts monotonic reading order via `round(y0/10)*10` bucket comparison. Still passes because sequential `reading_order` is also monotonically non-decreasing. But the test no longer guards AC-2's "no bucketing" prohibition specifically.

**Impact**: AC-2 guard is now provided by `TestReadingOrderField::test_reading_order_sequential_not_y_bucket`. The stale test adds no regression risk; it just tests a weaker property.

**Owner**: Not addressed in this change — acceptable technical debt given the new dedicated test covers AC-2 properly.

### RISK-3 (Low): Golden snapshot auto-initialization on first run
**Description**: `_load_or_create_snapshot()` writes a new snapshot JSON if none exists, then passes. This means a new fixture added without a committed snapshot would silently auto-pass on first CI run.

**Mitigation**: PDF snapshots are now committed (`tests/fixtures/golden/pdf/*.ir.json`), so the 3 PDF samples are protected against silent auto-pass. DOCX/PPTX will need committed snapshots when fixtures are added.

**Owner**: test-strategist — add CI guard that fails (not writes) when a snapshot is missing.
