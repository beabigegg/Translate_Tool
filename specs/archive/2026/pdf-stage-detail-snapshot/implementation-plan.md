---
change-id: pdf-stage-detail-snapshot
schema-version: 0.1.0
last-changed: 2026-07-08
---

# Implementation Plan: pdf-stage-detail-snapshot

## Objective
Make running **PDF** jobs populate `JobRecord.current_segment` (stage `"translate"` +
non-null source/draft) during translation, so the StageDetailPanel shows the current
segment for PDFs — parity with Office (docx/pptx/xlsx). Root cause is confirmed
(change-classification.md `## Bug Evidence Required`): the PDF pipeline
`translate_pdf → translate_blocks_batch` bypasses `translation_service.translate_texts`
(where #7 wired the snapshot), and `translate_pdf` has no `status_callback` param.
Fix is additive/observational: thread an optional `status_callback` into the PDF path
and emit the existing `CurrentSegmentSnapshot` via `translate_blocks_batch`'s existing
`on_segment_done` hook. Deliver against AC-1..AC-8 (change-classification.md
`## Inferred Acceptance Criteria`), bug-fix lane, Tier 3.

## Execution Scope

### In Scope
- `pdf_processor.translate_pdf`: add optional `status_callback` param (default `None`);
  thread into `_translate_pdf_with_pymupdf`, `_translate_pdf_with_pypdf2`,
  `_translate_pdf_to_pdf` (AC-3).
- In each of the 3 sub-functions: add the `status_callback` param and pass
  `on_segment_done=<wrapper>` at the `translate_blocks_batch(...)` flatten-batch call;
  wrapper builds `CurrentSegmentSnapshot(stage="translate", source, draft)` and calls
  `status_callback(<detail>, snapshot)` (AC-2, AC-4).
- `orchestrator.py` `.pdf` branch: pass `status_callback=status_callback` into
  `translate_pdf(...)` (AC-5).
- `contracts/data/data-shape-contract.md`: apply contract-reviewer's drafted PDF-path
  parity note + schema-version bump + CHANGELOG (per contract-reviewer decision).
- New `tests/test_pdf_stage_snapshot.py` + AC-8 RED→GREEN bug-fix evidence; regression
  via existing suites (test-plan.md).

### Out of Scope
- Office (docx/pptx/xlsx) and judge snapshot wiring — unchanged, regression-gated only
  (AC-6). Do not touch `translation_service.translate_texts` snapshot logic.
- PDF translation output / rendering / layout / performance — no change (AC-7).
- Any critique/QE/adopt loop for the PDF path — only the `"translate"` stage applies for
  PDF (change-request.md `## Non-goals`).
- New endpoint / env var / UI component / route change. `api-contract.md` untouched
  (task 2.1 stays skipped; contract-reviewer confirmed no `JobStatus` drift).
- The Windows COM `word_convert → translate_docx` route inside `translate_pdf`
  (L353-375) and the `_translate_pdf_tables_with_context` table-cell path — see
  `## Known Risks`; not part of the 3 named sub-functions (AC-3).

## Required Changes
| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | `app/backend/processors/pdf_processor.py` `translate_pdf` (L284-413) | Add `status_callback: Optional[Callable[[Optional[str], Optional[Any]], None]] = None` to the signature (after `warnings_callback`, L300); add `Any` to the `typing` import (L14). Thread `status_callback=status_callback` into the 3 dispatch calls: `_translate_pdf_to_pdf` (L335), `_translate_pdf_with_pymupdf` (L388), `_translate_pdf_with_pypdf2` (L402). | bug-fix-engineer |
| IP-2 | `pdf_processor.py` 3 sub-functions | Add the same `status_callback` param (default `None`) to `_translate_pdf_with_pymupdf` (L416), `_translate_pdf_with_pypdf2` (L659), `_translate_pdf_to_pdf` (L782). In each, at the flatten `translate_blocks_batch(...)` call (L579, L731, L930), pass `on_segment_done=<wrapper>`. Verified: none of these 3 call sites currently pass `on_segment_done` (grep-confirmed) — no composition needed; do NOT clobber if a later edit introduces one. | bug-fix-engineer |
| IP-3 | `app/backend/processors/orchestrator.py` `.pdf` branch (L865-882) | Pass `status_callback=status_callback` into the `translate_pdf(...)` call. `status_callback` is already a `process_files` param (L395), in scope here. | bug-fix-engineer |
| IP-4 | `contracts/data/data-shape-contract.md` | Apply contract-reviewer's EXACT drafted PDF-path parity paragraph inside `### JobStatus / JobRecord — current-segment snapshot fields`, after the "All 8 fields…" sentence. Bump `schema-version` 0.17.2 → 0.17.3. Append the drafted `## [data 0.17.3]` CHANGELOG entry. Do NOT edit `api-contract.md`. | bug-fix-engineer |
| IP-5 | `tests/test_pdf_stage_snapshot.py` (new) + regression | Add the 3 unit tests + AC-8 RED→GREEN evidence (test-plan.md `## Test Update Contract`). Regression: existing `test_job_manager_current_segment.py` (extend, add the `.pdf` end-to-end case), `test_jobstatus_stage_detail.py` (unmodified, stays green). | bug-fix-engineer |
| IP-6 | PDF-path test doubles | Grep for and update any fake/stub that reproduces the `translate_pdf` / sub-function signature or a `translate_blocks_batch` side_effect closure, in the same change (CLAUDE.md learning; param is optional so existing callers stay green). | bug-fix-engineer |

## Source Artifact Pointers
| source | relevant pointer | used for |
|---|---|---|
| change-classification.md | AC-1..AC-8; `## Bug Evidence Required`; Tier 3, bug-fix lane | acceptance + root-cause + lane |
| test-plan.md | `## Acceptance Criteria → Test Mapping`, `## Test Update Contract`, `## Notes` (anti-tautology + env) | tests to run/write, mock boundary |
| ci-gates.md | `## Required Gates for This Change` table | verification commands (blanket pytest, `cdd-kit validate --contracts`, local `cdd-kit gate --strict`) |
| agent-log/contract-reviewer.yml | drafted data-shape note; `data-shape 0.17.2 → 0.17.3`; api no bump | IP-4 exact contract edit |
| `translation_service.translate_texts` L483-512 | `status_callback(msg, CurrentSegmentSnapshot(stage="translate", source, draft))` + lazy import at L484 | the exact pattern IP-2 wrapper mirrors |
| `job_manager._status_cb` L390-398 | `_status_cb(detail, segment)` writes `status_detail` + `current_segment` | contract the PDF wrapper's `status_callback(detail, snapshot)` must satisfy |

## File-Level Plan
| path or glob | action | notes |
|---|---|---|
| `app/backend/processors/pdf_processor.py` | edit | IP-1 + IP-2. Add `Any` to `from typing import ...` (L14). Wrapper (define inside each `for tgt in targets` loop so `tgt` is captured, or bind `tgt` as a default arg): guard `if status_callback is None: return`, then lazy `from app.backend.services.job_manager import CurrentSegmentSnapshot`, then `status_callback(<short detail str, e.g. f"翻譯中… ({tgt})">, CurrentSegmentSnapshot(stage="translate", source=src, draft=translated))`. Do not construct the snapshot when `status_callback is None`. |
| `app/backend/processors/orchestrator.py` | edit | IP-3 — one added kwarg on the `.pdf` `translate_pdf(...)` call (L867). No other change. |
| `contracts/data/data-shape-contract.md` | edit | IP-4 — verbatim drafted note + `schema-version` bump + CHANGELOG. Bump from the LIVE version (confirm it is 0.17.2 before writing 0.17.3). |
| `tests/test_pdf_stage_snapshot.py` | create | IP-5 — 3 unit tests below; mock only `translate_blocks_batch` per branch (`patch.object(pdf_processor, "translate_blocks_batch", ...)` + fake parser), mirroring `tests/test_pdf_layout_viz_persistence.py`; never mock `CurrentSegmentSnapshot`. |
| `tests/test_job_manager_current_segment.py` | edit | IP-5 — add `test_pdf_job_populates_current_segment_stage_translate_end_to_end` (real `create_job` on a `.pdf`, mock only `translate_blocks_batch`/LLM client). |
| `tests/test_jobstatus_stage_detail.py` | none | regression-only, stays green unmodified (AC-6). |

## Contract Updates
- API: none. `contracts/api/api-contract.md` untouched — contract-reviewer confirmed the
  `JobStatus` `current_segment_*` fields are already declared by #7 (format-agnostic);
  this is a values-populate fix, not a schema change. `openapi.yml` export not needed.
- CSS/UI: none.
- Env: none.
- Data shape: `contracts/data/data-shape-contract.md` — additive PDF-path parity note
  (contract-reviewer draft), `schema-version` 0.17.2 → 0.17.3, `## [data 0.17.3]`
  CHANGELOG entry (IP-4).
- Business logic: none.
- CI/CD: none (ci-gates.md `## New Workflow Changes` = None; blanket `pytest tests/`
  picks up the new/edited test files automatically).

## Test Execution Plan
| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-3 | tests/test_pdf_stage_snapshot.py::test_translate_pdf_signature_accepts_status_callback | `translate_pdf` accepts `status_callback` and threads it to all 3 sub-functions |
| AC-2, AC-8 | tests/test_pdf_stage_snapshot.py::test_pymupdf_path_on_segment_done_emits_translate_stage_snapshot | mocked `translate_blocks_batch` FIRES `on_segment_done(src, translated)`; `status_callback` receives `CurrentSegmentSnapshot` with `stage=="translate"`, exact `source`/`draft` per call (RED pre-fix, GREEN post-fix) |
| AC-4 | tests/test_pdf_stage_snapshot.py::test_pypdf2_and_to_pdf_paths_on_segment_done_emit_translate_stage_snapshot | same emission asserted for the PyPDF2 and to-PDF paths |
| AC-1, AC-5 | tests/test_job_manager_current_segment.py::test_pdf_job_populates_current_segment_stage_translate_end_to_end | real `create_job` on a `.pdf`; `job.current_segment.stage == "translate"` with non-null source/draft end-to-end |
| AC-6 | tests/test_jobstatus_stage_detail.py; tests/test_translation_service_stage_snapshot.py; tests/test_job_manager_current_segment.py (existing) | Office/judge snapshot + JobStatus projection stay green, unmodified |
| AC-7 | tests/test_pdf_layout_table_fixes.py; tests/test_pdf_layout_viz_persistence.py; tests/test_pdf_render_warnings.py | existing PDF renderer suites stay green (output/perf unchanged) |

Test phases (bug-fix lane floor): `collect`, `targeted`, `changed-area`. Generate
evidence with `conda run -n translate-tool cdd-kit test run --phase <p> ...` scoped to the
EXACT node-ids above (never a `test_pdf_*` glob — avoids the onnxruntime import-ordering
subset artifact and guarantees the torch-bearing interpreter; CLAUDE.md learnings).
AC-8 bug-fix evidence (ADR 0006): record `agent-log/bug-fix-engineer.yml` with a
`bug-fix:` block whose `test-reproduced` points at a genuinely FAILED pre-fix
`cdd-kit test run` of
`test_pymupdf_path_on_segment_done_emits_translate_stage_snapshot` — recipe: temporarily
restore pre-fix `pdf_processor.py` (`git show main:app/backend/processors/pdf_processor.py
> app/backend/processors/pdf_processor.py`), run ONLY that node-id via
`cdd-kit test run --phase targeted` (fails: no `status_callback` param / never invoked),
then restore the fix and re-run that phase green; reproduction/regression `command` must
equal the recorded run's command minus runner-added flags.

## Handoff Constraints
- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into code or
  the log; follow the source pointers above (IP-4 applies the contract-reviewer draft
  verbatim, not a paraphrase).
- If this plan omits a required file, behavior, contract, or test, stop and report
  `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is
  approved (CER-001 for `schemas.py`/`routes.py` is `pending` — only open it if evidence
  shows the serialization layer also needs a change; it should not, per AC-6).

## Known Risks
- **Signature-reproducing test doubles** (recurred in qa-judge-hang-recovery,
  batch-critique-qe-scoring, translation-progress-detail-ui): adding a kwarg to
  `translate_pdf`/sub-functions can break fakes that reproduce the signature or a
  `translate_blocks_batch` side_effect closure. Mitigation: keep every new param
  optional/defaulted `None`; grep PDF-path tests for such doubles and update them in this
  change (IP-6). A whole-function `MagicMock`/`patch.object` replacement is tolerant of
  the new kwarg; a hand-written stub reproducing the arg list is not.
- **Circular import**: `job_manager` imports `orchestrator.process_files`, which imports
  `pdf_processor`. Import `CurrentSegmentSnapshot` LAZILY inside the wrapper (mirroring
  `translation_service` L484), never at module top of `pdf_processor.py`.
- **`Any` typing import**: `pdf_processor.py` L14 currently imports
  `TYPE_CHECKING, Callable, Dict, List, Optional` — add `Any` (or annotate the callback
  without `Any`) or the `status_callback` type hint will `NameError` at import.
- **Uncovered PDF sub-paths (accepted, out of scope)**: the Windows-only COM
  `word_convert → translate_docx` route (L353-375) and `_translate_pdf_tables_with_context`
  table-cell translation do not emit the snapshot after this change. AC-3 names only the 3
  sub-functions and the main flatten batch; table cells / COM route are not in scope. If a
  reviewer flags table-cell coverage, route back rather than expanding scope silently.
- **Anti-tautology (test-plan.md `## Notes`)**: the `translate_blocks_batch` mock's
  `side_effect` MUST itself call `on_segment_done(src, translated)`, and assertions must
  check exact `stage`/`source`/`draft` VALUES per call (N distinct, correctly-ordered
  snapshots for N segments) — a mock that returns results without firing `on_segment_done`,
  or that only asserts non-null, passes without exercising the wiring.
- **Contract version drift**: bump `schema-version` from the LIVE value in
  `data-shape-contract.md` (confirm 0.17.2 immediately before editing), not blindly from
  the number in this plan, in case a sibling change landed first.
- **Tier-floor false positive**: `"endpoint"/"route"/".pdf branch"` appear only in negation
  here; apply `tier-floor-override` with written rationale if `cdd-kit gate` flags it
  (change-classification.md `## Clarifications or Assumptions`).
