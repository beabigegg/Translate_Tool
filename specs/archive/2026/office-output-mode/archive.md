# Archive — office-output-mode

## Change Summary

Extended the translation pipeline's `output_mode` field from 2 values (`append`, `replace`) to 5 values (`append`, `replace`, `bilingual`, `adjacent`, `annotation`), implementing format-specific write-back semantics across DOCX, XLSX, and PPTX processors. The change was motivated by Wave 3 Track F: translators need format-faithful bilingual documents (DOCX), side-by-side XLSX columns for CAT tool import, and annotation-layer translations without disturbing source cell values. A cross-format degradation layer in the orchestrator ensures non-native modes (`bilingual` on XLSX, `adjacent` on DOCX, etc.) automatically fall back to `append` with a warning rather than failing.

## Final Behavior

- **DOCX bilingual**: each body paragraph replaced by a two-column `<w:tbl>` (col-A source, col-B translation); SDT/para-in-cell/text-box paths honor `replace` mode
- **XLSX adjacent**: translation written to `(row, col + original_max_column)`; source cell unchanged
- **XLSX annotation**: translation attached as `openpyxl.Comment`; source cell unchanged; idempotent; existing non-tool comments preserved with `\n---\n` separator
- **XLSX replace**: source cell overwritten; no `wrap_text` inflation
- **PPTX SmartArt replace**: `<a:t>` node text set to translation only
- **Orchestrator**: per-file `_file_output_mode` computes resolved mode; bilingual/adjacent/annotation degrade to `append` for non-native format files with warning emitted to `job.warnings`

## Final Contracts Updated

- `contracts/api/api-contract.md` — `output_mode` enum: `enum(append,replace,bilingual,adjacent,annotation)`; warnings field prose updated; schema-version 0.9.0
- `contracts/api/openapi.yml` — regenerated with all 5 enum values
- `contracts/data/data-shape-contract.md` — §Per-Format output_mode Output Structure (DOCX/XLSX/PPTX write-back shapes); §Cross-format degradation rules table; schema-version 0.15.0
- `docs/adr/0007-bilingual-docx-dual-column.md` — structural decision: two-column table vs alternating paragraphs (two-column wins for bitext alignment and CAT compatibility)

## Final Tests Added / Updated

- `tests/test_output_mode_processors.py` — 21 unit tests (AC-1..AC-7 data-boundary coverage per processor)
- `tests/test_output_mode_orchestrator.py` — integration tests: degrade path for bilingual/adjacent/annotation on non-native formats with warning assertions
- `tests/test_output_mode_api.py` — contract tests: all 5 enum values accepted, invalid values rejected, openapi sync

## Final CI/CD Gates

| gate | tier | command |
|---|---|---|
| validate-contracts | 1 | `cdd-kit validate --contracts` |
| openapi-sync | 1 | `cdd-kit openapi export --check` |
| targeted-output-mode | 1 | `pytest test_output_mode_processors.py test_output_mode_orchestrator.py test_output_mode_api.py` |
| full-test-suite | 1 | `pytest tests/` |

## Production Reality Findings

- **Contract-reviewer initial BLOCK**: backend-engineer shipped `bilingual` but omitted `adjacent` and `annotation` from the `OutputMode` enum in `schemas.py` and from `api-contract.md`. Clients sending those values would have received HTTP 422. Fixed in a second backend-engineer pass before merge.
- **QA gate initially BLOCKED on missing specs dir**: CDD artifacts existed only in the main repo working tree, not in the worktree. Fixed by copying `specs/changes/` to the worktree before committing. Lesson saved as workflow guidance.
- 1009 tests passing at merge; 1 pre-existing order-dependent failure in `test_judge_apply.py` passes in isolation (not a regression from this change).

## Lessons Promoted to Standards

- **promote-to-guidance** → `CLAUDE.md` (folded into existing `/cdd-close` entry): "At `/cdd-close`: remove the archived change's `cdd-kit gate <id>` line AND any per-change targeted-test steps from `.github/workflows/contract-driven-gates.yml`." Evidence: `ci-gates.md` §New Workflow Changes.
- **promote-to-guidance** → `CLAUDE.md` (new entry): "Git worktrees have separate working directories — `specs/changes/<id>/` created in main working tree invisible inside worktree; copy before committing or running gate; brief review agents with full absolute worktree path." Evidence: QA gate BLOCKED finding (qa-reviewer `a502f6b7f71d2f911`).

## Follow-up Work

None. All AC-1..AC-8 implemented and verified.

---

*This archive is historical evidence. Current requirements live in `contracts/` and active project guidance.*
