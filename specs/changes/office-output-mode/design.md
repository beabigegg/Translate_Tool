# Design: office-output-mode

## Summary
Wave 3 Track F expands the existing `output_mode` field from a 2-value DOCX/PPTX knob
into per-format output semantics across all three Office processors, without adding any
endpoint. A new enum value `bilingual` (DOCX only) emits a two-column source/translation
table. XLSX gains the field for the first time with three modes (`adjacent`, `annotation`,
`replace`), replacing the hard-coded `"src\n譯文"+wrap_text` stack that inflates row height.
DOCX SDT / table-cell / text-box and PPTX SmartArt gain the missing `replace` write-back
branch. The orchestrator stays the single routing chokepoint: it already clamps multi-target
`replace`→`append` (BR-67) and now also degrades `bilingual`→`append` per-file for non-DOCX
formats, mirroring that pattern. All changes are write-back-step only; element extraction is
untouched.

## Affected Components
| component | file path(s) | nature of change |
|---|---|---|
| OutputMode enum | `app/backend/api/schemas.py:11-13` | add `BILINGUAL = "bilingual"` value |
| Orchestrator routing | `app/backend/processors/orchestrator.py:398-400, 760-774` | degrade `bilingual`→`append` for non-DOCX (per-file); thread `output_mode` into the `translate_xlsx_xls` call (currently absent) |
| DOCX write-back | `app/backend/processors/docx_processor.py:383-406 (SDT), 408-461 (para-in-cell), 509-531 (txbx)` | add `replace` branch (2.3) |
| DOCX bilingual | `app/backend/processors/docx_processor.py:462-508 (body para path)` | new `bilingual` dual-column-table path (2.1) |
| XLSX write-back | `app/backend/processors/xlsx_processor.py:40-57 (signature), 263-279 (write block)` | add `output_mode` param; branch into adjacent/annotation/replace (2.2) |
| PPTX SmartArt | `app/backend/processors/pptx_processor.py:121-179 (_update_smartart_texts), 458 (call site)` | add `replace` branch (2.3) |
| API contract | `contracts/api/api-contract.md:316` + `openapi.yml`/`openapi.json` | enum gains `bilingual`; regen via `cdd-kit openapi export` |
| Data-shape contract | `contracts/data/data-shape-contract.md` | document per-format output structure |

## Key Decisions

- **Bilingual DOCX = two-column table (col-A source, col-B translation), one row per
  body paragraph**: rationale → the feature's headline benefit is round-trip into CAT tools
  (DeepL/Smartcat/Trados export aligned dual-column bitext, which import segment-by-segment);
  the literal requirement is 雙欄 (two columns); the source paragraph's `<w:p>` is relocated
  into col-A so run-level formatting is preserved. → rejected alternative: alternating styled
  paragraphs (translation paragraph below source) — this is indistinguishable from the existing
  `append` path, does not round-trip as aligned bitext, and would not justify a new enum value.
  → rejected alternative: full-document rebuild into one table — loses images/charts/section
  layout. Non-paragraph blocks (tables, images, text boxes) are NOT wrapped; they pass through
  in document order with their existing append/replace handling. **ADR-0007 records this.**

- **Cross-format `bilingual`: accept at API, degrade at orchestrator (not reject)**: rationale →
  a single job can mix DOCX+XLSX+PPTX under one `output_mode`; rejecting `bilingual` at the API
  layer would block the DOCX files in that batch. The orchestrator already owns per-format
  degradation (multi-target `replace`→`append`, BR-67) via `effective_output_mode`; `bilingual`
  on a non-DOCX file degrades to `append` there and surfaces a notice in the existing job
  `warnings` field (same mechanism PDF uses for renderer fallback). → rejected alternative:
  hard-reject at the API/422 — breaks mixed-format batches and diverges from the existing clamp
  precedent.

- **XLSX `adjacent` column targeting = block-shift by original sheet width**: translation for
  cell (r, c) is written to column `c + original_max_column`, i.e. a parallel translated block
  appended to the right of all existing data. rationale → guarantees no overwrite of neighbour
  data and keeps per-column alignment stable across rows; source cell value and width unchanged,
  no `wrap_text`. → rejected alternative: write to `c+1` in place — overwrites the adjacent
  column and corrupts the sheet. → rejected alternative: first empty column per row — produces
  ragged, misaligned translation columns.

- **XLSX `annotation` = openpyxl `Comment`, non-destructive + idempotent**: reuse the already
  imported `Comment` (the formula-comment path at `xlsx_processor.py:255-260` is the precedent).
  Idempotency mirrors line 259 (skip when our comment text already matches). If a pre-existing
  non-translation comment is present, append the translation below it rather than clobber it, so
  author comments survive. Source cell value unchanged, no `wrap_text`. → rejected alternative:
  unconditional `cell.comment = Comment(...)` — destroys user-authored comments.

## Data Flow
`OutputMode` (schemas.py) → `JobCreate` request → `job_manager` → `orchestrator.process_files
(output_mode=…)` → `effective_output_mode` chokepoint (clamp multi-target `replace`→`append`;
degrade non-DOCX `bilingual`→`append`, emit `warnings`) → `translate_docx` /
`translate_pptx` / `translate_xlsx_xls(output_mode=…)` → per-element write-back branch
(`append` | `replace` | `bilingual` | XLSX `adjacent`/`annotation`). 2.3 and 2.2 affect only
the write-back branch selection; extraction segments are identical across modes.

## Migration / Rollback
No data migration — `output_mode` is a per-request field with no persisted schema. Default
remains `append`, so untouched callers see identical behaviour (AC-8 regression). Rollback path:
revert the enum value and the processor write-back branches; the orchestrator degrade rule is
additive and inert when `bilingual` is never sent. No feature flag is added; the enum value
itself is the gate (omitting `bilingual` from a request fully disables the new DOCX path).

## Open Risks
- Bilingual relocation of `<w:p>` into table cells: paragraphs inside existing tables, headers/
  footers, multi-column sections, and SDT-wrapped content need explicit pass-through handling —
  scope and exact block taxonomy is an implementation-plan concern; structural assertion in tests
  must prove source and translation occupy distinct cells (AC-2).
- Multi-target + `bilingual`: side-by-side has no in-place ambiguity, so it need not clamp like
  `replace`; intended shape is one translation column per target (col-A source + col-B..N). Must
  be confirmed in the data-shape contract before implementation.
- XLSX `adjacent` block-shift collides if the sheet already has populated columns beyond
  `max_column` due to sparse/merged regions; implementation must compute width from the true used
  range, not a cached value.
