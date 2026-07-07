---
change-id: qa-mechanism-docs
schema-version: 0.1.0
last-changed: 2026-07-07
---

# Implementation Plan: qa-mechanism-docs

## Objective

Land three documentation-only contract edits that make the QA/quality
pipeline's three independent quality mechanisms legible in one place and stop
the API/data-shape surfaces from implying a gating relationship that does not
exist. No behavior, schema, field, type, or nullability change. The exact
wording and placement were drafted and approved by contract-reviewer
(`agent-log/contract-reviewer.yml`); this plan is the execution packet that
turns that approval into a low-ambiguity landing sequence.

The three edits:
1. New Decision Table (Table Y) in `contracts/business/business-rules.md`
   cross-referencing the three mechanisms (satisfies AC-1..AC-4, AC-7).
2. Advisory/non-gating language on `quality_score_avg` in
   `contracts/api/api-contract.md` (satisfies AC-5).
3. Advisory/non-gating language on the `JobQualityRecord`/QE representation in
   `contracts/data/data-shape-contract.md` (satisfies AC-6).

## Execution Scope

### In Scope
- Add one new Decision Table (Table Y) to `business-rules.md`, Table-U-style,
  cross-referencing (not restating) BR-54..58 (mech 2), BR-72..77 + the
  finalized sibling BR-98/99/100 (mech 3), and BR-89/90 (mech 1, batched per
  `batch-critique-qe-scoring`).
- Add advisory/non-gating prose to the `quality_score_avg` notes cell in
  `api-contract.md` (notes column only).
- Add an advisory/non-gating paragraph before `### BlockQualityScore — data
  shape` in `data-shape-contract.md`.
- Patch-level frontmatter version bumps + `last-changed` refresh on all three
  edited contracts.
- `contracts/CHANGELOG.md` entries (drafted by contract-reviewer).
- Re-run `cdd-kit openapi export --out contracts/api/openapi.yml` after the
  api-contract.md edit and commit the regenerated file.

### Out of Scope
- Any change to the actual behavior of mechanisms 1/2/3. Behavior fixes are the
  sibling changes `br92-rescore-resolution`, `qa-judge-provider-consistency`,
  `qa-judge-hang-recovery` — do not touch their code, tests, or contracts here.
- Any schema/field/type/nullability change to `quality_score_avg`,
  `JobQualityRecord`, or `BlockQualityScore`. This edit is prose only.
- Restating BR-54..58, BR-72..77, BR-89/90, BR-98/99/100 verbatim. Table Y
  cross-references them; it does not rewrite them.
- Editing `openapi.json` by hand (it is regenerated, not hand-edited).
- Any UI, env, CI/CD, backend, or frontend code. No `backend-engineer` /
  `frontend-engineer` / test-authoring agent is in scope for this change.
- Applying the edits in this pass. This planning pass STOPS at
  implementation-plan.md; the actual contract-file edits are a later,
  separately-approved implementation pass.

## Required Changes

| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | business-rules.md | Insert new `### Table Y — QA quality-mechanism relationships` (Table-U-style Decision Table) after Table X, before `## Change Policy`. Content must satisfy AC-1..AC-4 and cross-reference (not restate) BR-54..58, BR-72..77, BR-89/90, BR-98/99/100 per AC-7. Use contract-reviewer's approved wording. | contract-reviewer (implementation capacity) |
| IP-2 | api-contract.md | Extend the `quality_score_avg` notes cell (line 154) with advisory/non-gating language; no other column changes. Satisfies AC-5. | contract-reviewer (implementation capacity) |
| IP-3 | data-shape-contract.md | Insert advisory/non-gating paragraph immediately before `### BlockQualityScore — data shape` (line 476). Satisfies AC-6. No table/field change. | contract-reviewer (implementation capacity) |
| IP-4 | frontmatter | Bump `schema-version` (patch) + refresh `last-changed` on all three files: business 0.23.0->0.23.1, api 0.10.0->0.10.1, data 0.15.0->0.15.1. | contract-reviewer (implementation capacity) |
| IP-5 | contracts/CHANGELOG.md | Append the three drafted CHANGELOG entries (one per edited contract). | contract-reviewer (implementation capacity) |
| IP-6 | api openapi export | Run `cdd-kit openapi export --out contracts/api/openapi.yml`; commit regenerated `openapi.yml` (and `openapi.json` if the exporter regenerates it). | contract-reviewer (implementation capacity) |

## Source Artifact Pointers

| source | relevant pointer | used for |
|---|---|---|
| change-classification.md | Inferred Acceptance Criteria AC-1..AC-7 | content requirements for each edit |
| change-classification.md | Required Contracts / Required Agents | scope of edits + owner-map (no backend/frontend) |
| change-request.md | "Sibling Decisions (now finalized)" | in-prompt brief for BR-92 retirement + BR-98/99/100; do NOT expect these live in the contract file yet |
| agent-log/contract-reviewer.yml | summary + artifacts | authoritative source of drafted wording, placement, version bumps, CHANGELOG entries — reproduce, do not re-derive |
| context-manifest.md | Allowed Paths | read boundary; CER-001 (sibling specs dirs) rejected — brief in-prompt |
| business-rules.md | Table X (L407-414) + `## Change Policy` (L416) | insertion anchor for Table Y |
| api-contract.md | `quality_score_avg` row (L154) | insertion anchor for IP-2 |
| data-shape-contract.md | `### BlockQualityScore — data shape` (L476) | insertion anchor for IP-3 |

## File-Level Plan

| path or glob | action | notes |
|---|---|---|
| contracts/business/business-rules.md | edit | Insert Table Y between L415 (blank after Table X) and L416 (`## Change Policy`). Bump frontmatter 0.23.0->0.23.1, `last-changed`. Use Bash string-anchored replace (see Tooling note). |
| contracts/api/api-contract.md | edit | Extend notes cell of the `quality_score_avg` row (L154). Bump frontmatter 0.10.0->0.10.1, `last-changed`. MUST use Bash string-anchored replace — `CDD_CONTRACT_WRITE_STRICT=1` hook blocks Edit/Write on this file. |
| contracts/api/openapi.yml | regenerate | `cdd-kit openapi export --out contracts/api/openapi.yml` after L154 edit; commit. CI `openapi export --check` fails if stale. |
| contracts/api/openapi.json | regenerate (if exporter emits) | Do not hand-edit. |
| contracts/data/data-shape-contract.md | edit | Insert advisory paragraph before `### BlockQualityScore — data shape` (L476). Bump frontmatter 0.15.0->0.15.1, `last-changed`. Use Bash string-anchored replace. |
| contracts/CHANGELOG.md | append | Three drafted entries (business, api, data). Outside this planner's read scope — reproduce from contract-reviewer's drafted text in the implementation pass. |

### Tooling note (mandatory for the implementation pass)
- `CDD_CONTRACT_WRITE_STRICT=1` arms `pre-tool-use-contract-write.sh`, which
  blocks ALL Edit/Write/MultiEdit calls on `contracts/api/api-contract.md`
  (including frontmatter and free-form prose). IP-2 and the api frontmatter bump
  MUST be done via Bash string-anchored replace (e.g. a python/sed anchored
  substitution), not the Edit tool.
- The hook is confirmed (per promoted CLAUDE.md learning) to target
  `api-contract.md` specifically. Whether it also intercepts
  `business-rules.md` / `data-shape-contract.md` is NOT independently confirmed
  this pass. Regardless: use Bash string-anchored replace for ALL THREE files.
  Rationale: `cdd-kit contract` has no CLI command for free-form prose or
  Decision-Table edits, so the CLI path is unavailable for every one of these
  edits; Bash-replace is the safe, uniform default (contract-reviewer's
  recommendation).
- After the api-contract.md edit, `cdd-kit openapi export --out
  contracts/api/openapi.yml` is REQUIRED and the regenerated file committed, or
  the CI `openapi export --check` gate fails on drift.

## Contract Updates

- API: `contracts/api/api-contract.md` — `quality_score_avg` notes cell gains
  advisory/non-gating language (AC-5). Prose only; schema unchanged. Frontmatter
  0.10.0->0.10.1. Requires openapi re-export.
- CSS/UI: none.
- Env: none.
- Data shape: `contracts/data/data-shape-contract.md` — advisory/non-gating
  paragraph before `### BlockQualityScore — data shape` covering
  `JobQualityRecord` (AC-6). Prose only; fields/types/nullability unchanged.
  Frontmatter 0.15.0->0.15.1.
- Business logic: `contracts/business/business-rules.md` — new Table Y
  cross-referencing the three mechanisms (AC-1..AC-4, AC-7). Frontmatter
  0.23.0->0.23.1.
- CI/CD: none (no workflow change). Note the mechanical `openapi export` +
  `cdd-kit validate` re-runs below are verification, not CI-config edits.

## Test Execution Plan

| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1..AC-4, AC-7 | contracts/business/business-rules.md | Table Y present after Table X, before `## Change Policy`; cross-references present; contract-reviewer confirms accuracy |
| AC-5 | cdd-kit openapi export --out contracts/api/openapi.yml | export succeeds; `cdd-kit openapi export --check` stays green (no schema drift) |
| AC-6 | contracts/data/data-shape-contract.md | advisory paragraph present before BlockQualityScore; no field/type/nullability delta |
| AC-1..AC-7 | cdd-kit validate | all contract validators + BR-id validator pass |

No unit/contract/integration test authoring is in scope (no schema/behavior
change; classification Required Tests = none). Required test-phase floor
(collect / targeted / changed-area) selects to an empty/no-op set for this
documentation-only change; the gate is satisfied by `cdd-kit validate` and the
`openapi export --check` staying green. Do not author or run broad pytest for
this change.

## Handoff Constraints

- Implementation agents must not infer missing requirements from chat history.
- The verbatim Table Y text, api note-cell wording, data-shape paragraph, and
  CHANGELOG entries are owned and were drafted by contract-reviewer
  (`agent-log/contract-reviewer.yml`). The implementation pass reproduces that
  approved wording — the implementation-planner does not author contract prose,
  and no agent should re-derive the wording from scratch.
- Do not re-copy full design, test strategy, CI policy, or contract prose into
  this plan; follow the source pointers above.
- Sibling BR-92 retirement and BR-98/99/100 exist only in the siblings' own
  specs at this time; do NOT expect them live in `business-rules.md`. Table Y
  references the finalized sibling decisions per change-request.md's "Sibling
  Decisions" section (in-prompt brief; CER-001 for cross-change reads was
  rejected and is non-approvable).
- Keep implementation within the file-level plan. If any required file,
  behavior, contract, or test is missing, stop and report `blocked`.

## Known Risks

- Placement drift: `business-rules.md` line numbers shift as siblings land. The
  implementation pass must anchor on the LITERAL strings `### Table X — ...` /
  `## Change Policy` (not line 416) when doing the Bash-replace, since sibling
  changes may add tables ahead of landing.
- Stale openapi: forgetting the `cdd-kit openapi export` re-run after the
  api-contract.md edit fails the CI `openapi export --check` gate. IP-6 is not
  optional.
- Hook-scope uncertainty for business/data files (see Tooling note) — mitigated
  by mandating Bash-replace for all three regardless.
- Version-bump/CHANGELOG omission: `cdd-kit gate`/validators expect the patch
  bumps and CHANGELOG entries; skipping IP-4/IP-5 can block the gate.
- `.cdd/code-map.yml` currency was not needed for this doc-only, contract-file
  change (no source symbols in scope), so it was not consulted; not a risk here.
