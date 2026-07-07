# Change Classification

## Change Types
- primary: documentation-change (contract documentation)
- secondary: api-only-change (doc-only), business-logic-change (doc-only), data-shape-change (doc-only)

Note on secondaries: flagged only because edits land in the API, business,
and data-shape contract files. No behavior, schema, field, type, or
nullability change — the secondaries force the contract-review path, not
code/test work.

## Lane
- feature

Not bug-fix: the "mechanisms 1 and 3 can disagree" observation is being
documented as intentional current behavior, not fixed — all three actual
behavior fixes are the sibling changes, out of scope here.

## Risk Level
- low

## Impact Radius
- cross-module (touches 3 contract surfaces: api/data/business-domain) — but purely prose; no runtime coupling changes

## Tier
- 4

Rationale: contract documentation-only edits (clarifying language + one
cross-reference section/table), no behavior/schema change. Not Tier 5
fast-path because touched files are contracts (Tier 5 is limited to prose
docs/prompts). Tier 4 keeps the contract-review path forced.

## Architecture Review Required
- no
- reason: n/a. The one design-ish question (placement: Decision Table vs.
  prose vs. new ADR) is a contract-authoring decision within
  contract-reviewer's domain, already informed by this session's earlier
  contract-reviewer findings. No module-boundary, data-flow, migration, or
  compatibility trade-off — this change deliberately depends on three
  siblings so it only records already-finalized behavior.

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

STOP after `implementation-plan.md` — the plan captures exact drafted wording
+ placement; actual contract-file edits are a later, separately-approved
pass (`pre-tool-use-contract-write.sh`/`CDD_CONTRACT_WRITE_STRICT=1` requires
the `cdd-kit contract` CLI or Bash string-replace for `api-contract.md`, not
direct Edit/Write).

## Optional Artifacts (default: no)
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | current behavior already captured via direct code reads this session |
| proposal.md | no | no product/behavior decision open |
| spec.md | no | no user-facing behavior change |
| design.md | no | Architecture Review Required = no |
| qa-report.md | no | no blocking findings expected; use agent-log pointer |
| regression-report.md | no | no behavior change to regress |
| visual-review-report.md | no | no UI surface |
| monkey-test-report.md | no | n/a |
| stress-soak-report.md | no | n/a |

## Required Contracts
- API: yes — contracts/api/api-contract.md quality_score_avg gains "advisory/non-gating" language (prose only, schema unchanged)
- CSS/UI: no
- Env: no
- Data shape: yes — contracts/data/data-shape-contract.md JobQualityRecord gains "advisory/non-gating" language (prose only)
- Business logic: yes — contracts/business/business-rules.md gains a cross-referencing "how the three QA mechanisms relate" section/table (Decision-Table style, Table U precedent)
- CI/CD: no

## Required Tests
- unit: none
- contract: none new — no schema/field/type/nullability change; if wording edits trigger openapi export-check or a BR-id validator, implementation pass re-runs `cdd-kit openapi export`/`cdd-kit validate` (mechanical, not a new test)
- integration/E2E/visual/data-boundary/resilience/fuzz/stress/soak: none

## Required Agents
- implementation-planner — turns drafted wording + placement into the execution packet (STOP here)
- contract-reviewer — primary owner; confirms cross-reference accuracy against BR-55/56, BR-72-77, BR-89/90, BR-98/99/100; confirms "advisory/non-gating" wording implies no schema/behavior change; confirms placement
- qa-reviewer — release-readiness/gate-readiness confirmation (agent-log pointer only)

No backend/frontend/test implementation agents — no code, test, or UI surface in scope.

## Inferred Acceptance Criteria
- AC-1: contracts/business/business-rules.md contains one new cross-referencing "how the three QA mechanisms relate" section/table (Decision-Table style, Table U precedent) covering mechanism 1 (critique loop, BR-89/90, relative COMET, batched per batch-critique-qe-scoring), mechanism 2 (bulk COMET rescore, BR-55/56), mechanism 3 (LLM-judge, BR-72-77 + BR-98/99/100).
- AC-2: The new section states mechanism 2 is permanently advisory/dashboard-only (post BR-92 retirement) and never triggers re-translation.
- AC-3: The new section states mechanism 3 (LLM-judge) is the only mechanism that gates re-translation.
- AC-4: The new section records the "no bridging between mechanism 1 and mechanism 3" disagreement behavior as intentional/current (unresolved by any sibling change, out of scope for all three).
- AC-5: contracts/api/api-contract.md quality_score_avg gains explicit "advisory / non-gating" language with no schema change (verifiable via `cdd-kit openapi export --check` staying green).
- AC-6: contracts/data/data-shape-contract.md JobQualityRecord gains explicit "advisory / non-gating" language, no schema change.
- AC-7: The change references (does not restate) existing BR-55/56, BR-72-77, BR-89/90, BR-98, BR-99, BR-100 and sibling changes' decisions.

## Tasks Not Applicable
- not-applicable: 1.3, 1.4, 2.2, 2.3, 2.6, 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 4.4, 5.1, 5.2

(1.3 no design review needed. 1.4/2.6/4.4 no CI/CD change. 2.2/2.3 no CSS/env
change. All 3.x test-authoring and 4.x implementation rows: no code/test
surface — this is documentation only. 5.1/5.2 no UI surface.)

## Clarifications or Assumptions
- Assumption: all three depends-on siblings have landed in planning (BR-92
  retirement confirmed, BR-98/99/100 designed) before this change's agents
  run — true as of this pass.
- Doc-only contract changes still STOP after implementation-plan.md per this
  repo's established pattern (draft exact wording now; apply via `cdd-kit
  contract` CLI / Bash string-replace in a later, separately-approved pass).
- No new ADR created; the relationship note lives as a Decision Table in
  business-rules.md per contract-reviewer's earlier-session recommendation.
- CER-001 (requesting sibling specs/changes/* dirs for design.md citations) is
  NOT approvable — `.cdd/context-policy.json`'s forbiddenPaths baseline
  blocks all cross-change specs/changes/* reads unconditionally. Main Claude
  briefs contract-reviewer/implementation-planner directly, in-prompt, with
  the finalized sibling decisions instead (already summarized in this
  change's own change-request.md "Sibling Decisions" section).
