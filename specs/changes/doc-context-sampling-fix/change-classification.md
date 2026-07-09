# Change Classification

## Change Types
- primary: bug-fix (implementation correction of the BR-109 document-context sampler + observability)
- secondary: business-logic-change (adds a clarifying BR-109 sub-rule defining what constitutes a valid sample and mandating an observable skip/failure at INFO)

## Lane
- bug-fix

Justification: this is a symptom-driven defect. An already-shipped behavior (BR-109's one-sentence document-context summary) is silently broken — it never fires on real documents because `_sample_file_text` returns `''` for legacy `.xls`, table-only `.docx`, and table/graphic-frame `.pptx`. The request starts from an observed wrong behavior in a real job (`d19484ce43f94fa4b076ef0a0d07abae`) with root-cause pointers already found, which is the definition of the bug-fix lane. It is promoted alongside `business-logic-change` because a clarifying contract rule is warranted, but the evidence discipline of the bug-fix lane applies.

## Bug Symptom Type
- data

The core symptom is that document text extraction/sampling yields empty content for common document shapes (legacy binary `.xls`, text-in-tables `.docx`/`.pptx`), so the downstream context feature receives no data. This routes to `backend-engineer`, `test-strategist`, and — because a business-logic contract rule is touched — `contract-reviewer`.

## Diagnostic Only
- no

The change makes real behavior fixes (read table text; obtain a real sample for legacy `.xls`), not only instrumentation. Added INFO observability rides alongside the fix; it is not the sole deliverable.

## Bug Evidence Required
- symptom: BR-109 preamble never reaches the model; header cells translated with generic meaning (e.g. `制作日期` → `Ngày sản xuất`, `审核(工务)` → `Kiểm duyệt (công vụ)`) in job `d19484ce43f94fa4b076ef0a0d07abae`.
- expected behavior: `.xls` sampling reads real text; `.docx`/`.pptx` sampling includes table (and pptx graphic-frame) text; a `[CONTEXT] Detected:` INFO line appears when detection runs.
- actual behavior: `_sample_file_text` returns `''` for legacy `.xls` (openpyxl `InvalidFileException`), for the table-only `.docx` (reads only `doc.paragraphs`), and misses tables in `.pptx`; no `[CONTEXT] Detected:` line since 2026-06-19.
- reproduction status: to be recorded by `bug-fix-engineer` as a genuinely-FAILED pre-fix behavioral `cdd-kit test run` (assertion failure), per the bug-fix evidence rules.
- hypotheses: (1) openpyxl cannot open legacy `.xls`; (2) `.docx` branch ignores table cells; (3) `.pptx` branch ignores table/graphic-frame text; (4) empty-sample skip and `_detect_document_context` exception path log below INFO.
- root cause pointer: `app/backend/processors/orchestrator.py` — `_sample_file_text` (per-format branches) and `_detect_document_context` (silent skip + `logger.debug` swallow).
- regression evidence: new tests must stay green post-fix (legacy `.xls`, table-only `.docx`, pptx-table sampling all produce non-empty sample and emit `[CONTEXT] Detected:`), and a sampling failure must degrade to no-preamble without raising.

## Risk Level
- medium

## Impact Radius
- module-level

Cross-module reads only: orchestrator sampling reuses/coordinates with the xlsx/docx/pptx processors, parsers, and the LibreOffice conversion helper.

## Tier
- 3

## Architecture Review Required
- no
- reason: the single open design question (reuse the existing LibreOffice `.xls`→`.xlsx` conversion vs. read the legacy format directly) is a bounded, single-module implementation choice with a documented constraint (must not double-convert or change per-file timing). The change-request explicitly delegates it to the implementation plan; there is no module-boundary redesign, data-flow re-architecture, or migration/rollback decision.

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

## Optional Artifacts (default: no — set yes only with explicit reason)
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | Current behavior and root cause are already captured in change-request.md "Known Context"; bug-fix-engineer records evidence in agent-log/bug-fix-engineer.yml. |
| proposal.md | no | No product/behavior decision beyond the documented fix. |
| spec.md | no | No new user-facing spec; governed by existing BR-109. |
| design.md | no | Architecture Review is no. |
| qa-report.md | no | Routine pass/fail via agent-log/qa-reviewer.yml; promote to yes only if a blocking/approved-with-risk finding arises. |
| regression-report.md | no | Regression evidence carried as tests + agent-log pointers. |
| visual-review-report.md | no | No UI output. |
| monkey-test-report.md | no | Not applicable. |
| stress-soak-report.md | no | Not applicable. |

Artifact minimization:
- Prefer optional `agent-log/*.yml` pointers for routine review evidence.
- Create report markdown only for blocking findings, approved-with-risk, visual evidence bundles, or high-risk load/soak results.
- Later artifacts should reference earlier artifacts by path/section/id instead of duplicating full content.

## Required Contracts
- API: none
- CSS/UI: none
- Env: none (no new env vars/flags; `CONTEXT_DETECTION_ENABLED` is a `config.py` constant, `QWEN_CONTEXT_FLOW_ENABLED` unchanged)
- Data shape: none (xlsx phantom-column data defect is explicitly out of scope)
- Business logic: `contracts/business/business-rules.md` — add/clarify a BR-109 sub-rule: a valid sample must include table-resident text (docx/pptx) and legacy-format text (`.xls`); a genuinely unobtainable or failed sample must degrade to no-preamble AND be logged at INFO with the reason (never silent, never raise into the pipeline). Bump `schema-version` from the LIVE value and update `contracts/CHANGELOG.md`.
- CI/CD: none

## Required Tests
- unit: yes — `_sample_file_text` per-format branches (legacy `.xls`, table-only `.docx`, `.pptx` with tables/graphic-frames) return non-empty representative text; `_detect_document_context` emits INFO on skip/failure and on success.
- contract: no
- integration: yes — end-to-end sampling → `_detect_document_context` → `[CONTEXT] Detected:` for the three document shapes; verify the `.xls` path does not double-convert or shift per-file timing.
- E2E: no
- visual: no
- data-boundary: yes — malformed/empty document, legacy binary `.xls`, table-only doc, and no-text doc must degrade gracefully to no-preamble without raising into the job pipeline.
- resilience: no
- fuzz/monkey: no
- stress: no
- soak: no

## Required Agents
- bug-fix-engineer (records reproduction/root-cause/regression evidence; owns the fix)
- backend-engineer (implements sampling fixes across orchestrator/processors; data symptom owner)
- implementation-planner (produces the execution packet; resolves the `.xls` reuse-vs-direct-read decision against live source)
- test-strategist (bug-fix lane; designs unit/integration/data-boundary tests and AC→test mapping)
- contract-reviewer (business-rules BR-109 sub-rule + CHANGELOG + schema-version)
- qa-reviewer (bug-fix lane; release readiness, confirms no required test failures)

## Inferred Acceptance Criteria
- AC-1: Sampling a legacy binary `.xls` yields non-empty representative text (via reuse of the existing LibreOffice conversion or a legacy reader), so the BR-109 summary can fire.
- AC-2: Sampling a `.docx` whose text lives entirely in tables includes table-cell text, not only `doc.paragraphs`.
- AC-3: Sampling a `.pptx` includes table and graphic-frame text, not only `shape.has_text_frame` shapes.
- AC-4: When a sample genuinely cannot be obtained, `_detect_document_context` emits an INFO log stating the reason instead of skipping silently.
- AC-5: When context detection succeeds, a `[CONTEXT] Detected:` INFO line is emitted.
- AC-6: A sampling failure never raises into the job pipeline; the job proceeds with no preamble, preserving BR-109's graceful fallback.
- AC-7: The `.xls` sampling path invokes the LibreOffice conversion at most ONCE per file, and leaves the existing `xlsx_processor` conversion and its per-file timing semantics untouched. (Amended after implementation-planner verified live source: the original wording, "does not double-convert", was self-contradictory — a `.xls` is necessarily converted twice per run, once by the sampler and once by the unchanged processor, because sharing one conversion across that boundary is exactly the per-file timing change the second clause forbids. The residual second conversion is an accepted, bounded cost; eliminating it via a shared/cached conversion is a recorded follow-up.)
- AC-8: Re-running the legacy `.xls` and the table-only `.docx` from job `d19484ce43f94fa4b076ef0a0d07abae` both emit a `[CONTEXT] Detected:` INFO line.

## Tasks Not Applicable
- not-applicable: 1.3, 2.1, 2.2, 2.3, 2.4, 2.6, 3.3, 3.5, 4.2, 4.3, 4.4, 5.1, 5.2

Rationale: 1.3 design.md (Architecture Review is no); 2.1/2.2/2.3/2.4/2.6 no API, CSS/UI, env, data-shape or CI/CD contract touched; 3.3 no E2E/resilience surface; 3.5 no stress/soak risk; 4.2 no frontend surface; 4.3 no new env vars; 4.4 existing CI gates suffice; 5.1/5.2 no UI surface.

## Clarifications or Assumptions
- Assumption: this is treated as a bug-fix that also carries a small clarifying business-rule refinement (valid-sample coverage + mandatory INFO observability) rather than a change to BR-109's delivery mechanism, which is out of scope. If contract-reviewer judges that no new normative rule is needed, the `business-logic-change` type may be dropped and the change stays a pure Tier 3 bug-fix — but classifying upward, the contract path is required here.
- Assumption: the `.xls` reuse-vs-direct-read decision is resolved by `implementation-planner` (delegated by the change-request), not by architecture review.
- Assumption: the xlsx table-batch phantom-column defect (`ws.max_column` = 257) is explicitly out of scope; any file/test touching `table_serializer.parse()` behavior belongs to the deferred JSON structured-I/O change.
- Verified by main Claude before manifest write: every path named in the Context Manifest Draft exists on disk (including `app/backend/processors/libreoffice_helpers.py`, `app/backend/services/context_prompts.py`, `app/backend/utils/logging_utils.py`).

## Context Manifest Draft

See `context-manifest.md` for the authoritative read boundary. Summary of affected surfaces:

- `app/backend/processors/orchestrator.py` — `_sample_file_text`, `_detect_document_context` (primary)
- Legacy `.xls` sampling / LibreOffice conversion reuse — `app/backend/processors/xlsx_processor.py`, `app/backend/processors/libreoffice_helpers.py`
- `.docx` table-text sampling — `app/backend/processors/docx_processor.py`, `app/backend/parsers/docx_parser.py`
- `.pptx` table/graphic-frame sampling — `app/backend/processors/pptx_processor.py`, `app/backend/parsers/pptx_parser.py`
- Context prompt assembly / observability — `app/backend/services/context_prompts.py`, `app/backend/utils/logging_utils.py`, `app/backend/config.py`
- Business rule BR-109 — `contracts/business/business-rules.md`
