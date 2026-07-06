# Archive: table-context-translation

## Change Summary
Replaced per-cell/per-paragraph independent translation for DOCX/XLSX/PPTX tables with whole-table context translation: each table is serialized once into a Markdown pipe-grid, translated as a single LLM call, then parsed back and remapped into cells/paragraphs. This gives the model full-table context (headers, row/column relationships) instead of translating isolated cell strings, improving terminology and structural consistency across a table. Shipped via PR #7 (merged 2026-06-27) and a follow-up fix via PR #11 (merged 2026-07-04, CJK layout-faithful rendering + whole-table context translation refinements).

## Final Behavior
- `app/backend/utils/table_serializer.py` (new): `serialize()`/`parse()` round-trip a table to/from a Markdown pipe-grid string.
- `OllamaClient`/`OpenAICompatibleClient._build_table_translate_prompt()`: constructs the whole-table translation prompt.
- `translation_service.translate_table_cells()`: serialize → `translate_once()` → parse, one LLM call per table.
- DOCX/XLSX/PPTX processors group cells per table and call `translate_table_cells()` instead of per-cell/per-paragraph translation; the cell/paragraph dedup key is now `(tgt, text, col)` for cells and `(tgt, text, None)` for paragraphs (BR-83).
- Fallback: any exception unpacking `translate_once()`'s result (network error, parse mismatch, model error) falls back to per-cell batch translation (BR-82) rather than applying BR-25 placeholders — strictly safer than the original plan, since every failure mode still produces a real translation.
- 1-column tables and PDF tables are exempt from whole-table serialization (serializer produces no pipe characters for 1-column tables, so `parse()` returns `None` and the per-cell fallback always runs; PDF's `TableCell` IR path is exempt per BR-83 design decision).

## Final Contracts Updated
- `contracts/business/business-rules.md`: BR-79–BR-83 (Rule Inventory) + Table T (decision table) — v0.19.0 → v0.20.0
- `contracts/data/data-shape-contract.md`: §Table Serialization Wire Format, §Office Processor Cell Dedup Key — v0.13.0 → v0.14.0
- No API/env contract change (AC-7 — verified by `cdd-kit openapi export --check`)

## Final Tests Added / Updated
- `tests/test_table_serialization.py` (new, 17 tests — unit: serialize/parse round-trip, pipe-escape, delimiter collision)
- `tests/test_table_context_translation.py` (new, 15 tests — unit + integration: per-format processor wiring, fallback path)
- `tests/test_translation_service.py` (+3 tests — `translate_table_cells()` non-regression)
- Full suite at close: 571 passed, 3 skipped, 0 failed (changed-area); full-phase run in test-evidence.yml: `final-status: passed`

## Final CI/CD Gates
- No new dedicated gate/job added. A per-change targeted-test step ("Targeted tests — table_serialization + table_context_translation") was added to the `contract-and-fast-tests` job for fast-fail; removed from the workflow as part of this close (per-change targeted steps are removed at archive time — CLAUDE.md promoted learning).
- Tier 2 required gates (golden-sample-regression, layout-detector-dependency-gate, renderer-equivalence, text-expansion-benchmark) applied unchanged.

## Production Reality Findings
- qa-reviewer found one blocker during review — BR-79..BR-83 contract additions were not yet committed to the feature branch — resolved by committing them before merge.
- A pre-existing PR-scope meta-guard test (`test_no_app_backend_files_modified`, a Wave 1 leftover) was removed as structurally incompatible with any backend-touching PR; not specific to this change's design.
- Two accepted design deviations, both judged safe by qa-reviewer: (1) 1-column tables always fall back to per-cell translation (no pipe grid possible) — correct behavior, just means such tables don't benefit from whole-table context; (2) the `translate_once()` exception path falls back to per-cell batch rather than BR-25 placeholders — strictly better (still produces real output on any failure).
- Follow-up PR #11 (merged 2026-07-04) revisited whole-table context translation together with CJK layout-faithful rendering fixes, suggesting the initial table-context integration surfaced secondary layout issues that were addressed in a later, separate change.

## Lessons Promoted to Standards
- **promote-to-guidance** (CLAUDE.md, `cdd-kit:learnings` region, replacing the existing bullet in place — net growth ≈ 0): strengthened the existing "/cdd-close removes archived changes' CI steps" rule to require sweeping the ENTIRE `.github/workflows/contract-driven-gates.yml` against the full archived-changes list, not just the change currently being closed. Evidence: this close-out found the `table_serialization + table_context_translation` step still present (now removed) plus two OTHER already-archived changes' stale targeted-test steps (`table_recognizer` for p3-table-structure, `quality_judge+co.` for p3-llm-judge) that survived their own close-outs undetected — reviewed and confirmed by contract-reviewer (agent-log evidence path: this session's contract-reviewer invocation, not a separate agent-log file since this is a close-time-only review).
- A candidate process lesson ("verify archival via `cdd-kit list`, not commit-message text") was evaluated and **rejected** (do-not-promote) — contract-reviewer judged the existing `/cdd-close` Step 4 already mandates this verification; the root cause was a prior session not executing the documented step, not a documentation gap. Not added to avoid duplicating existing guidance.

## Follow-up Work
- DOCX multi-paragraph cells: `translate_table_cells()` joins all paragraph text within a cell into one segment; the single concatenated translation is inserted back, so multi-paragraph layout within a cell is not preserved. No tracked follow-up change exists for this as of archival — noted here for future reference.
- The CI workflow (`.github/workflows/contract-driven-gates.yml`) still carries stale per-change targeted-test steps for other already-archived changes (`table_recognizer` for p3-table-structure, `quality_judge`+co. for p3-llm-judge) that were never cleaned up at their own close time — out of scope for this archival, flagged for a separate housekeeping pass.

## Cold Data Warning
This archive is historical evidence. Current requirements live in `contracts/` and active project guidance (`CLAUDE.md`/`CODEX.md`).
