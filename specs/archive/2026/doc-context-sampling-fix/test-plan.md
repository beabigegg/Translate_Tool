---
change-id: doc-context-sampling-fix
schema-version: 0.1.0
last-changed: 2026-07-09
risk: medium
tier: 3
---

# Test Plan: doc-context-sampling-fix

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | unit | tests/test_orchestrator_context_detection.py::test_sample_file_text_reads_legacy_xls_via_conversion | 0 |
| AC-1 | integration | tests/test_orchestrator_context_detection.py::test_process_files_context_detected_for_legacy_xls | 1 |
| AC-2 | unit | tests/test_orchestrator_context_detection.py::test_sample_file_text_docx_table_only_includes_cell_text | 0 |
| AC-3 | unit | tests/test_orchestrator_context_detection.py::test_sample_file_text_pptx_table_includes_cell_text | 0 |
| AC-4 | unit | tests/test_orchestrator_context_detection.py::test_detect_document_context_logs_info_reason_on_exception | 0 |
| AC-4 | unit | tests/test_orchestrator_context_detection.py::test_process_files_logs_info_reason_when_sample_empty | 0 |
| AC-5 | unit | tests/test_orchestrator_context_detection.py::test_detect_document_context_logs_info_on_success | 0 |
| AC-6 | data-boundary | tests/test_orchestrator_context_detection.py::test_sampling_exception_degrades_to_no_preamble_job_completes | 1 |
| AC-7 | integration | tests/test_orchestrator_context_detection.py::test_xls_sampling_does_not_double_convert_via_libreoffice | 1 |
| AC-8 | integration | tests/test_orchestrator_context_detection.py::test_legacy_xls_and_table_only_docx_both_emit_context_detected | 1 |

Regression (no new tests, existing suite must stay green): tests/test_context_prompt_i18n.py (preamble assembly once sample non-empty), tests/test_context_prefix_bleed.py (system-channel routing untouched), tests/test_orchestrator_phase0.py (Phase 0 hook untouched).

## Test Families Required

Applicable: unit, integration, data-boundary.

| family | tier | notes |
|---|---|---|
| unit | 0 | `_sample_file_text` per-format branches called directly against real fixture files (not mocks) — asserts a specific known token from table cells / legacy-xls cell content is present in the returned string, never merely non-empty. `_detect_document_context` INFO-logging asserted via `caplog.at_level(logging.INFO)` against the real logger record, not a patched `.info()` call. |
| integration | 1 | Full `process_files()` run against a real fixture file (docx/pptx/xls), HTTP boundary mocked at `requests.Session.post`, LibreOffice boundary mocked at `subprocess.Popen` (per `tests/test_libreoffice_helpers.py` convention) — never at `xls_to_xlsx`'s own internals. Asserts on `caplog`/captured `log` text and on Popen call-count, not on internal attribute writes. |
| data-boundary | 1 | Sampler raises / returns unreadable bytes for each of `.docx`, `.pptx`, `.xls` — asserts `process_files()` still completes (`stopped is False`) with no `Document context:` preamble reaching the outgoing request, proving graceful degradation rather than job abort. |

## Fixtures Required

- Table-only `.docx`: generate at test time via `python-docx` (`doc.add_table`, no/blank `doc.add_paragraph`) with a distinctive cell token (e.g. `"PANJIT-TABLE-TOKEN-771"`), mirroring `tests/test_docx_parser.py::table_docx`. No binary committed.
- `.pptx` with only a table shape (no `has_text_frame` shape): generate at test time via `python-pptx` `slide.shapes.add_table(...)` with a distinctive cell token. A table shape is itself a `GraphicFrame`, so this single fixture proves AC-3's "table and graphic-frame" wording without needing real SmartArt XML.
- Legacy binary `.xls` with a distinctive cell token: **cannot** be produced by `openpyxl` (write-only for `.xlsx`) or `python-docx`/`python-pptx`. Two options, decision deferred to implementation-planner: (a) commit a small binary fixture `tests/fixtures/legacy_sample.xls` (produced once, offline, e.g. via LibreOffice `--convert-to xls` from a throwaway `.xlsx`), or (b) add `xlwt` as a test-only dependency to author it programmatically. Either way the fixture must carry a distinctive token the test asserts on, not merely be present.

## Test Execution Ladder

| phase | required | command source | max failures | result artifact |
|---|---:|---|---:|---|
| collect | yes | cdd-kit test select | 1 | test-runs/<run-id>/summary.json |
| targeted | yes | cdd-kit test select | 1 | test-evidence.yml |
| changed-area | yes | cdd-kit test select | 1 | test-evidence.yml |
| full | final/CI | cdd-kit test run --phase full | 1 | test-evidence.yml |

changed-area scope: `tests/test_orchestrator_context_detection.py tests/test_libreoffice_helpers.py` (add the latter only if a new reuse/caching helper lands there for AC-7). Do not widen to whole `test_pdf_*`/QE files — unrelated pre-existing env artifacts (see CLAUDE.md learnings).

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| (none identified) | — | Prior change's AC-1..AC-7 tests in `test_orchestrator_context_detection.py` remain valid; this change only adds new tests below them. |

## Stop Rules

- Do not run broad pytest before targeted and changed-area phases pass.
- Do not investigate more than the first failure per phase.
- Do not classify any failure as known, pre-existing, waived, or allowed.
- If full suite fails, record the first failure and block the gate.

## Out of Scope

- xlsx table-batch phantom-column defect (`ws.max_column`=257 → `table_serializer.parse()` returns `None`) — deferred to the JSON structured-I/O change; no tests touch `table_serializer.parse()`.
- `Document context:` injection wiring into the system prompt — already covered by `tests/test_orchestrator_context_detection.py` (prior change `cloud-doc-context-summary`); not re-tested here.
- `.pdf` and `.doc` sampling branches — unaffected by this change's ACs (already return non-empty text/stem fallback).
- Real SmartArt XML text extraction for sampling (`pptx_processor._extract_smartart_texts` is a translation-path helper, not a sampling-path one) — table-shape coverage suffices for AC-3.
- `CONTEXT_DETECTION_ENABLED` / `QWEN_CONTEXT_FLOW_ENABLED` / translation-dedicated gating — already regression-locked by the prior change's AC-3/AC-4 tests in the same file.

## Notes

- AC-7's "does not double-convert" must be proven by mocking `subprocess.Popen` (process boundary, per `test_libreoffice_helpers.py::_FakePopen`) across one full `process_files()` run on a single `.xls` file and asserting total invocation count — never by reading the implementation.
- If backend-engineer adds a caching/reuse helper in `libreoffice_helpers.py` for AC-7, add a companion unit test there for that helper directly.
- All new tests must fail RED against current `orchestrator.py` (empty-string sampler branches, `logger.debug`-only swallow) before the fix lands.
