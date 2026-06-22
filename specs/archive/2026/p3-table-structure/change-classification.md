# Change Classification: p3-table-structure

## Change Types
- primary: feature-add
- secondary: data-shape-change (new table/cell IR), business-logic-change (numeric-cell passthrough rule, cell-batch boundary)

## Lane
- feature

## Risk Level
- medium

## Impact Radius
- cross-module

## Tier
- 2

## Architecture Review Required
- yes
- reason: Introduces a new optional ML-model runtime + failure mode (mirrors ADR 0003 layout_detector), a new table/cell IR data-flow into the unified `translatable_document` model, a module-boundary decision on where cell-level batching plugs into the translation seam (translation_service vs orchestrator vs chunker), and a numeric-passthrough business rule. These are non-obvious design/data-flow/operational-risk decisions that must be settled in `design.md` before `implementation-planner` runs.

## Required Artifacts

The following 7 artifacts are always required for implementation changes:
`change-request.md`, `change-classification.md`, `implementation-plan.md`, `test-plan.md`, `ci-gates.md`, `tasks.yml`, `context-manifest.md`

## Optional Artifacts

| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | No existing behavior is changing; tables are currently untranslated/passthrough. New capability, not a behavior override. |
| proposal.md | no | Scope is fixed by P3-3; no separate product investigation needed. |
| spec.md | no | Behavior fully captured in change-request + design + impl-plan. |
| design.md | yes | Architecture Review Required = yes: new ML runtime/failure mode, cell IR shape, batch-boundary placement, numeric-passthrough rule must be decided before planning. |
| qa-report.md | no | Routine pass/fail goes in agent-log/qa-reviewer.yml; escalate to yes only if blocking/approved-with-risk findings emerge. |
| regression-report.md | no | No existing behavior overridden. Promote to yes only if a regression surfaces. |
| visual-review-report.md | no | No UI surface touched. |
| monkey-test-report.md | no | Not warranted for a backend parser module. |
| stress-soak-report.md | no | Cell-batch is a single coalesced LLM call per table (reduces load). |

## Required Contracts
- contracts/data/data-shape-contract.md — add table/row/column/cell IR structure to the unified `translatable_document` model; record the new `ElementType` handling and cell-batch IR-consumption contract.
- contracts/business/business-rules.md — numeric-only cell passthrough rule, "cells from same table batched into one LLM request" rule, cell-granularity translation rule.

## Required Agents
- spec-architect (writes design.md: ML runtime/failure mode, cell IR shape, batch-boundary placement, numeric-passthrough rule)
- contract-reviewer (validates data-shape + business-rule contract updates)
- test-strategist (acceptance-criteria → test mapping; non-tautological selection/wiring tests)
- ci-cd-gatekeeper (writes ci-gates.md)
- implementation-planner (turns design + contracts + tests into execution packet)
- backend-engineer (implements parsers/table_recognizer.py + integration into pdf_parser/orchestrator/translation_service)
- qa-reviewer (release readiness, regression scope)

## Inferred Acceptance Criteria
- AC-1: A PDF containing a table is parsed and its structure is recognized as rows/columns/cells (via TableFormer or TATR), producing a typed table/cell representation in the unified IR.
- AC-2: Each text-bearing cell is translated individually at cell granularity (not as flattened paragraph text).
- AC-3: Numeric-only cells pass through unchanged — they are not sent to the LLM and their content is identical pre/post translation.
- AC-4: All translatable cells from the same table are coalesced into exactly one LLM batch request (assert one call per table and that the request payload contains the table's text cells, excluding numeric cells).
- AC-5: When the table-recognition ML model is unavailable or its weights fail to download, the parse path degrades gracefully (lazy-load failure mode, no crash), mirroring layout_detector behavior.
- AC-6: Degenerate tables (empty cells, all-numeric tables, merged/spanning cells) are handled without error and respect the numeric-passthrough and per-cell rules.

## Tasks Not Applicable
- 2.1 (API contract) — no new/changed endpoint; translation runs through existing job pipeline
- 2.2 (CSS/UI contract) — no UI surface touched
- 2.3 (Env contract) — ML model auto-downloads/lazy-loads per ADR 0003 pattern; no new env key or secret
- 2.6 (CI/CD contract) — no CI/CD workflow changes
- 3.3 (E2E/resilience) — Tier 2; graceful-degradation test covered by backend-engineer
- 3.4 (Data-boundary/monkey) — Tier 2; degenerate-table coverage by backend-engineer; no dedicated monkey-test-engineer
- 3.5 (Stress/soak) — Tier 2; cell-batch coalesces requests (reduces not increases load)
- 4.2 (Frontend) — no UI changes
- 4.3 (Env/deploy) — no deployment changes
- 5.1 (UI/UX review) — no UI
- 5.2 (Visual review) — no UI
- 6.3 (Informational gates) — none defined for Tier 2
- 6.4 (Nightly/weekly/manual gates) — not required for Tier 2

## Tier Floor Override
- tier-floor-override: 2
- rationale: Gate heuristic may escalate on vocabulary false-positives: "table" (document table, NOT database table — no ALTER TABLE / migration), "cache" (translation_cache.py in repo), "integration"/"batch"/"model" (routine feature-add terms). No data migration, no auth/secret change, no cache behavior change. Genuine risk is medium cross-module → Tier 2 correct.

## Clarifications / Assumptions
- Scope is PDF-only for table recognition (TableFormer/TATR operate on visual layout). DOCX/PPTX native table structure out of scope unless design decides to unify (see CER-001 in context-manifest.md).
- "Numeric-only" passthrough exact predicate is a business-rule decision for spec-architect to define in business-rules.md.
- Cell-batch boundary plugs into existing LLM batching seam (translation_service batch call), reusing model_router fallback chain; no new endpoint or job-API change.
- Model download is optional/lazy with graceful degradation (ADR 0003 pattern); no new env key or secret.
