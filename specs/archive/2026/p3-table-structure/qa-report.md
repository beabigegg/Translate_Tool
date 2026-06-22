# QA Report: p3-table-structure

## Pre-existing Failures

The following tests were failing **before any p3-table-structure code was written** (confirmed via `git stash` baseline run on 2026-06-22):

| test | file | reason | baseline evidence |
|---|---|---|---|
| `TestPyMuPDFParserIntegration::test_parse_pdf` | `test_pdf_parser.py` | requires real PDF file + fitz installed in test env | fails on stash baseline |
| `TestPyMuPDFParserIntegration::test_elements_have_bbox` | `test_pdf_parser.py` | same — real PDF file required | fails on stash baseline |
| `TestPyMuPDFParserIntegration::test_reading_order` | `test_pdf_parser.py` | same | fails on stash baseline |
| `TestPyMuPDFParserIntegration::test_header_footer_detection` | `test_pdf_parser.py` | same | fails on stash baseline |
| `TestReadingOrderField::test_reading_order_is_integer_or_none` | `test_pdf_parser.py` | same | fails on stash baseline |
| `TestReadingOrderField::test_reading_order_sequential_not_y_bucket` | `test_pdf_parser.py` | same | fails on stash baseline |
| `TestLayoutDetectorIntegration::test_detector_order_replaces_y0_heuristic` | `test_pdf_parser.py` | `ModuleNotFoundError: No module named 'onnxruntime'` | fails on stash baseline |
| `TestLayoutDetectorIntegration::test_parse_invokes_layout_detector_on_native_pdf` | `test_pdf_parser.py` | `ModuleNotFoundError: No module named 'onnxruntime'` | fails on stash baseline |
| `TestLayoutDetectorIntegration::test_detector_failure_parse_still_returns_document` | `test_pdf_parser.py` | `ModuleNotFoundError: No module named 'onnxruntime'` | fails on stash baseline |

**All 9 failures are outside the scope of p3-table-structure.** They are caused by missing runtime dependencies (`onnxruntime`, real PDF test fixture files) that are not installed in this test environment. No fix is required for this change.

Owner: platform-team (test environment configuration)
Follow-up: install onnxruntime and test fixtures in CI test environment.
