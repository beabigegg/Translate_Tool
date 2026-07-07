# ADR 0014: Retiring a phantom business rule and its inert env var (BR-92 / QE_RESCORE_THRESHOLD)

## Status
proposed

## Context
BR-92 ("qe-rescore-threshold") and its env var `QE_RESCORE_THRESHOLD` documented a
post-job behavior — segments whose CometKiwi score fell below the threshold would be
flagged for re-translation by the post-translate hook — that **no code ever implemented**.
The constant was parsed in `config.py` but never read by any code path; contracts
(`business-rules.md`, `env-contract.md`, `env.schema.json`, `.env.example.template`,
`data-shape-contract.md`) and tests asserted its presence, and two data-shape rows even
claimed it was "wired in job_manager.py post-translate hook (CER-002)". This is pure
spec-drift: the artifacts overclaim behavior the runtime does not have.

The build-vs-retire decision (design.md) weighed implementing the rescore→re-translate
pass versus deleting the phantom rule. Building it would add a second COMET-based
re-translation gate largely redundant with the existing LLM-judge gate (BR-72..BR-77) and
would have to reuse the judge-apply re-render/re-archive machinery. The user confirmed
**RETIRE**.

This repo has no prior precedent for formally retiring a business rule, so the retirement
convention needs recording — hence this ADR.

## Decision
Retire BR-92 and `QE_RESCORE_THRESHOLD` by **hard deletion** from every live artifact
(contract, config, env schema/template, data-shape rows, and the tests that asserted their
presence), with the presence-tests inverted into absence-tests plus a live-surface
zero-reference sweep.

Retirement convention established here:
- A rule/var that describes behavior **no code implements** is spec-drift and is deleted
  outright, not deprecated. There is no runtime consumer to keep working, so no
  compatibility shim, alias, or grace window is warranted.
- Env-var removal is **not** a policy-defined breaking change: the `deprecate-2-minors`
  policy is API-field-scoped, and this var was operationally inert (removing it changes no
  behavior). Operators who set it in their environment simply have an ignored variable
  before and after.
- Surviving business rules are **not renumbered**; BR-92 leaves a numbering gap by design
  so historical references remain unambiguous.
- Rollback is a plain `git revert` of the retirement commit — it restores the phantom
  artifacts exactly. No contract/schema downgrade path is required.

## Consequences
- `business-rules.md` now has a permanent gap at BR-92 (BR-91 → BR-93). Future readers
  find the retirement recorded here and in the change's `specs/` archive.
- The QE per-segment score list (`data-shape-contract.md`) is documented as feeding only
  the critique adoption gate (BR-89); the false post-job-rescore wiring claim is removed.
- A regression sweep (`test_qe_rescore_threshold_zero_references_repo_wide`) guards the
  live surface (`app/backend`, `contracts/`) against the symbol reappearing; it
  intentionally excludes `tests/`, `specs/`, and the auto-generated `.cdd/code-map.yml`.
- This ADR is the reusable precedent for the next phantom-rule retirement: delete from live
  artifacts, invert the tests, add a scoped zero-reference sweep, leave a numbering gap,
  and rely on `git revert` for rollback.
