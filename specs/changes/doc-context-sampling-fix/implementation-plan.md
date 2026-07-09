---
change-id: doc-context-sampling-fix
schema-version: 0.1.0
last-changed: 2026-07-09
---

# Implementation Plan: doc-context-sampling-fix

## Objective
Make the BR-109 document-context sampler (`_sample_file_text`) return real,
representative text for the three document shapes it currently drops to `""` —
legacy binary `.xls`, table-only `.docx`, and table/graphic-frame `.pptx` — so
the one-sentence context summary actually fires in production; and make the
skip/failure/success outcome of context detection observable at INFO level so a
silent skip can never again masquerade as "ran". Sampling must stay cheap and
must never raise into the job pipeline (degrade to no preamble).

## Execution Scope

### In Scope
- `_sample_file_text` `.docx` branch: also read `doc.tables` cell text, not only
  `doc.paragraphs`.
- `_sample_file_text` `.pptx` branch: also read table/graphic-frame cell text,
  not only `shape.has_text_frame` shapes.
- `_sample_file_text` `.xls` sampling: obtain real text via the existing
  LibreOffice `.xls`→`.xlsx` conversion (`xls_to_xlsx`) into a throwaway temp
  file, read with openpyxl, delete the temp; guard with
  `is_libreoffice_available()` and degrade to `""` when unavailable
  (see Decision Record).
- Observability in `orchestrator.py`: emit INFO through the module logger
  (`logging.getLogger(__name__)`, defined at `orchestrator.py:51`) for
  (a) successful detection (`[CONTEXT] Detected:`), (b) a caught detection
  exception (reason), and (c) an empty sample when detection would otherwise
  have run.
- New tests in `tests/test_orchestrator_context_detection.py` per test-plan.md
  AC-1..AC-8 mapping (owned by test-strategist / bug-fix-engineer).

### Out of Scope
- The xlsx table-batch phantom-column defect (`ws.max_column`=257 →
  `table_serializer.parse()` returns `None`). Deferred to the JSON structured-I/O
  change (change-request.md Non-goals). No file/test may touch
  `table_serializer.parse()`.
- Any change to how the summary is DELIVERED to the model (BR-109 delivery /
  ADR-0016 system-channel wiring, `build_strategy` injection,
  `client.system_prompt`). Only how the sample is obtained and how the outcome
  is logged.
- New env vars or feature flags. `CONTEXT_DETECTION_ENABLED` (config constant)
  and `QWEN_CONTEXT_FLOW_ENABLED` (env var) stay unchanged.
- Eliminating the second, in-production `.xls` conversion performed by
  `translate_xlsx_xls` (see Known Risks — accepted tradeoff, forbidden by the
  "do not change per-file timing semantics" constraint).
- `.pdf` / `.doc` sampling branches, real SmartArt XML extraction, and the
  translation-path processors (`docx_processor`/`pptx_processor` translation
  logic) — unaffected by these ACs.

## Required Changes
| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | orchestrator `.docx` sampling | Extend `_sample_file_text` `.docx` branch to append non-empty `doc.tables[*].rows[*].cells[*].text` after paragraphs, honoring the `max_chars` budget | backend-engineer |
| IP-2 | orchestrator `.pptx` sampling | Extend `_sample_file_text` `.pptx` branch to read table cells for graphic-frame/table shapes (`getattr(shape, "has_table", False)` → `shape.table.rows`→`cells`→`cell.text`) in addition to `has_text_frame` shapes, honoring `max_chars` | backend-engineer |
| IP-3 | orchestrator `.xls` sampling | Split the `.xls`/`.xlsx` branch: keep openpyxl for `.xlsx`; for `.xls`, if `is_libreoffice_available()` convert to a temp `.xlsx` via `xls_to_xlsx`, read it with the existing openpyxl row loop, delete the temp; if LibreOffice absent, return `""`. Must never raise (see IP-6) | backend-engineer |
| IP-4 | detection success INFO | In `_detect_document_context` success path, additionally emit `logger.info("[CONTEXT] Detected: %s", context)` (keep the existing `log(...)` callback for translator.log) | backend-engineer |
| IP-5 | detection failure INFO | In `_detect_document_context` exception handler, raise the swallow from `logger.debug` to `logger.info` including the reason (exception) | backend-engineer |
| IP-6 | empty-sample INFO | In `process_files` (context block ~L560-568), when `CONTEXT_DETECTION_ENABLED and QWEN_CONTEXT_FLOW_ENABLED and not client._is_translation_dedicated()` but `sample` is falsy, emit an INFO skip line naming the file and reason; do NOT call `_detect_document_context` | backend-engineer |
| IP-7 | reproduction/regression evidence | Record a genuinely-FAILED pre-fix behavioral `cdd-kit test run` (assertion failure) for at least one new sampler test, then green post-fix, per bug-fix evidence rules | bug-fix-engineer |
| IP-8 | tests | Author AC-1..AC-8 tests in `tests/test_orchestrator_context_detection.py` per test-plan.md mapping, including the real-`.xlsx`-writing Popen fake (see Test Execution Plan) | test-strategist |

## Source Artifact Pointers
| source | relevant pointer | used for |
|---|---|---|
| test-plan.md | AC→test mapping table; Fixtures Required; Notes | test node ids, fixture generation, mock boundaries |
| test-plan.md | Test Execution Ladder; changed-area scope | required phases + scoped targets |
| ci-gates.md | Required Gates table; Risk Analysis | verification job (`contract-and-fast-tests` blanket `pytest tests/ -x -q`) |
| contracts/business/business-rules.md | BR-109 (line 120, schema-version 0.27.1) | sampling + INFO-observability normative rule (ALREADY amended — see note) |
| docs/adr/0016-context-out-of-band-system-channel.md | Decision / Invariant | delivery mechanism is out of scope; do not touch system-channel wiring |
| app/backend/processors/orchestrator.py | `_sample_file_text` (L71-146), `_detect_document_context` (L322-343), context block (L560-568) | exact edit sites |
| app/backend/processors/libreoffice_helpers.py | `xls_to_xlsx` (L199-211), `is_libreoffice_available` (L72-82) | reused `.xls` conversion seam |
| app/backend/processors/xlsx_processor.py | `translate_xlsx_xls` `.xls` branch (L59-98) | proves the second (processor-side) conversion is per-file and must stay put (AC-7) |
| tests/test_libreoffice_helpers.py | `_FakePopen` (L46-64) | Popen-mock convention; note it writes literal bytes, not a valid `.xlsx` |

> Contract note: BR-109 was ALREADY amended to carry the valid-sample coverage
> and mandatory-INFO-observability requirement (business-rules.md line 120), and
> `schema-version` is ALREADY `0.27.1` (line 6). No further business-rules edit
> is required by this plan. contract-reviewer owns confirming the
> `contracts/CHANGELOG.md` entry exists for the 0.27.0→0.27.1 bump.

## File-Level Plan
| path or glob | action | notes |
|---|---|---|
| app/backend/processors/orchestrator.py | edit | IP-1..IP-6. Imports already present: `is_libreoffice_available`, `xls_to_xlsx` (L31-36), `os` (L6), module `logger` (L51). Add `import tempfile` and use `tempfile.TemporaryDirectory()` for the `.xls` temp `.xlsx` (auto-clean, no `shutil` needed). Keep the outer `try/except` in `_sample_file_text` so any failure still returns `""` (never raises). |
| tests/test_orchestrator_context_detection.py | edit (append) | Add AC-1..AC-8 tests below the existing prior-change tests. Do not modify the existing AC-1..AC-7 (cloud-doc-context-summary) tests — they must stay green. |
| contracts/business/business-rules.md | no change | BR-109 already amended; schema-version already 0.27.1. |
| contracts/CHANGELOG.md | verify only | contract-reviewer confirms the 0.27.1 entry is present. |
| .github/workflows/contract-driven-gates.yml | no change | Per ci-gates.md "Workflow Changes Applied: None". |

## Contract Updates
- API: none.
- CSS/UI: none.
- Env: none (no new vars/flags; `CONTEXT_DETECTION_ENABLED`/`QWEN_CONTEXT_FLOW_ENABLED` unchanged).
- Data shape: none (xlsx phantom-column defect out of scope).
- Business logic: BR-109 already amended (business-rules.md line 120, schema-version 0.27.1). No new edit by this plan; verify CHANGELOG entry only.
- CI/CD: none.

## Decision Record: `.xls` sampling — reuse LibreOffice conversion (CHOSEN) vs. read legacy `.xls` directly

**Decision:** the `.xls` sampling branch reuses the already-shipped
`app/backend/processors/libreoffice_helpers.py:xls_to_xlsx` LibreOffice
conversion into a throwaway temp `.xlsx` (via `tempfile.TemporaryDirectory()`),
reads it with the existing openpyxl row loop, and lets the temp dir auto-delete.
Guard the call with `is_libreoffice_available()`; when it returns False, the
branch returns `""` (no preamble). The existing `_sample_file_text` outer
`try/except` catches any residual failure and returns `""`.

**Rejected alternative — read legacy `.xls` directly via `xlrd`:**
- Adds a runtime dependency. `xlrd` is NOT installed in the `translate-tool`
  env; adding it (plus wiring into `requirements.txt`/`environment.yml`) is a
  larger footprint than reusing a shipped, already-tested helper.
- Contradicts the test strategy this change is built on. test-plan.md and
  ci-gates.md mock the LibreOffice boundary at `subprocess.Popen`; the AC-1/AC-7/
  AC-8 integration tests exercise the sampler with a faked process boundary and
  need NO real `soffice` binary. An `xlrd` path invokes no subprocess, so it
  could not be exercised by those tests and would force both a real `.xls`
  binary fixture and an `xlrd` CI dependency.
- Self-containment is a weak benefit here: the reuse path is already
  self-degrading (`is_libreoffice_available()` guard) and already covered by the
  Popen-mock convention.

**Graceful degradation (AC-6):** LibreOffice absent → guard returns `""` before
any conversion; conversion raising → caught by the outer `try/except` → `""`.
A `.xls` sample never raises into the job pipeline.

**Temp-file lifetime:** owned entirely inside the `.xls` branch via
`tempfile.TemporaryDirectory()`; nothing leaks and nothing is shared with the
processor-side conversion.

**Fixture question (resolved — NO new binary, NO `xlwt`):** because the AC-1/
AC-7/AC-8 tests mock `subprocess.Popen`, the `.xls` INPUT file in those tests is
a dummy (its bytes are never read — LibreOffice is mocked). The distinctive
token must live in the CONVERSION OUTPUT: the test's Popen fake must write a
GENUINE openpyxl-authored `.xlsx` (carrying e.g. `"PANJIT-XLS-TOKEN-771"`) at
the `--outdir/<stem>.xlsx` path the sampler then reads. The stock
`tests/test_libreoffice_helpers.py::_FakePopen` writes literal
`b"converted-bytes"`, which openpyxl CANNOT open — so a local fake that writes a
real `.xlsx` is required (do NOT reuse `_FakePopen` verbatim for the sampler
tests). No committed binary `.xls` and no `xlwt` test dependency are needed.
The AC-2 (`.docx` table) and AC-3 (`.pptx` table) fixtures are generated at test
time via `python-docx add_table` / `python-pptx add_table` with distinctive
tokens (test-plan.md Fixtures Required).

## Test Execution Plan
| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 (unit) | tests/test_orchestrator_context_detection.py::test_sample_file_text_reads_legacy_xls_via_conversion | sample contains the distinctive xls token (via mocked-Popen conversion) |
| AC-1 (integration) | tests/test_orchestrator_context_detection.py::test_process_files_context_detected_for_legacy_xls | `[CONTEXT] Detected:` emitted; job `stopped is False` |
| AC-2 | tests/test_orchestrator_context_detection.py::test_sample_file_text_docx_table_only_includes_cell_text | sample contains the table-cell token, not merely non-empty |
| AC-3 | tests/test_orchestrator_context_detection.py::test_sample_file_text_pptx_table_includes_cell_text | sample contains the table-cell token |
| AC-4 | tests/test_orchestrator_context_detection.py::test_detect_document_context_logs_info_reason_on_exception | INFO record with reason via `caplog.at_level(logging.INFO)` |
| AC-4 | tests/test_orchestrator_context_detection.py::test_process_files_logs_info_reason_when_sample_empty | INFO skip line when sample empty and flags on |
| AC-5 | tests/test_orchestrator_context_detection.py::test_detect_document_context_logs_info_on_success | `[CONTEXT] Detected:` INFO record via caplog (module logger, not patched `.info`) |
| AC-6 | tests/test_orchestrator_context_detection.py::test_sampling_exception_degrades_to_no_preamble_job_completes | job completes `stopped is False`, no `Document context:` preamble reaches outgoing request |
| AC-7 | tests/test_orchestrator_context_detection.py::test_xls_sampling_does_not_double_convert_via_libreoffice | with `translate_xlsx_xls` stubbed, `subprocess.Popen` called exactly once per `.xls` (sampler side) |
| AC-8 | tests/test_orchestrator_context_detection.py::test_legacy_xls_and_table_only_docx_both_emit_context_detected | both files emit `[CONTEXT] Detected:` |

Required phases (test-plan.md Test Execution Ladder; floor = collect, targeted,
changed-area): implementation agents generate evidence with `cdd-kit test run`;
the gate validates `test-evidence.yml`. changed-area scope:
`tests/test_orchestrator_context_detection.py` (add
`tests/test_libreoffice_helpers.py` only if a new reuse helper lands there).
Do NOT widen to `test_pdf_*`/QE files (CLAUDE.md env-artifact learnings).
The binding CI check is `contract-and-fast-tests` (`pytest tests/ -x -q`),
which runs AC-1..AC-8 unconditionally via the mocked-Popen boundary
(ci-gates.md Risk Analysis).

## Handoff Constraints
- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full BR-109, ADR-0016, test strategy, or CI policy prose into
  code or comments; follow the source pointers above.
- All new tests must fail RED against current `orchestrator.py` (empty-string
  sampler branches, `logger.debug`-only swallow) before the fix lands
  (test-plan.md Notes).
- INFO logs for AC-4/AC-5 must go through the module logger
  `logging.getLogger(__name__)` so `caplog` captures them; keep the existing
  `log(...)` callback for translator.log continuity — add, don't replace.
- Keep implementation within the file-level plan unless a Context Expansion
  Request is approved.
- If this plan omits a required file, behavior, contract, or test, stop and
  report `blocked`.

## Known Risks
- **AC-7 wording vs. production reality (flagged):** AC-7 says the `.xls`
  sampling path "does not double-convert". In PRODUCTION a `.xls` is converted
  TWICE per run — once by the sampler (this change) and once by the unchanged
  `xlsx_processor.translate_xlsx_xls` (L59-98). Fully sharing one conversion
  across the sampler→processor boundary would change the processor's per-file
  conversion timing, which AC-7's own second clause and the change-request
  constraint explicitly forbid. The AC-7 test's operational definition is
  therefore narrower: with `translate_xlsx_xls` stubbed, the SAMPLER must invoke
  LibreOffice exactly once (not twice) per `.xls`. This plan satisfies that and
  accepts the residual second production conversion as a bounded, cheap cost
  (sampling reads only `CONTEXT_SAMPLE_CHARS`). Eliminating it (shared/cached
  conversion) is a separate future refactor, out of scope here.
- The sampler-test Popen fake must write a REAL openpyxl `.xlsx` at the
  converted-output path; reusing `_FakePopen` (literal `b"converted-bytes"`)
  verbatim will make the sampler's `openpyxl.load_workbook` fail and the AC-1
  assertion misleadingly pass/fail. Called out in the Decision Record.
- python-pptx: a table lives on a GraphicFrame shape; use
  `getattr(shape, "has_text_frame", False)` and `getattr(shape, "has_table",
  False)` as independent branches (a shape is not both) so neither raises on the
  other shape kind. Confirmed against `parsers/pptx_parser.py` (uses
  `hasattr(shape, "table")` then `shape.table.rows`/`row.cells`/`cell.text`).
- `.docx` `doc.tables` yields only top-level tables (not nested); sufficient for
  sampling but note it if a future doc nests text solely in nested tables.
