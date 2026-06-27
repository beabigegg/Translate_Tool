---
change-id: table-context-translation
schema-version: 0.1.0
last-changed: 2026-06-27
---

# Implementation Plan: table-context-translation

## Objective
Stop translating table cells as isolated, position-stripped strings. Each recognized table is serialized once to a Markdown pipe-grid, wrapped with an instruction-before-grid prompt, sent as a single LLM call, and remapped onto cells by `(row,col)`. Serialization/remap live in one shared utility used by Ollama, OpenAI-compatible, and the PDF path. Office processors gain a `(tgt, src_text, col)` dedup key. No API, env, or IR-schema change.

## Execution Scope

### In Scope
- New shared utility `app/backend/utils/table_serializer.py` (`serialize`, `parse`).
- `_build_table_translate_prompt` mirrored in `ollama_client.py` and `openai_compatible_client.py`.
- PDF `TableCell` cell-batch path in `translation_service.py` (~:614) switched to serialize→one-call→parse with per-cell SEG fallback.
- Per-table cell grouping + `(tgt, src_text, col)` dedup key (build + restore passes) in `docx_processor.py`, `xlsx_processor.py`, `pptx_processor.py`.
- New tests `tests/test_table_serialization.py`, `tests/test_table_context_translation.py`; non-regression assertions in `tests/test_translation_service.py`.

### Out of Scope
- TATR `_parse_outputs()` (shipped Wave 1), `output_mode` table interaction (Track F), PDF rendering refactor (Track G), quality evaluator / critique loop.
- Any API endpoint add/rename/reshape (AC-7). Any IR schema change — NO `is_header` field; header detection is positional (row 0 / col 0).
- Do NOT apply the `(tgt, src_text, col)` flat-dedup key to the PDF path (BR-83); PDF cells stay position-unique inside `TableStructure`.
- No refactors beyond the file-level plan below.

## Required Changes
| id | area | required action | owner agent |
|---|---|---|---|
| IP-0 | tests | Write failing tests in test_table_serialization.py + test_table_context_translation.py FIRST (TDD) | backend-engineer |
| IP-1 | utils | Create `app/backend/utils/table_serializer.py`: `serialize(cells)->str`, `parse(text,num_rows,num_cols)->Optional[list[list[str]]]` | backend-engineer |
| IP-2 | clients | Add `_build_table_translate_prompt(serialized_table, src_lang, tgt_lang)` to ollama_client.py; mirror identically in openai_compatible_client.py | backend-engineer |
| IP-3 | services | PDF cell-batch path (~:614): serialize→single call→parse; on None fall back to existing per-cell SEG batch | backend-engineer |
| IP-4 | processors | docx/xlsx/pptx: group cells per native table; change tmap/dedup key to `(tgt, src_text, col)` for cells, `(tgt, src_text, None)` for non-table; apply to build AND restore | backend-engineer |

## Source Artifact Pointers
| source | relevant pointer | used for |
|---|---|---|
| design.md | §Key Decisions Q1–Q6, §Remap Contract, §Open Risks | serialization format, strict remap, dedup semantics, gotchas |
| contracts/business/business-rules.md | BR-79..BR-83, Table T rows (`:323`,`:331`,`:334`-`:336`) | normative behavior |
| contracts/data/data-shape-contract.md | §Table Serialization Wire Format (`:414`), §Office Processor Cell Dedup Key (`:448`) | serialize/parse rules, key schema |
| test-plan.md | AC→test mapping table; Notes (collection-time `patch.object`, new test_translation_service.py) | tests to write/run |
| ci-gates.md | Required Gates table | verification commands |

## File-Level Plan
| path | action | notes |
|---|---|---|
| `app/backend/utils/table_serializer.py` | create | `serialize`: cells→`num_rows×num_cols` grid; escape `|`→`\|`, `\n`→space; numeric/empty kept as positional placeholders (data-shape §Serialization). `parse`: strip `---` lines, keep `|`-lines, split on unescaped `|`, unescape, trim; accept iff `len==num_rows` AND every row `==num_cols`, else return `None` (data-shape §Parse). |
| `app/backend/clients/ollama_client.py` (~625) | edit | Add `_build_table_translate_prompt`: instruction string BEFORE grid (BR-80). Call it from the table batch path instead of the flat-list builder. |
| `app/backend/clients/openai_compatible_client.py` (~193) | edit | Mirror `_build_table_translate_prompt` with identical wording (AC-2/BR-80). |
| `app/backend/services/translation_service.py` (540–660, esp. :614) | edit | Replace `batch_texts=[c.content ...]` with serialize(`TableStructure.cells`)→single LLM call→`parse(resp,num_rows,num_cols)`. On grid: assign `grid[r][c]`→`translated_content`, status `translated`; numeric→`passthrough`, empty→`skipped`. On `None`: WARNING + fall back to existing per-cell SEG batch (BR-82/BR-83). |
| `app/backend/processors/docx_processor.py` (239–244, 584–589, restore) | edit | Materialize per-`Tbl(r,c)` cell groups separate from paragraph stream; tmap/dedup key `(tgt, src_text, col)` for cells, `(tgt, src_text, None)` for paragraphs; apply in build AND `_insert_*translations`. |
| `app/backend/processors/xlsx_processor.py` (120–139) | edit | Per-table (sheet row/col region) grouping; same key change build+restore. |
| `app/backend/processors/pptx_processor.py` (258–262) | edit | Per-table grouping; same key change build+restore. |
| `tests/test_table_serialization.py` | create | serialize/parse unit + round-trip + shape-mismatch (None) cases per test-plan. |
| `tests/test_table_context_translation.py` | create | one-call-per-table, dedup-by-col, fallback, PDF row/col, numeric passthrough per test-plan. |
| `tests/test_translation_service.py` | create/extend | non-table path AC-6 (`col=None`) called directly, not via `translate_document()`. |

## Contract Updates
- API: none (AC-7 — `openapi-sync` gate must show no change).
- CSS/UI: none.
- Env: none (`TABLE_RECOGNITION_ENABLED` already exists).
- Data shape: already authored — §Table Serialization Wire Format, §Office Processor Cell Dedup Key. Implement to match; do not re-edit.
- Business logic: BR-79..BR-83, Table T already authored. Implement to match; do not re-edit.
- CI/CD: none (targeted step already added to workflow per ci-gates.md).

## Test Execution Plan
| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 one-call-per-table | tests/test_table_context_translation.py | exactly one LLM call per table; all-numeric → zero calls |
| AC-2 instruction before grid | tests/test_table_context_translation.py::test_instruction_precedes_serialized_grid_in_prompt | instruction index < grid index |
| AC-3 per-column dedup | tests/test_table_context_translation.py::test_same_text_different_cols_get_separate_translations | independent translations per col |
| AC-4 header inline | tests/test_table_serialization.py::test_serialized_grid_row0_and_col0_inline_with_body | row0/col0 present in grid string |
| AC-5 PDF row/col drives serialization | tests/test_table_context_translation.py::test_pdf_tablecell_row_col_drives_serialization | serialize fed by TableCell row/col |
| AC-6 non-table unaffected | tests/test_translation_service.py | paragraph path + `col=None` key unchanged |
| AC-8 mismatch → None / fallback | tests/test_table_serialization.py + tests/test_table_context_translation.py | parse None on row/col/no-pipe; per-cell SEG fallback preserves 1:1 mapping |

Test phases (floor): `collect`, `targeted`, `changed-area`; plus `contract` (BR/data-shape) and `full` (AC-6 regression). Generate evidence with `cdd-kit test run`; gate commands per ci-gates.md: `cdd-kit validate --contracts`, `cdd-kit openapi export --check`, targeted `pytest tests/test_table_serialization.py tests/test_table_context_translation.py -x -q --tb=short`, full `pytest tests/ -x -q`.

## Handoff Constraints
- Stay inside `context-manifest.md` Allowed Paths (note: real new-utility module dir is `app/backend/utils/`, now allowed; `services/translation_helpers.py` does NOT exist — helpers live at `app/backend/utils/translation_helpers.py`).
- Do not infer missing requirements from chat history; do not re-copy design/contract/CI prose into this plan; follow the source pointers above.
- All LLM mocks target the client boundary (`ollama_client`/`openai_compatible_client`) via collection-time `patch.object` (CLAUDE.md tautology rule); test PDF path directly, not via `translate_document()`.
- If a required file, behavior, contract, or test is missing here, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved.

## Known Risks
- Office grouping is structural (largest blast radius): table cells currently flatten into the paragraph dedup stream; per-table `(row,col)` grouping must not alter non-table paragraph behavior (regression-report.md required). Apply the key change symmetrically in build AND restore or cells fail to remap.
- Delimiter/escape collision: cells containing `|` or multi-line text rely on escaping; an LLM that normalizes escapes trips strict shape check → safe fallback but loses whole-table context for that table.
- Positional header heuristic mislabels headerless/transposed tables — accepted, in scope.
- Line numbers above are from design.md and may drift after the last code-map refresh — locate seams by symbol, not raw line.
