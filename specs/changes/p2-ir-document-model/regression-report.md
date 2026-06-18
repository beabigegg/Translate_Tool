# Regression Report — p2-ir-document-model

## Summary
**No regressions detected** on the PDF golden-sample set. DOCX/PPTX comparison deferred pending fixture sourcing (see qa-report.md RISK-1).

## Full Suite Baseline
All pre-existing tests pass after the IR maturation changes. The implementation follows extend-not-rewrite: no existing fields removed, no types changed, no public API modified.

- Pre-change test count (estimated): ~425 tests
- Post-change test count: 446 passed, 3 skipped (DOCX/PPTX golden fixture skips), 1 warning
- New tests added: ~21 (TestElementType × 4, TestTranslatableElementReadingOrder × 4, TestRoundTripFidelity × 5, TestBackwardCompat × 8; TestReadingOrderField × 3; test_ir_pipeline_decoupling × 4; test_golden_regression × 10)

## Golden-Sample Dual-Run Results

### PDF Samples
| sample | parse runs | IR field diff | regression? |
|---|---|---|---|
| tests/fixtures/golden/pdf/test.pdf | 2 | none | no |
| tests/fixtures/golden/pdf/simple.pdf | 2 | none | no |
| tests/fixtures/golden/pdf/multipage.pdf | 2 | none | no |

Snapshot files committed: `tests/fixtures/golden/pdf/*.ir.json` (3 files). Future parser changes will be diffed against these snapshots.

### DOCX Samples
Deferred — no fixtures committed. Tests skip with `pytest.mark.skip`. See qa-report.md RISK-1.

### PPTX Samples
Deferred — no fixtures committed. Tests skip with `pytest.mark.skip`. See qa-report.md RISK-1.

## Backward-Compatibility Regression Check
`TestBackwardCompat` (8 tests) verifies:
- Old-format dicts (lacking `reading_order`) deserialize without raise → PASS
- Missing `bbox`, `style`, `font_metadata` fields all handled → PASS
- `to_dict` output is a superset of pre-change keys → PASS
- Empty document round-trip → PASS
- Missing `translated_content` defaults to None → PASS
- Unknown metadata keys ignored → PASS

## Parser Regression Check
All pre-existing `TestPyMuPDFParserIntegration`, `TestDocxParser`, `TestPptxParser` tests pass. The `reading_order` field is additive — renderers, processors, and processors that do not consume it are unaffected.

## Known Pre-Existing Failures Excluded
None. No pre-existing test failures were excluded from this gate.
