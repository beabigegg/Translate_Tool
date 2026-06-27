---
change-id: office-output-mode
schema-version: 0.1.0
last-changed: 2026-06-27
---

# Implementation Plan: office-output-mode

## Objective
Expand `output_mode` from a 2-value DOCX/PPTX knob into per-format output semantics across DOCX, XLSX, and PPTX. Add a DOCX-only `bilingual` (two-column table) mode, give XLSX an `output_mode` (`adjacent`/`annotation`/`replace`) for the first time, and add the missing `replace` write-back branches for DOCX SDT/table-cell/text-box and PPTX SmartArt. No new endpoint. All changes are write-back-step only; extraction is untouched. Default stays `append` so existing callers are unaffected (AC-8).

## Execution Scope

### In Scope
- `app/backend/api/schemas.py` — add `BILINGUAL = "bilingual"` to `OutputMode`.
- `app/backend/processors/orchestrator.py` — degrade `bilingual`→`append` for non-DOCX per file; thread `output_mode` into the `translate_xlsx_xls` call.
- `app/backend/processors/docx_processor.py` — add `replace` branches to SDT / para-in-cell / text-box; add new `bilingual` dual-column path for body paragraphs.
- `app/backend/processors/xlsx_processor.py` — add `output_mode` param; branch write block into `adjacent`/`annotation`/`replace`.
- `app/backend/processors/pptx_processor.py` — thread `output_mode` into SmartArt and add `replace` branch.
- `contracts/api/api-contract.md` + `openapi.yml`/`openapi.json` regen; `contracts/data/data-shape-contract.md`.
- Run the three planned test files (authored by test-strategist): `tests/test_output_mode_processors.py`, `tests/test_output_mode_orchestrator.py`, `tests/test_output_mode_api.py`.

### Out of Scope
- Element extraction logic (segment building is identical across modes).
- Any new endpoint, request field beyond the enum value, or feature flag (the enum value itself is the gate).
- Frontend changes (no UI surface — see classification Tasks Not Applicable).
- Refactoring existing append/replace code beyond adding the new branches.
- `libreoffice_helpers.py` (CER-001 stays unapproved; the XLSX write path uses openpyxl directly — confirmed at `xlsx_processor.py:264-281`).

## Required Changes
| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | api/schemas.py | Add `BILINGUAL = "bilingual"` to `OutputMode` enum | backend-engineer |
| IP-2 | orchestrator | Degrade `bilingual`→`append` for non-DOCX per file + emit job warning; thread `output_mode` into xlsx call | backend-engineer |
| IP-3 | docx_processor | Add `replace` branches (SDT, para-in-cell, text box); add `bilingual` dual-column path for body paras | backend-engineer |
| IP-4 | xlsx_processor | Add `output_mode` param; branch write block into adjacent/annotation/replace | backend-engineer |
| IP-5 | pptx_processor | Thread `output_mode` into SmartArt; add `replace` branch | backend-engineer |
| IP-6 | contracts | Update API enum, data-shape contract; regen openapi | backend-engineer |
| IP-7 | tests | Run targeted/changed-area/contract/full ladder against the three test files | backend-engineer |

## Source Artifact Pointers
| source | relevant pointer | used for |
|---|---|---|
| design.md | Key Decisions (bilingual two-column table; cross-format degrade; XLSX adjacent block-shift; annotation non-destructive Comment) | implementation constraints |
| design.md | Affected Components table | per-file line ranges |
| change-classification.md | Inferred Acceptance Criteria AC-1..AC-8 | acceptance mapping |
| change-classification.md | Required Contracts / Required Tests | contract + test family scope |
| context-manifest.md | Allowed Paths | read/write boundary |
| test-plan.md | AC→test mapping + ladder | tests to run (currently scaffold — see Known Risks) |

## File-Level Plan
Implement in this order; each step is independently testable.

| # | path | line / function | action |
|---|---|---|---|
| 1 | `app/backend/api/schemas.py` | `OutputMode` enum, lines 11-13 | Add `BILINGUAL = "bilingual"` after `REPLACE`. |
| 2 | `app/backend/processors/orchestrator.py` | `effective_output_mode`, lines 398-400 | After the BR-67 multi-target clamp, add a per-file degrade: when mode is `bilingual` and the file ext is not `.docx`, use `append` for that file and append a notice to the job `warnings` field (same mechanism PDF renderer fallback uses). Keep `effective_output_mode` as the single chokepoint. |
| 3 | `app/backend/processors/docx_processor.py` | SDT branch, lines 383-406 | Add a `replace` branch: overwrite the SDT content paragraph run text in-place instead of appending a new `<w:p>`. Mirror the body-para replace pattern at lines 464-475 (first run = translation, clear remaining runs). |
| 4 | `app/backend/processors/docx_processor.py` | para-in-cell branch, lines 408-461 | Add a `replace` branch: overwrite the cell paragraph runs in-place instead of inserting `to_add` paragraphs after it. |
| 5 | `app/backend/processors/docx_processor.py` | body-para else branch, lines 462-508 (replace already at 464-475) | Add a `bilingual` branch: relocate the source paragraph's `<w:p>` into col-A of a new one-row, two-column `<w:tbl>`, write the translation into col-B (per design ADR-0007). Non-paragraph blocks (tables/images/text boxes/headers-footers/SDT-wrapped) are NOT wrapped — pass through with existing append/replace handling. |
| 6 | `app/backend/processors/docx_processor.py` | txbx branch, lines 509-531 | Add a `replace` branch: overwrite the text-box paragraph text in-place instead of `_txbx_append_paragraph`. |
| 7 | `app/backend/processors/xlsx_processor.py` | signature, lines 40-57 | Add `output_mode: str = "append"` parameter. |
| 8 | `app/backend/processors/xlsx_processor.py` | write block, lines 263-279 | Branch on `output_mode`: `adjacent` → write translation to column `c + original_max_column` (compute width from the true used range, not cached; source cell + width unchanged, no `wrap_text`); `annotation` → openpyxl `Comment` (reuse the existing import; idempotent like line 259; append below a pre-existing non-translation comment rather than clobber); `replace` → overwrite cell value with translation only, no `"src\n譯文"` stack, no `wrap_text`; default/`append` → keep current combined-stack behaviour. |
| 9 | `app/backend/processors/orchestrator.py` | xlsx call site, lines 760-774 | Add `output_mode=effective_output_mode,` to the `translate_xlsx_xls(...)` call (currently absent). |
| 10 | `app/backend/processors/pptx_processor.py` | `_update_smartart_texts`, lines 121-179 (line 162 hard-coded `f"{text}\n({translated})"`) | Add an `output_mode` param; in `replace` mode set `t_elem.text = translated` instead of the appended parenthetical. |
| 11 | `app/backend/processors/pptx_processor.py` | SmartArt call site, line 458 | Pass `output_mode` through to `_update_smartart_texts`. (`translate_pptx` already accepts `output_mode`, line 196.) |

## Contract Updates
- API: `contracts/api/api-contract.md:316` — add `bilingual` to the `output_mode` enum description (note: DOCX-only; degrades to `append` on non-DOCX). Keep `append`/`replace` valid; unknown values still rejected.
- Data shape: `contracts/data/data-shape-contract.md` — document per-format `output_mode` output structure: DOCX dual-column table (source col-A / translation col-B, one row per body paragraph; multi-target = one translation column per target, no clamp); XLSX `adjacent` (block-shift by original sheet width, source unchanged, no wrap), `annotation` (non-destructive Comment), `replace` (overwrite, no wrap / no row-height inflation); PPTX SmartArt `replace`.
- CSS/UI: none.
- Env: none.
- Business logic: none new.
- CI/CD: none.
- After contract + schema edits: run `cdd-kit openapi export --out contracts/api/openapi.yml` and commit the regenerated `openapi.yml` (+ `openapi.json`) — the CI `openapi export --check` gate fails on stale output (promoted learning).

## Test Execution Plan
Test files are authored by test-strategist; backend-engineer runs them and generates `test-evidence.yml` via `cdd-kit test run`. Required floor: collect, targeted, changed-area; add contract (api-only + data-shape change) and full. Full ladder in test-plan.md / references/sdd-tdd-policy.md.

| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 | tests/test_output_mode_api.py | `bilingual` accepted by `OutputMode`; `append`/`replace` still valid; unknown rejected; openapi reflects enum |
| AC-2 | tests/test_output_mode_processors.py | DOCX `bilingual`: source and translation occupy distinct table cells (structural assert), not concatenated |
| AC-3 | tests/test_output_mode_processors.py | XLSX `adjacent`: translation in shifted column; source value + width unchanged; no wrap_text |
| AC-4 | tests/test_output_mode_processors.py | XLSX `annotation`: translation in cell comment; source value unchanged |
| AC-5 | tests/test_output_mode_processors.py | XLSX `replace`: cell overwritten; no `src\n譯文` stack; no wrap_text |
| AC-6 | tests/test_output_mode_processors.py | DOCX cell/SDT/text-box `replace`: translation replaces source |
| AC-7 | tests/test_output_mode_processors.py | PPTX SmartArt `replace`: translation replaces source |
| AC-8 | tests/test_output_mode_orchestrator.py | default `append` + existing `replace` unchanged; non-DOCX `bilingual` degrades to `append` with warning |

## Handoff Constraints
- Worktree: ALL implementation happens in `.claude/worktrees/office-output-mode/` on branch `feat/office-output-mode`. Do not edit the main checkout.
- Implementation agents must not infer missing requirements from chat history; follow this plan and the source pointers.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above. Never edit `design.md`.
- Keep implementation within the file-level plan; if a required path is missing, file a Context Expansion Request and stop.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.

## Known Risks
- `test-plan.md` and `ci-gates.md` are still template scaffolds (not yet authored). The AC→test mapping and test-file list here are derived from `change-classification.md` Inferred Acceptance Criteria and `design.md`. test-strategist must populate `test-plan.md` (and confirm the test-file names) before the gate; if it diverges from this table, the test-plan is authoritative.
- Bilingual `<w:p>` relocation: paragraphs inside existing tables, headers/footers, multi-column sections, and SDT-wrapped content must be explicitly passed through (not wrapped) — confirm the block taxonomy during implementation; tests must prove distinct cells (AC-2, design Open Risks).
- XLSX `adjacent` block-shift can collide if the sheet has populated columns beyond `max_column` (sparse/merged regions) — compute width from the true used range, not a cached value (design Open Risk).
- XLSX `annotation` must not clobber author comments — append below pre-existing non-translation comments; idempotency mirrors `xlsx_processor.py:259`.
- Multi-target + `bilingual`: no in-place ambiguity, so do NOT clamp like `replace`; one translation column per target. Confirm the shape in the data-shape contract before implementation.
