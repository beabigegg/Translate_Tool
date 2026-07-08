# Change Classification

## Change Types
- primary: bug-fix
- secondary: data-shape-note (additive note to `contracts/data/data-shape-contract.md`)

## Lane
- bug-fix

## Bug Symptom Type
- data

## Diagnostic Only
- no

## Bug Evidence Required
- symptom: `GET /api/jobs/{id}` for a running PDF job returns `current_stage` / `current_segment_source` / `current_segment_draft` = `null` throughout translation.
- expected: PDF jobs report `current_stage="translate"` with non-null source/draft, matching Office formats.
- actual: fields stay `null` for the entire PDF job; StageDetailPanel shows no current segment for PDFs.
- root cause pointer: `translate_pdf` + `_translate_pdf_with_pymupdf` / `_translate_pdf_to_pdf` / `_translate_pdf_with_pypdf2` never receive/emit a `status_callback`; `orchestrator.py` .pdf branch does not pass one; PDF uses `translate_blocks_batch`, bypassing `translation_service.translate_texts` where #7 wired the snapshot.
- reproduction: recorded by bug-fix-engineer per ADR 0006 — a FAILED pre-fix `cdd-kit test run`, then green post-fix.
- regression: Office + judge snapshot paths unchanged; PDF output/performance unchanged (additive/observational only).

## Risk Level
- low-to-medium

## Impact Radius
- module-level (backend PDF progress-snapshot wiring)

## Tier
- 3

## Architecture Review Required
- no — root cause + fix seam confirmed; reuses existing `on_segment_done` callback and the #7 `CurrentSegmentSnapshot`/`status_callback` pattern.

## Required Artifacts
The 7 always-required: change-request, change-classification, implementation-plan, test-plan, ci-gates, tasks, context-manifest.

## Optional Artifacts (default: no)
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | captured in change-request |
| proposal.md | no | no product decision open |
| spec.md | no | parity with Office, no new behavior |
| design.md | no | no architecture review |
| qa-report.md | no | upgrade to yes only on blocking/approved-with-risk finding |
| regression-report.md | no | covered by test-plan + agent-log |
| visual-review-report.md | no | no UI change |
| monkey-test-report.md | no | n/a |
| stress-soak-report.md | no | additive, negligible perf |

## Required Contracts
- API: none (no route change; JobStatus snapshot fields already documented by #7). contract-reviewer confirms no drift (read-only).
- CSS/UI: none. Env: none. Business logic: none. CI/CD: none.
- Data shape: `contracts/data/data-shape-contract.md` — additive note that `current_stage="translate"` + source/draft now also populate on the PDF path.

## Required Tests
- unit: PDF snapshot emission (translate_pdf threads status_callback; on_segment_done emits CurrentSegmentSnapshot(stage="translate", source, draft)).
- integration: orchestrator .pdf branch → `job.current_segment` populated end-to-end (backend).
- data-boundary: `current_segment` nullability transition on the PDF path.
- contract: data-shape snapshot fields hold on the PDF path.
- E2E / visual / resilience / fuzz / stress / soak: none.

## Required Agents
- implementation-planner, bug-fix-engineer (backend impl owner + bug-fix evidence; folds the data-symptom backend role), test-strategist, contract-reviewer, qa-reviewer.
- Not required: frontend-engineer, ui-ux-reviewer, visual-reviewer (fields + panel already exist), spec-architect, e2e/monkey/stress-soak.

## Inferred Acceptance Criteria
- AC-1: For a running PDF job, `GET /api/jobs/{id}` returns `current_stage="translate"` while translating.
- AC-2: During PDF translation, `current_segment_source` + `current_segment_draft` are non-null and reflect the current segment.
- AC-3: `translate_pdf` accepts `status_callback` and threads it into `_translate_pdf_with_pymupdf` / `_translate_pdf_to_pdf` / `_translate_pdf_with_pypdf2`.
- AC-4: `translate_blocks_batch`'s `on_segment_done(src, translated)` emits `CurrentSegmentSnapshot(stage="translate", source, draft)` to `status_callback` (CurrentSegmentSnapshot lazy-imported from job_manager — no circular import).
- AC-5: `orchestrator.py` passes `status_callback` into the `.pdf` branch.
- AC-6: Office (docx/pptx/xlsx) snapshot + judge snapshot fields unchanged (no regression).
- AC-7: PDF translation output + measurable performance unchanged (additive/observational only).
- AC-8: A pre-fix test shows `current_segment_*` stays `null` on the PDF path (red); the same test passes after the fix (green).

## Tasks Not Applicable
- not-applicable: 1.3, 2.1, 2.2, 2.3, 2.5, 2.6, 3.3, 3.4, 3.5, 4.2, 4.4, 5.1, 5.2

## Clarifications or Assumptions
- tier-floor false-positive risk ("endpoint"/"env var"/"route"/".pdf branch" appear only in negation context) → apply `tier-floor-override` if the gate flags it.
- Generate test evidence via `conda run -n translate-tool cdd-kit test run …`, scoped to NEW node-ids (avoid the onnxruntime subset artifact).
- Threading a new `status_callback` kwarg has historically broken signature-reproducing test doubles — grep + update PDF-path fakes in the same change (CLAUDE.md learning).
