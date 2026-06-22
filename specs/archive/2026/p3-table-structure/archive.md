# Archive: p3-table-structure

## Change Summary

Added an optional ML table-structure recognizer (`parsers/table_recognizer.py`, targeting TableFormer/TATR ONNX) that decomposes PDF `table`-typed regions into a row/col/cell `TableStructure` and attaches it to `TranslatableElement.metadata["table_structure"]`. A new cell-batch seam (`translation_service.translate_table_cells()`) translates each table's text-bearing cells in exactly one coalesced LLM call (BR-69), passes numeric/empty cells through unchanged (BR-68), and reconstructs the parent element's `translated_content` as tab/newline-delimited text (D3). The recognizer follows the ADR 0003 lazy-load + fail-soft pattern: missing weights or runtime → WARNING logged once, no `TableStructure` attached, region falls back to existing flatten path (BR-71). Feature is gated off by default (`TABLE_RECOGNITION_ENABLED=false`). No wire-schema change to `TranslatableElement`; no data migration; PDF-only scope.

## Final Behavior

- When `TABLE_RECOGNITION_ENABLED=true` and model weights are available: PDF `table`-typed regions are decomposed into `TableStructure`; each table is translated in one coalesced LLM call; numeric/empty cells are passed through unchanged; structured table elements are never used as chunker split-boundary targets.
- When disabled or weights missing: fail-soft — table region treated as a plain `table` element; existing flatten path applies; no user-visible change.
- `TableRecognizer._parse_outputs()` is currently a structural placeholder — real TATR ONNX output decoding requires validated model weights (documented in design.md §Open Risks and qa-report.md §APPROVED_WITH_RISK).

## Final Contracts Updated

| contract | version change | what changed |
|---|---|---|
| `contracts/data/data-shape-contract.md` | 0.10.0 → 0.11.0 | `TableCell`/`TableStructure` dataclass shapes; `table_recognizer.py` as producer; cell-batch IR-consumption contract; degenerate table handling table; backward-compat rule; Known consumers table |
| `contracts/business/business-rules.md` | 0.16.0 → 0.17.0 | BR-68 (numeric passthrough), BR-69 (same-table batching), BR-70 (cell-granularity translation), BR-71 (graceful degradation); Table T (11-row decision table) |

Evidence: `agent-log/backend-engineer.yml` → contracts-touched (pre-updated before implementation agent ran); gate passed `cdd-kit validate --contracts`.

## Final Tests Added / Updated

| file | count | families |
|---|---|---|
| `tests/test_table_recognizer.py` | 23 new | unit, contract, integration, data-boundary |

Anti-tautology: AC-3 asserts `numeric.translated_content == "1,234.56"` AND `translation_status == "passthrough"`; AC-4 inspects `call_args[0][0]` batch texts (WHICH cells, not just call count); AC-2 calls `translate_table_cells()` directly (not through `translate_document()`). All 23 pass in conda env; full suite 755 passed.

Evidence: `agent-log/backend-engineer.yml` → test-output.

## Final CI/CD Gates

| gate | tier | where |
|---|---|---|
| `cdd-kit gate p3-table-structure` | 1 | contract-and-fast-tests job |
| `pytest tests/test_table_recognizer.py -x -q --tb=short` | 1 | contract-and-fast-tests job (new step) |
| `cdd-kit validate --contracts` | 1 | existing |
| `cdd-kit openapi export --check` | 1 | existing |
| `pytest tests/ -x -q --tb=short` (full suite) | 1 | existing |
| `full-regression` | 2 | pull_request |
| `layout-detector-dependency-gate` | 2 | pull_request |

Evidence: `ci-gates.md`; `agent-log/ci-cd-gatekeeper.yml`.

## Production Reality Findings

- **_parse_outputs() placeholder**: `TableRecognizer._parse_outputs()` returns a degenerate `TableStructure` for all inputs until real TATR ONNX output format is validated with actual weights. QA approved with risk; feature gated off by default. QA evidence: `qa-report.md` note `APPROVED_WITH_RISK`.
- **D3 reconstruction lossy**: Tab/newline D3 reconstruction is lossy for cells containing literal tabs/newlines. Authoritative per-cell text remains in `TableStructure.cells`; renderers must consume cells directly for coordinate placement. Documented in design.md §Open Risks.
- **Pre-existing failures (22 tests)**: onnxruntime/fitz/fastapi missing from CI test env; confirmed via `git stash` baseline before any code was written. Out of scope; owner: platform-team. Evidence: `qa-report.md` §Pre-existing Failures; `agent-log/backend-engineer.yml` §pre-existing-failures.
- **CER-001 rejected**: DOCX/PPTX in-scope request rejected by spec-architect; PDF-only confirmed. Deferred to future change.

## Lessons Promoted to Standards

None. All durable behavior is captured in the contract updates above (BR-68..BR-71, TableCell/TableStructure IR in data-shape-contract.md). No new agent-workflow patterns requiring CLAUDE.md guidance — the lazy-load/fail-soft pattern is already documented in ADR 0003.

## Follow-up Work

- **Real TATR output decoding**: Implement `TableRecognizer._parse_outputs()` with the actual ONNX model output format once weights are validated; remove placeholder; set `TABLE_RECOGNITION_ENABLED=true` in production config.
- **PDF table renderer**: If a PDF-table re-renderer is added later, it must consume `TableStructure.cells` directly for coordinate placement (not the D3 tab/newline reconstruction string).
- **DOCX/PPTX table unification** (CER-001 deferred): native table structure in DOCX/PPTX could be unified into `TableStructure` IR in a future change.
- **Test env onnxruntime**: Platform-team to install onnxruntime + fitz + real PDF fixtures in CI test env to un-block 22 pre-existing failures.

## Cold Data Warning

This archive is historical evidence. Current requirements live in `contracts/` and active project guidance.
