# Change Classification

## Change Types
- primary: feature-add (backend, output-side layout-QA safety net on the PDF render path)
- secondary: env-change (new `LAYOUT_QA_ENABLED` flag), business-logic-change (new BR governing the fail-soft layout-QA disclosure); conditionally ci-cd-change if the shared metric core is re-hosted and `ci-gate-contract.md` tool paths shift.

## Lane
- feature

## Risk Level
- low
- Rationale: default-OFF flag, fail-soft (all exceptions caught+logged, never fails a job), additive/observational, explicitly no output/pixel change. Blast radius contained by the gate. Classified upward on required agents/contracts (not on risk) because it touches the `orchestrator.py` hub and introduces a shared metric module consumed by both CI gate and runtime.

## Impact Radius
- module-level (backend PDF render/orchestration + runtime config + business/env contracts; no API, no UI, no Office paths)

## Tier
- 3

## Architecture Review Required
- yes
- reason: Non-obvious module-boundary/data-flow decision — where the shared metric core physically lives (move into `app/backend/services/layout_qa.py` with `tests/metrics/` re-exporting, vs runtime service importing from `tests/metrics/`) so BOTH the CI gate and the runtime service share ONE implementation without duplication (the shared-module-consumed-by-multiple-backends risk from the promoted learnings). Also decides the orchestrator post-render seam placement (alongside BR-104's existing sweep), the aggregated-warning shape, and the BIoU budget constant. `spec-architect` writes `design.md` before `implementation-planner`.

## Required Artifacts
The 7 always-required: change-request, change-classification, implementation-plan, test-plan, ci-gates, tasks, context-manifest.

## Optional Artifacts (default: no)
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | Additive, default-off; no existing behavior changes. Design reference to closed PR #13 lives in change-request. |
| proposal.md | no | Scope is settled; no separate product investigation. |
| spec.md | no | Behavior fully expressed via new BR + change-request success criterion. |
| design.md | yes | Architecture Review Required = yes: metric-core hosting (module-boundary), orchestrator post-render seam, aggregated-warning shape, BIoU budget constant. |
| qa-report.md | no | Routine pass/fail → `agent-log/qa-reviewer.yml`. Promote only on blocking/approved-with-risk findings. |
| regression-report.md | no | Default-off + fail-soft; regression coverage lives in tests + qa-reviewer log. |
| visual-review-report.md | no | Explicit non-goal: no pixel/output change. |
| monkey-test-report.md | no | No interactive/UI surface. |
| stress-soak-report.md | no | Opt-in per-job pass; planner bounds BIoU matching, but no durable load evidence needed. |

## Required Contracts
- API: none — `job.warnings` already exists (BR-96/BR-104); non-goal of a new endpoint. No `openapi.yml` re-export.
- CSS/UI: none — non-goal (no UI component).
- Env: yes — add `LAYOUT_QA_ENABLED` (default off, mirroring `LAYOUT_DETECTOR_ENABLED`) to `contracts/env/env-contract.md`, `contracts/env/.env.example.template`, `contracts/env/env.schema.json`.
- Data shape: conditional — add a note to `contracts/data/data-shape-contract.md` ONLY if the aggregated warning introduces a new category/field beyond the existing `job.warnings` shape; if it reuses the BR-104 shape, no edit. contract-reviewer/planner decide.
- Business logic: yes — new BR at the next free number ABOVE BR-105 (BR-38 and BR-104 already live — do NOT reuse/edit) in `contracts/business/business-rules.md`, governing the fail-soft, default-off layout-QA disclosure.
- CI/CD: conditional — if the metric core is re-hosted into `app/backend/services/`, update `contracts/ci/ci-gate-contract.md` tool-path references; if it stays in `tests/metrics/` no edit. ci-cd-gatekeeper reviews.

## Required Tests
- unit: yes — `run_layout_qa(...)` yields exactly one aggregated warning; flag-off = pure no-op; BIoU-below-budget path; residual-source-text path; both signals aggregate into ONE entry.
- contract: yes — env contract test (`LAYOUT_QA_ENABLED` present, default off) + new-BR presence test.
- integration: yes — orchestrator PDF post-render branch emits exactly one `job.warnings` entry via `warnings_callback` → `_record_job_warning` when enabled; nothing when disabled.
- data-boundary: yes — degenerate output PDFs (empty/zero bbox lists, no text, mismatched box counts, unreadable/corrupt PDF) handled without raising.
- resilience: yes — fail-soft: force the metric/re-open to raise; assert caught+logged, job never fails, no fabricated warning (covered by backend unit/integration, no separate harness/report).
- E2E / visual / fuzz-monkey / stress / soak: none.

## Required Agents
- spec-architect (design.md), implementation-planner, backend-engineer, test-strategist, contract-reviewer, ci-cd-gatekeeper, qa-reviewer.
- Not required: frontend-engineer, ui-ux-reviewer, visual-reviewer (no UI/pixel change); e2e-resilience-engineer / stress-soak-engineer / monkey-test-engineer (fail-soft is unit/integration-level; default-off opt-in).

## Inferred Acceptance Criteria
- AC-1: With `LAYOUT_QA_ENABLED=false` (default), no layout-QA pass runs; rendered output + job behavior byte-for-byte unchanged (no new `job.warnings` entry).
- AC-2: With `LAYOUT_QA_ENABLED=true`, after a PDF render whose mean best-match BIoU is below the regression budget, exactly ONE aggregated `job.warnings` entry is emitted via `warnings_callback` → `_record_job_warning`.
- AC-3: With `LAYOUT_QA_ENABLED=true`, residual untranslated source text inside its own bbox emits a warning; when both BIoU regression and residual text occur they aggregate into the SAME single entry.
- AC-4: Any exception inside the layout-QA pass (metric error, corrupt/unreadable PDF, etc.) is caught+logged; the job never fails and no warning is fabricated (fail-soft).
- AC-5: BIoU and residual-text metrics are a SINGLE shared implementation used by BOTH the runtime service and the `tests/metrics/` CI-gate tools — no duplicated metric logic; all consumer imports verified (no orphaned module).
- AC-6: `LAYOUT_QA_ENABLED` documented in `env-contract.md`, `.env.example.template`, `env.schema.json`, mirroring `LAYOUT_DETECTOR_ENABLED`, default off.
- AC-7: Behavior governed by a NEW business rule (next free number above BR-105) without editing BR-38 or duplicating BR-104's truncation disclosure.
- AC-8: Layout QA wired only into the PDF output path; Office (docx/pptx/xlsx) untouched; no new API endpoint or UI component.
- AC-9: The BIoU regression budget is a documented named constant (PR #13 used 0.8 — confirm during design), not a magic literal.

## Tasks Not Applicable
- not-applicable: 2.1 (API contract), 2.2 (CSS/UI contract), 3.3 (E2E/resilience — resilience folded into unit/integration), 3.4 (data-boundary/monkey engineer — boundary cases folded into unit tests 3.1), 3.5 (stress/soak), 4.2 (frontend), 5.1 (UI/UX review), 5.2 (visual review).
- Design task 1.3 is APPLICABLE (design.md required — do NOT skip).

## Clarifications or Assumptions
- Tier-floor override recommended: gate vocab-scanner may floor on `"endpoint"` (appears ONLY in the non-goal "NOT adding a new API endpoint"), `"config"`/`"flag"` (a default-off feature flag, not a secret/migration), and generic feature-add terms — none reflect a real migration/secret/auth/endpoint change. Apply `tier-floor-override`; keep Tier 3.
- Performance caveat (planner, not a required stress artifact): best-match BIoU is source-boxes × output-boxes; on large PDFs this is a per-job cost even though default-off. Design should bound/cap the matching or short-circuit above a box-count threshold.
- Assumption: aggregated warning reuses the existing BR-96/BR-104 `job.warnings` shape; data-shape edit only if a new category/field is introduced (hence conditional).
- Assumption: `_record_job_warning`/`warnings_callback` plumbing lives in `job_manager.py` / `orchestrator.py`; backend-engineer confirms at the seam, does not re-invent.
- Deferred to spec-architect/planner: metric-core hosting decision + BIoU budget default constant.
