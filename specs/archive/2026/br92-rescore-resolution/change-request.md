# Change Request

## Original Request

`contracts/business/business-rules.md:104` (BR-92) declares that segments
whose post-job QE score falls below `QE_RESCORE_THRESHOLD`
(`config.py:133-136`, default `0.5`) are "flagged for re-translation by the
post-translate hook (AC-2)." This is a **phantom business rule** — no code
path implements it.

Verified this session (spec-drift-auditor pass + direct grep/read, not just
agent-reported):
- `grep -rn QE_RESCORE_THRESHOLD` across the entire repo shows it referenced
  ONLY in its own definition/comment (`config.py:133-136`) and in tests
  (`tests/test_quality_evaluation.py:538-627`, `tests/test_env_contract.py:146-205`)
  that assert float-parsing and env/schema/template documentation presence —
  none of them test any actual rescore-triggering behavior, because none
  exists.
- The only real `post_translate_hook` usage for QE is
  `job_manager.py:386` (`post_translate_hook=qe_blocks.extend`), which feeds
  the bulk **dashboard-only** COMET scorer at `job_manager.py:418-447`. That
  code path stores scores into `job.quality` (`JobQualityRecord`) purely for
  the `/jobs/{id}/quality` display endpoint — it never triggers
  re-translation.
- `tests/test_quality_evaluation.py:538`
  (`test_below_threshold_triggers_retranslation`) is a tautological test — it
  only asserts a bare list comprehension (`[i for i,s in enumerate(scores) if
  s<threshold]`), not any production routing. Its name and its listing as
  BR-92's "verified-by" test create false green coverage.
- `contracts/env/env-contract.md:37-38` repeats the same phantom claim
  ("enabling QE makes the post-job rescore threshold (AC-2) active out of the
  box" / "flagged for re-translation").

## Business / User Goal

Close the gap between documented and actual behavior for BR-92 — either by
building the real feature (post-job QE score below threshold triggers an
actual re-translation pass) or by formally retiring the rule so the contracts,
config, and tests stop claiming behavior that doesn't exist. This is
primarily a **product decision** (is "low COMET dashboard score
auto-retranslates" a feature the user actually wants?), not a pure
architecture call — spec-architect should lay out both options with cost/risk,
but the final build-vs-retire choice should be confirmed with the user before
`implementation-plan.md` is treated as final.

## Non-goals

- Not touching the in-line critique loop (`translation_service.py:59-96`,
  BR-89/90) or the LLM-judge re-translation gate (`quality_judge.py`,
  BR-72-77) — those are real, correctly-implemented, separate mechanisms.
  Cross-referenced in the sibling `qa-mechanism-docs` change, not modified
  here.
- Not touching `qa-judge-provider-consistency` or `qa-judge-hang-recovery`'s
  scope (judge-loop provider routing / cancellation / timeout) — unrelated
  mechanism (mechanism (c) in the audit, not mechanism (b) this change
  concerns).
- Not touching `batch-critique-qe-scoring`'s scope (mechanism (a) batching) —
  confirmed unaffected.

## Constraints

- Whichever direction is chosen must be a complete, coherent change — not a
  partial fix that still leaves some artifacts (contract, config, tests,
  env-contract) out of sync with the others.
- If retiring: delete BR-92 from `business-rules.md`, remove
  `QE_RESCORE_THRESHOLD` from `config.py`, scrub the rescore claims from
  `env-contract.md:37-38` (and `.env.example.template`/`env.schema.json` if
  they also document it — check `tests/test_env_contract.py:174-205` for the
  full list of artifacts that currently assert its presence), and delete the
  tautological test — do not leave a dangling "verified-by" reference.
- If building: the real rescore→re-translate hook must reuse the established
  patterns elsewhere in this pipeline (graceful degradation on
  exception/unreachable, no transition to `status: failed` solely for QE
  failure, mirroring BR-56/BR-61's pattern) and must get real (non-tautological)
  test coverage.
- STOP after `implementation-plan.md` — no `backend-engineer`/`bug-fix-engineer`
  in this pass.

## Known Context

- Related audit: this finding came from a `spec-drift-auditor` pass this
  session covering the whole QA pipeline; see sibling change
  `qa-mechanism-docs` for the broader three-mechanism documentation this
  change's outcome will feed into (that change depends on this one completing
  first, so its docs reflect final behavior).
- `contracts/business/business-rules.md` BR-55/56 (job-end bulk COMET
  scoring, dashboard-only) is the mechanism BR-92 was apparently meant to
  extend into a gate — read those alongside BR-92 for contrast.

## Open Questions

- **Build vs. retire** — RESOLVED: user confirmed **Retire**. spec-architect's
  design.md laid out both options (see design.md's Recommendation table):
  retire is near-zero cost and not a policy-defined breaking change (env-var
  removal isn't covered by the API `deprecate-2-minors` policy, which is
  scoped to API fields only); build would require reusing the BR-76/77
  judge-apply re-render machinery (outputs are archived before QE runs,
  job_manager.py:412-418) and would be functionally redundant with the
  already-real LLM-judge re-translation gate (BR-72-77). `implementation-plan.md`
  proceeds on the retire direction only.

## Requested Delivery Date / Priority

No fixed deadline. Not urgent (no live incident tied to this one, unlike the
sibling `qa-judge-hang-recovery` change) — plan now, decide direction with the
user, implement later.
