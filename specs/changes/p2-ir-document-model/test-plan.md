---
change-id: p2-ir-document-model
schema-version: 0.1.0
last-changed: 2026-06-18
risk: medium
tier: 1
---

# Test Plan: p2-ir-document-model

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | unit | tests/test_translatable_document.py::TestElementType | 0 |
| AC-2 | unit | tests/test_translatable_document.py::TestTranslatableElement | 0 |
| AC-2 | unit | tests/test_pdf_parser.py::TestReadingOrderField | 0 |
| AC-3 | unit | tests/test_translatable_document.py::TestRoundTripFidelity | 0 |
| AC-4 | data-boundary | tests/test_translatable_document.py::TestBackwardCompat | 0 |
| AC-5 | integration | tests/test_ir_pipeline_decoupling.py | 1 |
| AC-6 | data-boundary | tests/test_golden_regression.py::test_golden_fixture_inventory | 1 |
| AC-7 | regression | tests/test_golden_regression.py | 1 |
| AC-8 | integration | tests/test_ir_pipeline_decoupling.py::test_public_api_unchanged | 1 |

## Test Families Required

| family | tier | notes |
|---|---|---|
| unit | 0 | Extend `tests/test_translatable_document.py`; no I/O |
| data-boundary | 0 | Malformed/partial IR cases; same file; offline |
| integration | 1 | New file: parser→IR→renderer round-trips; offline fixture files only |
| regression (golden) | 1 | New `tests/test_golden_regression.py`; dual-run comparison; no network/GPU |

## Test Names

### tests/test_translatable_document.py — new classes appended

**TestElementType**
- `test_region_types_present` — TABLE, FIGURE, FORMULA, LIST exist on ElementType
- `test_existing_types_unchanged` — all 8 pre-existing values still present with same string values
- `test_unknown_element_type_from_dict_raises` — ElementType("nonexistent") raises ValueError
- `test_element_type_values_are_strings` — every .value is a lowercase string

**TestTranslatableElement additions**
- `test_reading_order_default_none` — new field defaults to None
- `test_reading_order_roundtrip` — integer reading_order serializes/deserializes correctly
- `test_reading_order_none_roundtrip` — None reading_order survives to_dict→from_dict
- `test_region_element_types_accepted` — element_type=TABLE/FIGURE/FORMULA/LIST constructs without error

**TestRoundTripFidelity**
- `test_full_ir_roundtrip_preserves_bbox` — x0/y0/x1/y1 exact after to_dict→from_dict
- `test_full_ir_roundtrip_preserves_font_metadata` — font_name, font_size, is_bold, color preserved
- `test_full_ir_roundtrip_preserves_element_type` — all ElementType values survive
- `test_full_ir_roundtrip_preserves_reading_order` — int and None preserved
- `test_document_roundtrip_element_count` — element list length unchanged

**TestBackwardCompat**
- `test_from_dict_missing_reading_order_defaults_none` — old dict without reading_order deserializes cleanly
- `test_from_dict_missing_bbox_ok` — old element without bbox key → bbox=None
- `test_from_dict_missing_style_ok` — old element without style key → style=None
- `test_from_dict_missing_font_metadata_fields_ok` — StyleInfo.from_dict with absent keys uses defaults
- `test_to_dict_keys_are_superset_of_old_keys` — no key removals from to_dict output
- `test_empty_elements_list_roundtrip` — document with zero elements round-trips cleanly
- `test_partial_ir_missing_translated_content` — element dict without translated_content → None
- `test_from_dict_unknown_key_in_metadata_field_ignored` — unknown key in metadata dict does not raise

### tests/test_pdf_parser.py — new class appended

**TestReadingOrderField**
- `test_reading_order_is_integer_or_none` — every element from PyMuPDFParser has reading_order: int | None
- `test_reading_order_sequential_not_y_bucket` — values are sequential ints, not round(y0/10) products
- `test_region_element_types_emitted` — parser emits TABLE element_type when table detected

### tests/test_ir_pipeline_decoupling.py (new file)

- `test_rerender_without_reparse` — translate IR in-memory, render; assert parse not called
- `test_swap_mt_engine_without_rerender` — replace translated_content in loaded IR, re-render; parse not called
- `test_public_api_unchanged` — translate_pdf/translate_docx/translate_pptx accept same positional args
- `test_ir_carries_new_fields_after_pdf_parse` — reading_order and region types present post-parse

### tests/test_golden_regression.py (new file)

- `test_golden_fixture_inventory` — at least 3 PDF, 3 DOCX, 3 PPTX files exist under tests/fixtures/golden/
- `test_golden_pdf_parse_ir_stable[<sample>]` — parametrized; element count and type distribution match snapshot
- `test_golden_docx_parse_ir_stable[<sample>]` — same for DOCX
- `test_golden_pptx_parse_ir_stable[<sample>]` — same for PPTX
- `test_dual_run_diff_no_regressions[<sample>]` — parse same file twice; IR dicts identical (determinism)
- `test_golden_offline_no_network` — golden tests pass with socket monkeypatched closed

## Golden-Sample Set Design

**Location:** `tests/fixtures/golden/{pdf,docx,pptx}/` + companion `*.ir.json` snapshots.
- 3–5 files per format; ≤ 2 pages each; committed to repo (no network fetch at test time).
- Coverage: plain text, title, at least one table, one list, one figure/caption.
- Snapshot format: `{element_count, element_types: {type: count}, reading_order_present: bool}`.
- Dual-run check: parse each file twice with identical parser config; diff IR dicts; any diff = failure.
- No GPU, no Ollama call required in any golden test.

## Out of Scope

- Scanned PDF / OCR path
- GPU-accelerated layout detection
- XLSX IR extension
- Translation quality of golden samples (structure only)
- Win32COM / LibreOffice processor paths

## Notes

- All Tier 0 tests must be red before implementation begins.
- `test_reading_order_sequential_not_y_bucket` is the primary guard for the bucketing prohibition (AC-2).
- `TestBackwardCompat` supplies all 8 required data-boundary cases (AC-4).
- Golden snapshot JSON files act as version-controlled IR contracts (AC-7).
- `test_dual_run_diff_no_regressions` proves parse determinism as a CI gate.
