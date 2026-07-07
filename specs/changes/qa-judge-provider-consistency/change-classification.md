# Change Classification

## Change Types
- primary: business-logic-change
- secondary: bug-fix (silent-divergence correctness), config-behavior-change

Atomic-split check: no trigger fires. Single change-type, single surface
(backend judge/QA re-translation), ≤2 contracts, well under 10 task-IDs.
This is a focused two-file behavior fix — proceed as one change.

## Lane
- feature

Rationale: root cause and code location are already fully identified
(`job_manager.py:493-510` `_translate_fn`, `quality_judge.py:89-108`), and
the request needs a new/updated business rule to make QA re-translation
provider an explicit contract. Per the Mixed-cases rule, a fix that requires
a contract change is promoted out of the pure bug-fix lane to
`business-logic-change` so the contract path is forced.

## Risk Level
- medium

Provider-routing correctness inside the judge/QA re-translation loop. Not
auth/payments/migration, but it changes which provider executes a live LLM
call, so classify upward.

## Impact Radius
- module-level (confined to `services/job_manager.py`, `services/quality_judge.py`, plus `config.py`/`clients/` plumbing it reuses; main bulk-translation routing (`model_router.py`) is an explicit non-goal)

## Tier
- 2

## Architecture Review Required
- yes
- reason: The change-request explicitly defers two non-obvious design
  decisions to spec-architect — (a) whether QA re-translation reuses the
  exact scoring client/model or builds a distinct "translation-role" panjit
  client (depends on `providers.yml`'s actual shape), and (b) whether a new
  business rule (near BR-97/BR-72) is required to document the
  provider-consistency guarantee.

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

STOP after `implementation-plan.md` — no `backend-engineer`/`bug-fix-engineer` this pass.

## Optional Artifacts (default: no — set yes only with explicit reason)
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | Current behavior already precisely documented in change-request.md with line-level pointers |
| proposal.md | no | Goal is unambiguous; no product/user-facing decision to investigate |
| spec.md | no | No new user-facing behavior surface |
| design.md | yes | Architecture Review Required = yes; spec-architect must settle the client/model-role and business-rule questions |
| qa-report.md | no | Planning-only pass |
| regression-report.md | no | |
| visual-review-report.md | no | No UI surface |
| monkey-test-report.md | no | |
| stress-soak-report.md | no | |

## Required Contracts
- API: none
- CSS/UI: none
- Env: review-only — `JUDGE_CLOUD_PROVIDER_ID` already exists; non-goal forbids a new config surface. Confirm no new var; update prose only if needed.
- Data shape: none
- Business logic: yes — `contracts/business/business-rules.md`. Add/extend a rule (near BR-97/BR-72–77) stating that when the judge pass runs, QA re-translation MUST route through `JUDGE_CLOUD_PROVIDER_ID`'s provider, decoupled from `last_client`; MAY differ in model/endpoint within that provider but MUST NOT diverge in provider.
- CI/CD: none

## Required Tests
- unit: assert the re-translation callback constructs/uses the `JUDGE_CLOUD_PROVIDER_ID` (panjit) client rather than `last_client`; assert the already-panjit case is a behavioral no-op; assert the divergent case now routes to panjit. Assert WHICH provider is used, not merely that some client was called.
- contract: assert the new business rule is present/consistent; BR-97 skip semantics unchanged.
- integration: judge-loop path with mocked clients verifying scoring and re-translation both resolve to the panjit provider when the judge pass runs; verify BR-97 still skips both when winning provider is `deepseek`.
- E2E/visual/data-boundary/resilience/fuzz/stress/soak: none

Test-authoring caution (promoted learning): patch client symbols at the
binding point actually used at call time; prefer `patch.object` on a
collection-time-captured module ref; do not wire a mock against itself.

## Required Agents
- spec-architect — write `design.md`; resolve the reuse-vs-distinct-client and business-rule questions against `providers.yml`'s real shape
- contract-reviewer — own the business-rule addition/wording and env review
- test-strategist — author `test-plan.md` and the acceptance-criteria → test mapping
- implementation-planner — turn design + contract + tests into `implementation-plan.md` (execution stops here this pass)
- qa-reviewer — release-readiness / scope-consistency review of the plan artifacts

## Inferred Acceptance Criteria
- AC-1: When the judge pass runs (main translation provider is not `deepseek`, per BR-97), the QA-phase re-translation callback (`_translate_fn`) routes through `JUDGE_CLOUD_PROVIDER_ID`'s provider (panjit), independent of `last_client`.
- AC-2: When `last_client` already resolves to the panjit provider, the change is a behavioral no-op (identical requests and responses) — only the divergent case changes.
- AC-3: The re-translation client is built via the existing `_build_cloud_client()`/`providers.yml`/`JUDGE_CLOUD_PROVIDER_ID` plumbing; no new configuration surface is introduced.
- AC-4: Re-translation MAY use a different model/endpoint within panjit than scoring, but MUST NOT execute against a different provider than the judge's scoring provider.
- AC-5: BR-97's skip condition and BR-72–BR-77 remain unchanged; only which client executes the re-translation call changes.
- AC-6: A new or extended business rule in `contracts/business/business-rules.md` documents the QA re-translation provider-consistency guarantee.
- AC-7: The `last_client is None` fallback no longer silently drops to `OllamaClient(DEFAULT_MODEL)` when the judge pass runs; the judge-provider client is used instead.

## Tasks Not Applicable
- not-applicable: 1.4, 2.1, 2.2, 2.3, 2.4, 2.6, 3.3, 3.4, 3.5, 4.2, 4.3, 4.4, 5.1, 5.2

(2.1 API + 2.2 CSS/UI + 2.4 Data shape + 2.6 CI/CD contracts: none needed. 3.3
E2E/resilience + 3.4 data-boundary + 3.5 stress/soak: not applicable to this
backend provider-routing fix. 4.2 Frontend + 4.4 CI/CD workflows: no FE or
workflow change. 5.1 UI/UX + 5.2 Visual review: no UI surface. Task 1.3
REMAINS applicable.)

## Clarifications or Assumptions
- Open (deferred to spec-architect): reuse the exact scoring client/`JUDGE_MODEL` for re-translation vs. build a distinct translation-role panjit client with its own model — hinges on `providers.yml`'s real shape.
- Open (deferred to contract-reviewer/spec-architect): exact new business-rule number and whether it extends the BR-97/BR-72 cluster.
- Context Expansion Request needed for `config/providers.yml` (gitignored runtime file; only `.example` is index-tracked) — see context-manifest.md CER-001.
