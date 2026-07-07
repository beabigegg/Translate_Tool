# Design: br92-rescore-resolution

## Summary
BR-92 (`business-rules.md:104`) claims that segments scoring below
`QE_RESCORE_THRESHOLD` (`config.py:136`, default 0.5) are "flagged for
re-translation by the post-translate hook." No code implements this. The only
real QE post-translate hook (`job_manager.py:386`, `post_translate_hook=qe_blocks.extend`)
feeds the bulk, dashboard-only COMET scorer (`job_manager.py:418-447`), which
writes `JobQualityRecord` for `GET /jobs/{id}/quality` and never re-translates.
This document lays out both resolution directions — **retire** the phantom rule,
or **build** the real gate — with concrete edits, cost, and risk. It does not
pick a direction; that is the user's decision (AC-1).

## Affected Components
| component | file path(s) | nature of change |
|---|---|---|
| Business rule | `contracts/business/business-rules.md:104` (BR-92) | retire: delete row; build: rewrite to describe real gate + real verified-by test |
| Config flag | `app/backend/config.py:133-136` | retire: remove `QE_RESCORE_THRESHOLD`; build: keep, now actually consumed |
| Env contract | `contracts/env/env-contract.md:38` + `:37` | retire: delete row 38 and scrub the "post-job rescore threshold (AC-2)" phrase in the QE_ENABLED row (37); build: correct wording |
| Env schema | `contracts/env/env.schema.json:116-121` | retire: delete property; build: keep |
| Env template | `contracts/env/.env.example.template:68-72` | retire: delete lines; build: keep |
| Data-shape contract | `contracts/data/data-shape-contract.md:787` | **both directions must touch** — asserts BR-92 is "wired in job_manager.py post-translate hook, CER-002" (false). NOT in the change-request checklist nor Allowed Paths — see Open Risks. |
| Unit test | `tests/test_quality_evaluation.py:538-627` | retire: delete tautological `test_below_threshold_triggers_retranslation` + presence tests (605-627); build: replace with real routing test |
| Contract test | `tests/test_env_contract.py:164-206` | retire: delete rescore-presence asserts; build: keep |
| QE rescore path | `app/backend/services/job_manager.py:412-447` | build only: below-threshold filter + re-translate + re-render/re-archive |

## Key Decisions
This change frames a decision; it does not make it. The two directions:

### Direction A — Retire
- **Edits**: delete BR-92 row (`business-rules.md:104`); remove
  `QE_RESCORE_THRESHOLD` (`config.py:133-136`); scrub AC-2 rescore claims from
  `env-contract.md:37-38`, `env.schema.json:116-121`,
  `.env.example.template:68-72`; fix the false "wired... CER-002" claim in
  `data-shape-contract.md:787`; delete the tautological unit test and the four
  presence tests across `tests/test_quality_evaluation.py` and
  `tests/test_env_contract.py` that assert the var's mere existence (full grep
  list is 8 test-file hit sites + `.cdd/code-map.yml:306`, which regenerates).
- **Compatibility**: the API Compatibility Policy (`api-contract.md:368-378`,
  `deprecate-2-minors`) is scoped to **API paths and response fields only** — it
  does not cover env vars, and no separate env-var deprecation policy exists in
  this repo. Removing `QE_RESCORE_THRESHOLD` is therefore **not** a policy-defined
  breaking change. Operationally it is inert: the var already does nothing, so an
  operator who set it sees identical behavior before and after removal. No
  deprecation window is technically required; a one-line CHANGELOG note is
  courtesy, not obligation.
- **Cost**: near-zero. Contract/config/test deletions only; no runtime code path
  changes. This would be the **first formal BR retirement in the repo** (no
  precedent per contract-reviewer) — establishing the convention is the only
  non-trivial part, and warrants a short ADR (see ADR note below).
- **Risk**: functionally none. Sole risk is external documentation or a user
  expecting the behavior — unlikely, since it never worked.

### Direction B — Build
- **Architectural blocker (surface first)**: outputs are archived at
  `job_manager.py:412-416` **before** QE scoring runs at `:418`. A real
  rescore→re-translate gate that acts on scores computed at `:418-447` therefore
  operates on **already-archived output**. To reflect re-translated text in the
  downloadable file it must **re-render and re-archive** — the same expensive
  path the LLM-judge apply flow already owns (BR-76/BR-77, `POST /jobs/{id}/judge/apply`,
  re-render into a temp dir, atomic swap of `output_zip` on success). This is a
  much larger blast radius than the change-request's stated scope (it touches the
  renderer pipeline, cache invalidation, and job-lifecycle state), and it should
  **reuse the BR-77 re-render machinery rather than invent a parallel one**.
- **Re-translate strategy**: two options — (1) the critique-loop pattern
  (`translation_service.py:59-96`, BR-89/90: LLM revise, adopt-iff-COMET-better,
  relative), or (2) a simpler feedback-free single-shot re-translate. Absolute-
  threshold gating (score < 0.5 → retranslate) structurally matches BR-72's
  judge-tier gate, not the relative critique gate.
- **Graceful degradation**: must mirror BR-56/BR-61 — any QE or re-render failure
  is caught, logged WARNING, job still completes with the original output; never
  `status: "failed"` solely for a rescore failure.
- **Redundancy concern (honest assessment)**: the LLM-judge gate (BR-72-77)
  **already performs absolute score-tier-based re-translation with re-render/apply**.
  A built BR-92 would be a **second, COMET-based re-translation gate sitting
  beside the existing LLM-judge gate** — two independent quality gates that can
  both re-translate the same job on different score scales, with unclear
  precedence and doubled render cost. This is real semantic overlap, not a
  complementary feature. Before building, the user should ask whether COMET-gated
  auto-retranslation adds anything the judge gate does not already provide.
- **Cost**: real implementation — hook wiring, re-render/re-archive integration,
  cache-invalidation handling, resilience tests, integration tests. Comparable in
  scope to a slice of the p3-llm-judge apply feature.
- **Risk**: medium — renderer/output pipeline, cache invalidation, and the same
  graceful-degradation guarantees as BR-56/61; plus the redundancy/precedence
  question above.

## ADR note
No ADR is written now because no direction is chosen (the call is the user's).
Whichever is chosen carries a non-obvious, hard-to-reverse decision that SHOULD
get an ADR at implementation time: **Retire** establishes the repo's first
BR-retirement convention; **Build** commits to a second parallel re-translation
gate whose reversal would later look like a regression. `implementation-planner`
should author the ADR once the direction is confirmed.

## Migration / Rollback
- **Retire**: pure deletion; rollback is `git revert`. No data migration, no env
  migration (var is inert). No runtime behavior changes for any deployment.
- **Build**: additive behind `QE_ENABLED` + threshold; rollback is
  `QE_RESCORE_THRESHOLD` set unreachably low (or revert). Re-render swap must be
  atomic (temp dir → swap on success, BR-77 pattern) so a failed rescore never
  corrupts the archived output.

## Open Risks
- **Checklist gap**: `contracts/data/data-shape-contract.md:787` asserts BR-92 is
  "wired in job_manager.py post-translate hook, CER-002" — this is false today and
  is NOT listed in the change-request retire checklist, the classification's
  Required Contracts, or the context-manifest Allowed Paths. Either direction
  leaves a false/stale claim if this line is not corrected. Recommend a Context
  Expansion Request to add `contracts/data/data-shape-contract.md` before
  implementation, or explicitly fold it into the retire/build edit set.
- Build-only: precedence between a COMET rescore gate and the LLM-judge gate
  (BR-72-77) is undefined and must be decided if Build is chosen.
- Build-only: re-render cost and cache-invalidation semantics are unquantified in
  the change-request's stated scope.

## Recommendation for User Decision
This section is **input for the user's decision, not a decision**. spec-architect
does not pick the direction.

| dimension | Retire | Build |
|---|---|---|
| Implementation cost | Near-zero (deletions only) | Real (re-render integration, new tests) |
| Blast radius | Contracts/config/tests | Renderer + archive + cache + job lifecycle |
| Compatibility impact | None (env var is inert; not covered by deprecate-2-minors) | Additive behind existing flag |
| Functional risk | None | Medium (BR-56/61 degradation + atomic re-archive) |
| New value delivered | None (removes a knob that already does nothing) | COMET-gated auto-retranslation — **but largely redundant with the existing LLM-judge gate (BR-72-77)** |
| Precedent set | First formal BR retirement (needs convention + ADR) | Second parallel re-translation gate (needs precedence + ADR) |
| Leftover-artifact risk | Low if data-shape-contract.md:787 is included | Same |

**Honest engineering read (informational, not a decision)**: Retire is the
lower-risk, coherent close-out — it makes every artifact tell the truth at
near-zero cost and loses nothing that currently functions. Build only makes sense
if the user specifically wants a COMET-scale auto-retranslation gate that the
existing LLM-judge gate does not already cover; given the judge gate already does
score-tier-based re-translation with re-render/apply, a second COMET gate risks
being redundant machinery. The final build-vs-retire call is the user's.